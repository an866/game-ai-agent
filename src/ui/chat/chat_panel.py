"""聊天中心面板 —— 三列布局编排 + 消息持久化流水线

迁移自 _pages/chat.py（D6：流式机制不变，渲染升级）。
数据流：session_state 会话 → ChatService 持久化 → chat_stream 流式。
"""

import time

import streamlit as st

from src.services.chat_service import ChatService
from src.ui import ui_state
from src.ui.session_state import (
    init_chat_sessions, create_chat_session, get_active_messages,
    add_chat_session_message, run_async_safe,
)
from src.ui.chat.message_list import (
    render_message_list, render_streaming_cursor,
    render_streaming_placeholder, render_user_message, assistant_markdown,
)
from src.ui.chat.session_list import render_session_list

# 流式 token 重绘节流（秒）。过密会让 Streamlit markdown 反复重排，出现「重影」
_STREAM_PAINT_INTERVAL = 0.15


def _sanitize_stream_md(text: str) -> str:
    """流式中间态：补全未闭合围栏，避免半截表格/代码块造成视觉叠影"""
    if not text:
        return text
    fence = text.count("```")
    if fence % 2 == 1:
        text += "\n```"
    return text


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
    """消息后处理：落库 fire-and-forget + 压缩同步（首 token 不被 MySQL 阻塞）

    落库只碰 DB，不读写 session_state，投递到共享 loop 即可；
    压缩会改写会话窗口，必须同步等待完成。
    """
    if not sid or sid not in st.session_state.get("chat_sessions", {}):
        return
    from src.utils.async_utils import submit_coro

    mem = ChatService()
    sessions = st.session_state["chat_sessions"]

    submit_coro(mem.save_message(sid, role, content))

    current_msgs = sessions[sid]["messages"]
    if not mem.should_compress(len(current_msgs)):
        return

    async def _compress() -> None:
        existing = sessions[sid].get("summary")
        compacted, new_summary = await mem.compress(current_msgs, existing_summary=existing)
        sessions[sid]["messages"] = compacted
        sessions[sid]["summary"] = new_summary
        if new_summary:
            profile = await mem.extract_profile(new_summary)
            if profile and any(profile.values()):
                await mem.save_profile(sid, profile)

    run_async_safe(_compress())


def _ensure_session() -> None:
    init_chat_sessions()
    if not st.session_state.get("active_session_id") or not st.session_state["chat_sessions"]:
        create_chat_session()


