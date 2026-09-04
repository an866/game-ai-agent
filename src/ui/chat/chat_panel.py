"""聊天中心面板 —— 三列布局编排 + 消息持久化流水线

迁移自 _pages/chat.py（D6：流式机制不变，渲染升级）。
数据流：session_state 会话 → ChatService 持久化 → chat_stream 流式。
"""

import streamlit as st

from src.services.chat_service import ChatService
from src.ui import ui_state
from src.ui.session_state import (
    init_chat_sessions, create_chat_session, get_active_messages,
    add_chat_session_message, switch_session, run_async_safe,
)
from src.ui.chat.message_list import (
    bubble_html, render_message_list, render_streaming_cursor,
    render_streaming_placeholder,
)
from src.ui.chat.quick_commands import render_quick_commands
from src.ui.chat.session_list import render_session_list


async def _after_message_logic(mem: ChatService, sessions: dict, sid: str,
                               role: str, content: str) -> None:
    """消息落库 + 窗口维护 + 压缩判定 + 画像提取（纯逻辑，可注入测试）

    调用方（UI）会先经 add_chat_session_message 把消息并入窗口；
    此处仅在未触发压缩且窗口尾部尚无该消息时补并（幂等），
    保证直接调用本逻辑（如测试）窗口也包含新消息。
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
    """提交提示词：并入窗口 + 落库 + 立即渲染用户气泡 + 流式回复

    输入框与空态示例按钮共用；草稿清理由调用方（输入路径）负责。
    """
    add_chat_session_message("user", prompt_text)
    _after_message(st.session_state.get("active_session_id"), "user", prompt_text)
    render_message_list(get_active_messages())      # 立即显示用户消息
    with st.container():
        _render_streaming_chat(prompt_text, get_active_messages())


def render_chat_panel() -> None:
    """聊天中心：会话列 + 聊天区（X 三列式）"""
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

        # 快捷指令 + 输入（快捷指令胶囊写入 draft → 输入框回填；
        # 提交后无 draft 时重建输入框，模拟 chat_input 提交即清空）
        render_quick_commands()
        draft = ui_state.get_panel_state("chat").get("draft", "")
        if draft:
            st.session_state["chat_input_v2"] = draft
        else:
            st.session_state.pop("chat_input_v2", None)
        prompt = st.text_input("输入问题...", key="chat_input_v2", value=draft,
                               label_visibility="collapsed", placeholder="输入问题...")
        if prompt:
            if draft:
                ui_state.set_panel_state("chat", {})
            _submit_prompt(prompt)