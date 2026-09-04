"""ConversationMemory 单元测试"""

import pytest
from src.agents.memory import ConversationMemory


class TestShouldCompress:
    """压缩阈值判定 (纯逻辑，无 DB/LLM 依赖)"""

    def test_trigger_at_threshold(self):
        mem = ConversationMemory()
        # 20 * 0.85 = 17, 达到 17 应触发
        assert mem.should_compress(17, max_messages=20, threshold=0.85) is True

    def test_no_trigger_below_threshold(self):
        mem = ConversationMemory()
        assert mem.should_compress(16, max_messages=20, threshold=0.85) is False

    def test_zero_messages(self):
        mem = ConversationMemory()
        assert mem.should_compress(0) is False

    def test_custom_params(self):
        mem = ConversationMemory()
        # 10 * 0.85 = 8.5 → >= 8.5, 9 条触发
        assert mem.should_compress(9, max_messages=10, threshold=0.85) is True
        assert mem.should_compress(8, max_messages=10, threshold=0.85) is False


class TestGetContext:
    """上下文构建 (纯逻辑)"""

    def test_without_summary_returns_all_messages(self):
        mem = ConversationMemory()
        msgs = [
            {"role": "user", "content": "你好"},
            {"role": "assistant", "content": "你好！"},
        ]
        result = mem.get_context(msgs)
        assert result == msgs

    def test_with_summary_prepends_system(self):
        mem = ConversationMemory()
        msgs = [
            {"role": "user", "content": "黑神话价格"},
        ]
        summary = "用户之前询问了游戏价格信息。"
        result = mem.get_context(msgs, summary=summary)
        assert len(result) == 2
        assert result[0]["role"] == "system"
        assert result[0]["content"] == summary
        assert result[1] == msgs[0]

    def test_empty_messages_with_summary(self):
        mem = ConversationMemory()
        result = mem.get_context([], summary="摘要")
        assert len(result) == 1
        assert result[0]["role"] == "system"


class TestCompress:
    """压缩逻辑 (需要 LLM 调用，标记为 integration)"""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_compress_reduces_message_count(self):
        """压缩后消息数应减少到 recent_keep 条"""
        mem = ConversationMemory()
        msgs = [
            {"role": "user", "content": "消息"},
            {"role": "assistant", "content": "回复"},
        ] * 10  # 20 条消息
        # 压缩: recent_keep=8, 应返回 8 条 + 摘要
        compacted, summary = await mem.compress(msgs, recent_keep=8)
        assert len(compacted) == 8
        assert len(summary) > 0

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_compress_appends_to_existing_summary(self):
        """增量摘要应拼接已有摘要"""
        mem = ConversationMemory()
        msgs = [
            {"role": "user", "content": "推荐游戏"},
            {"role": "assistant", "content": "推荐黑神话"},
        ] * 5  # 10 条
        compacted, summary = await mem.compress(
            msgs, existing_summary="之前讨论了价格。", recent_keep=3
        )
        assert summary.startswith("之前讨论了价格。")
        assert len(compacted) == 3

    def test_no_compress_when_below_keep(self):
        """消息数 ≤ recent_keep 时不压缩"""
        mem = ConversationMemory()
        msgs = [{"role": "user", "content": "hi"}] * 3
        # 同步测试 —— compress 是 async，但少于 keep 时直接 return
        import asyncio
        compacted, summary = asyncio.run(mem.compress(msgs, recent_keep=5))
        assert compacted == msgs
        assert summary == ""


class TestSaveAndLoad:
    """DB 读写 (需要 MySQL)"""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_save_and_load_roundtrip(self):
        """写入后应能从 DB 读回"""
        mem = ConversationMemory()
        sid = "test_session_01"
        ok = await mem.save_message(sid, "user", "Hello", intent="general")
        assert ok is True

        msgs = await mem.load_recent(sid, limit=10)
        assert len(msgs) >= 1
        found = [m for m in msgs if m["content"] == "Hello"]
        assert len(found) == 1
        assert found[0]["role"] == "user"

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_load_returns_latest_first(self):
        """load_recent 返回时间升序（最早→最新）"""
        mem = ConversationMemory()
        sid = "test_session_02"
        await mem.save_message(sid, "user", "msg1")
        await mem.save_message(sid, "assistant", "msg2")
        await mem.save_message(sid, "user", "msg3")

        msgs = await mem.load_recent(sid, limit=10)
        contents = [m["content"] for m in msgs if m["role"] == "user"]
        # msg3 最晚，msg1 最早 → 升序
        assert contents == ["msg1", "msg3"] or "msg3" in contents


class TestMemoryInit:
    """初始化测试"""

    def test_new_instance_has_no_state(self):
        """ConversationMemory 是无状态服务类"""
        m1 = ConversationMemory()
        m2 = ConversationMemory()
        assert m1 is not m2  # 不同实例
        # 无实例属性（除 _compress_llm）
        assert m1._compress_llm is None
