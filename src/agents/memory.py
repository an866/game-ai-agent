"""对话记忆管理 —— 持久化 + Token 窗口压缩"""

import json
from datetime import datetime
from typing import Optional

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_openai import ChatOpenAI
from loguru import logger
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import get_settings
from src.data.database import async_session_factory
from src.data.models import ChatHistory

settings = get_settings()

# 摘要注入 LLM 用的 system prompt
COMPRESS_SYSTEM_PROMPT = (
    "你是一个对话摘要助手。请用一段话（不超过 3 句）总结以下对话的要点，"
    "只提取关键信息（如用户查询了什么游戏、获得了什么结果、表达了什么偏好），"
    "不要复述对话过程本身。用中文输出。"
)


def build_profile_text(profile: dict) -> str:
    """把结构化用户画像拼成提示词片段；无有效字段时返回空串"""
    parts = []
    if profile.get("favorite_genres"):
        parts.append(f"偏好类型: {profile['favorite_genres']}")
    if profile.get("favorite_games"):
        parts.append(f"喜欢的游戏: {profile['favorite_games']}")
    if profile.get("platforms"):
        parts.append(f"平台: {profile['platforms']}")
    if profile.get("budget_range"):
        parts.append(f"预算: {profile['budget_range']}")
    return "用户画像: " + "；".join(parts) + "。" if parts else ""