def _render_welcome() -> str | None:
    """DeepSeek 式空态：居中欢迎 + 建议问题。返回被点击的示例。"""
    st.markdown(
        """
        <div class="ds-welcome">
          <h1>有什么可以帮你的？</h1>
          <div class="ds-sub">游戏 AI 助手 · 查游戏 / 比价格 / 要推荐 / 看资讯</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    examples = [
        "黑神话悟空现在多少钱？",
        "推荐几个魂系游戏",
        "鸣潮最新活动",
        "原神是什么类型的游戏？",
    ]
    cols = st.columns(2, gap="small")
    for i, ex in enumerate(examples):
        with cols[i % 2]:
            if st.button(ex, key=f"ds_ex_{i}", use_container_width=True):
                return ex
    return None


def _render_streaming_chat(prompt: str, history: list[dict]):
    """流式输出：单一 output 占位，节流重绘；done 时 empty 后写终稿"""
    from src.agents.graph import chat_stream, NODE_LABELS
    from src.utils.stream_bridge import stream_sync

    progress_ph, output_ph = render_streaming_placeholder()
    full_text = ""
    last_paint = 0.0
    got_done = False

    sid = st.session_state.get("active_session_id")
    chat_summary = None
    if sid:
        chat_summary = st.session_state["chat_sessions"].get(sid, {}).get("summary")

    def _paint_stream(body: str) -> None:
        output_ph.empty()
        output_ph.markdown(assistant_markdown(body, with_cursor=True))

    try:
        for event in stream_sync(
            lambda: chat_stream(prompt, history[:-1] if len(history) > 1 else None,
                                summary=chat_summary)
        ):
            etype = event["type"]
            if etype == "progress":
                label = NODE_LABELS.get(event["node"], "")
                if label:
                    progress_ph.markdown(f'<div class="ds-progress">{label}</div>',
                                         unsafe_allow_html=True)
            elif etype == "clear":
                full_text = ""
                output_ph.empty()
            elif etype == "token":
                full_text += event["content"]
                now = time.monotonic()
                if now - last_paint >= _STREAM_PAINT_INTERVAL:
                    _paint_stream(_sanitize_stream_md(full_text))
                    last_paint = now
            elif etype == "done":
                got_done = True
                progress_ph.empty()
                response = event.get("response", "") or "抱歉，出错了。"
                output_ph.empty()
                output_ph.markdown(assistant_markdown(response))
                add_chat_session_message("assistant", response)
                _after_message(sid, "assistant", response)
            elif etype == "error":
                progress_ph.empty()
                output_ph.empty()
                error_msg = f"出错了: {event['message']}"
                st.error(error_msg)
                add_chat_session_message("assistant", error_msg)
                _after_message(sid, "assistant", error_msg)
                break
        if not got_done and full_text:
            # 无 done 时收尾，去掉光标
            output_ph.empty()
            output_ph.markdown(assistant_markdown(_sanitize_stream_md(full_text)))
    except Exception as exc:
        progress_ph.empty()
        output_ph.empty()
        st.error(f"出错了: {exc}")
        add_chat_session_message("assistant", f"出错了: {exc}")
        _after_message(sid, "assistant", f"出错了: {exc}")


def _submit_prompt(prompt_text: str) -> None:
    """提交一条用户消息：入窗 + 持久化 + 即时气泡 + 流式回复"""
    add_chat_session_message("user", prompt_text)
    _after_message(st.session_state.get("active_session_id"), "user", prompt_text)
    render_user_message(prompt_text)
    with st.container():
        _render_streaming_chat(prompt_text, get_active_messages())


def _note_submitted(sid: str | None, text: str) -> None:
    """按会话记录 last_submitted，避免跨会话误去重"""
    ui_state.update_panel_state("chat", {f"last_submitted:{sid or '_'}": text})


def _already_submitted(sid: str | None, text: str) -> bool:
    return ui_state.get_panel_state("chat").get(f"last_submitted:{sid or '_'}") == text


def _commit_user_message(prompt_text: str) -> None:
    """用户消息入窗 + 落库（不在此画气泡，避免 DOM 落到输入框下）"""
    add_chat_session_message("user", prompt_text)
    _after_message(st.session_state.get("active_session_id"), "user", prompt_text)


def render_chat_panel() -> None:
    """聊天中心：会话列 + DeepSeek 式主聊区

    DOM 顺序：历史 → （本轮新消息+流式）→ st.chat_input（沉底）。
    键盘提交用 pending+rerun：先入窗，下一轮在输入框上方渲染流式，
    避免 Streamlit 把新回复画到输入条下面。
    """
    _ensure_session()

    col_sessions, col_chat = st.columns([1, 4], gap="medium")
    with col_sessions:
        render_session_list()

    with col_chat:
        sid = st.session_state.get("active_session_id")
        pending = st.session_state.pop("_ds_pending_prompt", None)
        history = get_active_messages()
        picked = None

        # 用 empty 容器包住对话区，避免「欢迎页 + 流式」两套 DOM 同时在场
        body = st.empty()
        with body.container():
            if pending:
                # history 尾部已是本条 user；先画旧历史，再画本条 + 流式
                prior = history[:-1] if history else []
                render_message_list(prior)
                render_user_message(pending)
                _render_streaming_chat(pending, history)
            elif not history:
                picked = _render_welcome()
            else:
                render_message_list(history)

        # 建议卡：同一 run 在 chat_input 之前提交，气泡落在对话区
        if picked and not _already_submitted(sid, picked):
            _note_submitted(sid, picked)
            _submit_prompt(picked)

        prompt = st.chat_input(
            "输入问题，如：黑神话悟空现在多少钱？",
            key="chat_input_v2",
        )
        if prompt and not _already_submitted(sid, prompt):
            _note_submitted(sid, prompt)
            _commit_user_message(prompt)
            st.session_state["_ds_pending_prompt"] = prompt
            st.rerun()