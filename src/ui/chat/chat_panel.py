"""聊天中心面板 —— 三列布局编排 + 消息持久化流水线

迁移自 _pages/chat.py（D6：流式机制不变，渲染升级）。
数据流：session_state 会话 → ChatService 持久化 → chat_stream 流式。
"""

import streamlit as st

from src.services.chat_service import ChatService
from src.ui import ui_state
from src.ui.session_state import (
    init_chat_sessions, create_chat_session, get_active_messages,
    add_chat_session_message, run_async_safe,
)
from src.ui.chat.message_list import (
    bubble_html, render_message_list, render_streaming_cursor,
    render_streaming_placeholder,
)
from src.ui.chat.quick_commands import render_quick_commands
from src.ui.chat.session_list import render_session_list


async def _after_message_logic(mem: ChatService, sessions: dict, sid: str,
                               role: str, content: str) -> None:
    """消息落库 + 压缩判定 + 画像提取（纯逻辑，可注入测试）

    生产调用方先经 add_chat_session_message 把消息并入窗口，此处不负责并入；
    仅在未触发压缩且窗口尾部尚无该消息时补并（幂等）。触发压缩时窗口由
    compress 的结果整体替换——若调用方未预先并入（如直接调用本逻辑），
    新消息不会出现在压缩后的窗口中（消息已落库，摘要仍会覆盖上下文）。
    """
    await mem.save_message(sid, role, content)
    current_msgs = sessions[sid]["messages"]
    if mem.should_compress(len(current_msgs)):
        existing = sessions[sid].get("summary")
        compacted, new_summary = await mem.compress(current_msgs, existing_summary=existing)
        sessions[sid]["messages"] = compacted
        sessions[sid]["summary"] = new_summary
        if new_summary:
            profile = await mem.extract_profile(new_summary)
            if profile and any(profile.values()):
                await mem.save_profile(sid, profile)
    elif not current_msgs or current_msgs[-1] != {"role": role, "content": content}:
        sessions[sid]["messages"] = [*current_msgs, {"role": role, "content": content}]


def _after_message(sid: str, role: str, content: str) -> None:
    """流式 UI 包装：run_async_safe 桥接 + 读 session_state"""
    if not sid or sid not in st.session_state.get("chat_sessions", {}):
        return
    mem = ChatService()
    run_async_safe(_after_message_logic(mem, st.session_state["chat_sessions"],
                                        sid, role, content))


def _ensure_session() -> None:
    init_chat_sessions()
    if not st.session_state.get("active_session_id") or not st.session_state["chat_sessions"]:
        create_chat_session()


def _render_streaming_chat(prompt: str, history: list[dict]):
    """流式输出体验（机制同 V1：stream_sync + astream_events）"""
    from src.agents.graph import chat_stream, NODE_LABELS
    from src.utils.stream_bridge import stream_sync

    progress_ph, output_ph = render_streaming_placeholder()
    full_text = ""

    sid = st.session_state.get("active_session_id")
    chat_summary = None
    if sid:
        chat_summary = st.session_state["chat_sessions"].get(sid, {}).get("summary")

    try:
        for event in stream_sync(
            lambda: chat_stream(prompt, history[:-1] if len(history) > 1 else None,
                                summary=chat_summary)
        ):
            etype = event["type"]
            if etype == "progress":
                label = NODE_LABELS.get(event["node"], "")
                if label:
                    progress_ph.caption(label)
            elif etype == "clear":
                full_text = ""
                output_ph.empty()
            elif etype == "token":
                full_text += event["content"]
                render_streaming_cursor(output_ph, full_text)
            elif etype == "done":
                progress_ph.empty()
                response = event.get("response", "")
                output_ph.markdown(bubble_html("assistant", response or "抱歉，出错了。"),
                                   unsafe_allow_html=True)
                if not response:
                    response = "抱歉，出错了。"
                add_chat_session_message("assistant", response)
                _after_message(sid, "assistant", response)
            elif etype == "error":
                progress_ph.empty()
                error_msg = f"出错了: {event['message']}"
                st.error(error_msg)
                add_chat_session_message("assistant", error_msg)
                _after_message(sid, "assistant", error_msg)
                break
    except Exception as exc:
        progress_ph.empty()
        st.error(f"出错了: {exc}")
        add_chat_session_message("assistant", f"出错了: {exc}")
        _after_message(sid, "assistant", f"出错了: {exc}")


def _submit_prompt(prompt_text: str) -> None:
    """提交一条用户消息：入窗 + 持久化 + 即时气泡 + 流式回复

    只渲染新消息气泡——历史气泡已由 render_message_list(history) 渲染，
    重复渲染会造成双份；草稿清理由调用方（输入路径）负责。
    """
    add_chat_session_message("user", prompt_text)
    _after_message(st.session_state.get("active_session_id"), "user", prompt_text)
    render_message_list([{"role": "user", "content": prompt_text}])   # 只渲染新消息
    with st.container():
        _render_streaming_chat(prompt_text, get_active_messages())


def render_chat_panel() -> None:
    """聊天中心：图标栏(侧栏) + 会话列 + 聊天区"""
    _ensure_session()

    col_sessions, col_chat = st.columns([1, 4], gap="medium")
    with col_sessions:
        render_session_list()

    with col_chat:
        history = get_active_messages()

        # 空态引导
        if not history:
            st.markdown("### 你想问什么？")
            examples = ["黑神话悟空现在多少钱？", "推荐几个魂系游戏", "最近有什么游戏新闻？"]
            ex_cols = st.columns(len(examples))
            clicked = None
            for col, ex in zip(ex_cols, examples):
                with col:
                    if st.button(ex, key=f"ex_{ex[:4]}", use_container_width=True):
                        clicked = ex
            if clicked:
                # 点击直接发送并流式回复（同一 run，不 rerun；
                # 在示例列外调用以保持聊天空全宽渲染）
                _submit_prompt(clicked)
        else:
            render_message_list(history)

        # 输入区（V3: last_submitted 哨兵防误提交/防重复提交，永不 pop widget key；
        # 提交后文本保留在输入框——text_input 无法程序化清空，哨兵保证不会重复发送）
        render_quick_commands()
        draft = ui_state.get_panel_state("chat").get("draft", "")
        if draft and draft != ui_state.get_panel_state("chat").get("last_submitted", ""):
            # 胶囊草稿变更 → 写入 widget 初始值（pre-instantiation write）+ 标记为已知值，
            # 本 run 不触发提交；与 last_submitted 相等时跳过，避免回填覆盖用户已输入的文本
            st.session_state["chat_input_v2"] = draft
            ui_state.update_panel_state("chat", {"last_submitted": draft})
        prompt = st.text_input("输入问题...", key="chat_input_v2",
                               placeholder="输入问题，如：黑神话悟空现在多少钱？")
        if prompt and prompt != ui_state.get_panel_state("chat").get("last_submitted", ""):
            # 用户改动了内容并回车 → 真实提交；同时清空草稿，防止下次 run 回填旧模板
            ui_state.update_panel_state("chat", {"last_submitted": prompt, "draft": ""})
            _submit_prompt(prompt)