class ConversationMemory:
    """无状态记忆服务 —— 提供 DB 读写、压缩判定、LLM 摘要、上下文构建。

    消息 buffer 和摘要存储在 Streamlit st.session_state 中（调用方管理），
    本类仅提供纯方法，不持有任何实例状态。
    """

    PROFILE_EXTRACT_PROMPT = (
        "根据以下对话摘要，提取用户的游戏偏好，严格输出JSON格式，不要包含任何其他文字：\n"
        '{"favorite_genres":"","favorite_games":"","platforms":"","budget_range":""}\n'
        "只提取对话中明确提到的信息，不要推测。没有信息的字段留空字符串。\n"
        "对话摘要:\n{summary}"
    )

    def __init__(self):
        self._compress_llm: Optional[ChatOpenAI] = None

    # ── DB 读写 ──────────────────────────────────────────

    async def save_message(
        self,
        session_id: str,
        role: str,
        content: str,
        intent: Optional[str] = None,
    ) -> bool:
        """持久化一条消息到 MySQL。DB 不可用时返回 False 并 log warning。"""
        try:
            async with async_session_factory() as db:
                msg = ChatHistory(
                    session_id=session_id,
                    role=role,
                    content=content,
                    intent=intent,
                )
                db.add(msg)
                await db.commit()
            return True
        except Exception as exc:
            logger.warning(f"消息持久化失败 (session={session_id}): {exc}")
            return False

    async def load_recent(
        self, session_id: str, limit: int = 20
    ) -> list[dict]:
        """从 MySQL 加载指定会话的最近 N 条消息。DB 不可用时返回空列表。"""
        try:
            async with async_session_factory() as db:
                stmt = (
                    select(ChatHistory)
                    .where(ChatHistory.session_id == session_id)
                    .order_by(desc(ChatHistory.created_at))
                    .limit(limit)
                )
                result = await db.execute(stmt)
                rows = result.scalars().all()
            # 反转回时间升序（DB 是 desc 查的）
            rows = list(reversed(rows))
            return [
                {"role": r.role, "content": r.content}
                for r in rows
            ]
        except Exception as exc:
            logger.warning(f"消息加载失败 (session={session_id}): {exc}")
            return []

    # ── 压缩判定 ──────────────────────────────────────────

    def should_compress(
        self,
        count: int,
        max_messages: int | None = None,
        threshold: float | None = None,
    ) -> bool:
        """返回 True 表示当前消息数已达到压缩阈值。"""
        _max = max_messages if max_messages is not None else settings.memory_max_messages
        _threshold = threshold if threshold is not None else settings.memory_compress_threshold
        return count >= _max * _threshold

    # ── LLM 摘要 ──────────────────────────────────────────

    def _get_compress_llm(self) -> ChatOpenAI:
        """懒加载压缩用的 LLM 实例。"""
        if self._compress_llm is None:
            self._compress_llm = ChatOpenAI(
                model=settings.llm_model,
                api_key=settings.openai_api_key,
                base_url=settings.openai_base_url,
                temperature=0.3,
                max_tokens=200,
            )
        return self._compress_llm

    async def compress(
        self,
        messages: list[dict],
        existing_summary: Optional[str] = None,
        recent_keep: int | None = None,
    ) -> tuple[list[dict], str]:
        """压缩旧消息为增量摘要。

        Args:
            messages: 当前窗口全部消息 [{"role": ..., "content": ...}, ...]
            existing_summary: 已有的摘要文本（二次压缩时追加）
            recent_keep: 压缩后保留的最近消息数（默认取自 settings）

        Returns:
            (compacted_messages, new_summary):
              - compacted_messages: 保留的最近 recent_keep 条消息
              - new_summary: 增量摘要文本
        """
        _keep = recent_keep if recent_keep is not None else settings.memory_recent_keep

        if len(messages) <= _keep:
            return messages, existing_summary or ""

        # 取待压缩的旧消息
        overflow = messages[: len(messages) - _keep]
        recent = messages[len(messages) - _keep:]

        # 拼接旧消息文本
        old_text_parts = []
        for m in overflow:
            tag = "用户" if m["role"] == "user" else "助手"
            old_text_parts.append(f"[{tag}]: {m['content'][:300]}")
        old_text = "\n".join(old_text_parts)

        # 调用 LLM 生成摘要
        llm = self._get_compress_llm()
        prompt = f"{COMPRESS_SYSTEM_PROMPT}\n\n对话内容:\n{old_text}"
        try:
            response = await llm.ainvoke([HumanMessage(content=prompt)])
            new_summary = response.content.strip()
        except Exception as exc:
            logger.warning(f"LLM 摘要生成失败: {exc}")
            return messages, existing_summary or ""

        # 合并已有摘要
        if existing_summary:
            full_summary = f"{existing_summary}\n{new_summary}"
        else:
            full_summary = new_summary

        # 日志
        logger.info(
            f"[ConversationMemory] 触发压缩 | "
            f"压缩前消息数={len(messages)} | "
            f"压缩后消息数={len(recent)} | "
            f'摘要="{new_summary[:100]}"'
        )

        return recent, full_summary

    # ── 画像提取 ──────────────────────────────────────────

    async def extract_profile(self, summary: str) -> dict:
        """LLM 从摘要中提取游戏偏好 → {"favorite_genres": "动作,RPG", ...}"""
        if not summary:
            return {}
        llm = self._get_compress_llm()
        prompt = self.PROFILE_EXTRACT_PROMPT.format(summary=summary)
        try:
            response = await llm.ainvoke([HumanMessage(content=prompt)])
            text = response.content.strip()
            # Extract JSON (some models wrap in ```json ... ```)
            if "```" in text:
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
                text = text.strip()
            return json.loads(text)
        except Exception as exc:
            logger.warning(f"画像提取失败: {exc}")
            return {}

    async def save_profile(self, session_id: str, profile: dict) -> bool:
        """写入 user_preferences 表（upsert）"""
        if not profile:
            return False
        try:
            async with async_session_factory() as db:
                from src.data.models import UserPreference
                from sqlalchemy import update

                result = await db.execute(
                    select(UserPreference).where(UserPreference.session_id == session_id)
                )
                existing = result.scalar_one_or_none()
                if existing:
                    await db.execute(
                        update(UserPreference)
                        .where(UserPreference.session_id == session_id)
                        .values(
                            favorite_genres=profile.get("favorite_genres", ""),
                            favorite_games=profile.get("favorite_games", ""),
                            platforms=profile.get("platforms", ""),
                            budget_range=profile.get("budget_range", ""),
                        )
                    )
                else:
                    pref = UserPreference(
                        session_id=session_id,
                        favorite_genres=profile.get("favorite_genres", ""),
                        favorite_games=profile.get("favorite_games", ""),
                        platforms=profile.get("platforms", ""),
                        budget_range=profile.get("budget_range", ""),
                    )
                    db.add(pref)
                await db.commit()
            logger.info(f"[ConversationMemory] 画像已保存 (session={session_id}): {profile}")
            return True
        except Exception as exc:
            logger.warning(f"画像保存失败 (session={session_id}): {exc}")
            return False

    async def load_profile(self, session_id: str) -> dict | None:
        """从 user_preferences 读取最新画像"""
        try:
            async with async_session_factory() as db:
                from src.data.models import UserPreference

                result = await db.execute(
                    select(UserPreference)
                    .where(UserPreference.session_id == session_id)
                    .order_by(UserPreference.updated_at.desc())
                    .limit(1)
                )
                row = result.scalar_one_or_none()
                if row:
                    return {
                        "favorite_genres": row.favorite_genres or "",
                        "favorite_games": row.favorite_games or "",
                        "platforms": row.platforms or "",
                        "budget_range": row.budget_range or "",
                    }
            return None
        except Exception as exc:
            logger.warning(f"画像加载失败 (session={session_id}): {exc}")
            return None

    # ── 上下文构建 ──────────────────────────────────────────

    def get_context(
        self,
        messages: list[dict],
        summary: Optional[str] = None,
    ) -> list[dict]:
        """构建注入 LLM 的上下文消息列表。

        如有摘要 → [{"role": "system", "content": summary}] + messages
        无摘要 → messages 原样返回
        """
        if summary:
            return [{"role": "system", "content": summary}] + messages
        return messages
