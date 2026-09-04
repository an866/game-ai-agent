"""ChatService 单元测试"""

from types import SimpleNamespace

import pytest
from src.services.chat_service import ChatService, build_profile_text

# ── fakes：内存替代 SQLAlchemy session 与真实 LLM ──

class _DummySession:
    """async context manager 占位 session（fake repo 不使用它）"""
    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def commit(self):
        return None

    async def rollback(self):
        return None


class _DummySessionFactory:
    def __call__(self):
        return lambda: _DummySession()


class FakeChatRepo:
    records: list[dict] = []

    def __init__(self, session=None):
        self.session = session  # 忽略真实 session

    async def add(self, session_id, role, content, intent=None):
        FakeChatRepo.records.append({
            "session_id": session_id, "role": role, "content": content,
        })

    async def get_recent(self, session_id, limit=50):
        rows = [r for r in FakeChatRepo.records if r["session_id"] == session_id]
        # 倒序返回（与真实 repo 一致），并伪装成 ORM 对象（service 读 .role/.content）
        return [
            SimpleNamespace(role=r["role"], content=r["content"])
            for r in rows[-limit:][::-1]
        ]


class FakePrefRepo:
    stored: dict = {}

    def __init__(self, session=None):
        self.session = session  # 忽略真实 session

    async def upsert_profile(self, session_id, profile):
        FakePrefRepo.stored[session_id] = dict(profile)

    async def get_profile(self, session_id):
        return FakePrefRepo.stored.get(session_id)


class FakeLLM:
    """假 LLM —— 返回固定内容，让压缩/画像用例无需真实 API"""

    def __init__(self, content="测试摘要内容"):
        self.content = content

    async def ainvoke(self, messages):
        return SimpleNamespace(content=self.content)


def _fake_llm_factory(role, **kwargs):
    return FakeLLM()


@pytest.fixture(autouse=True)
def _fake_repos(monkeypatch):
    FakeChatRepo.records = []
    FakePrefRepo.stored = {}
    monkeypatch.setattr("src.services.chat_service.ChatHistoryRepository", FakeChatRepo)
    monkeypatch.setattr("src.services.chat_service.UserPreferenceRepository", FakePrefRepo)
    yield


def _service():
    return ChatService(
        session_factory=_DummySessionFactory(),
        llm_factory=_fake_llm_factory,
    )


class TestShouldCompress:
    """压缩阈值判定 (纯逻辑，无 DB/LLM 依赖)"""

    def test_trigger_at_threshold(self):
        mem = _service()
        # 20 * 0.85 = 17, 达到 17 应触发
        assert mem.should_compress(17, max_messages=20, threshold=0.85) is True

    def test_no_trigger_below_threshold(self):
        mem = _service()
        assert mem.should_compress(16, max_messages=20, threshold=0.85) is False

    def test_zero_messages(self):
        mem = _service()
        assert mem.should_compress(0) is False

    def test_custom_params(self):
        mem = _service()
        # 10 * 0.85 = 8.5 → >= 8.5, 9 条触发
        assert mem.should_compress(9, max_messages=10, threshold=0.85) is True
        assert mem.should_compress(8, max_messages=10, threshold=0.85) is False


class TestGetContext:
    """上下文构建 (纯逻辑)"""

    def test_without_summary_returns_all_messages(self):
        mem = _service()
        msgs = [
            {"role": "user", "content": "你好"},
            {"role": "assistant", "content": "你好！"},
        ]
        result = mem.get_context(msgs)
        assert result == msgs

    def test_with_summary_prepends_system(self):
        mem = _service()
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
        mem = _service()
        result = mem.get_context([], summary="摘要")
        assert len(result) == 1
        assert result[0]["role"] == "system"


class TestCompress:
    """压缩逻辑 (LLM 用例标记为 integration，需真实 API key)"""

    @pytest.mark.asyncio
    async def test_compress_reduces_message_count(self):
        """压缩后消息数应减少到 recent_keep 条"""
        mem = _service()
        msgs = [
            {"role": "user", "content": "消息"},
            {"role": "assistant", "content": "回复"},
        ] * 10  # 20 条消息
        # 压缩: recent_keep=8, 应返回 8 条 + 摘要
        compacted, summary = await mem.compress(msgs, recent_keep=8)
        assert len(compacted) == 8
        assert len(summary) > 0

    @pytest.mark.asyncio
    async def test_compress_appends_to_existing_summary(self):
        """增量摘要应拼接已有摘要"""
        mem = _service()
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
        mem = _service()
        msgs = [{"role": "user", "content": "hi"}] * 3
        # 同步测试 —— compress 是 async，但少于 keep 时直接 return
        import asyncio
        compacted, summary = asyncio.run(mem.compress(msgs, recent_keep=5))
        assert compacted == msgs
        assert summary == ""


class TestSaveAndLoad:
    """DB 读写（fake repository）"""

    @pytest.mark.asyncio
    async def test_save_and_load_roundtrip(self):
        """写入后应能从 repo 读回"""
        mem = _service()
        sid = "test_session_01"
        ok = await mem.save_message(sid, "user", "Hello", intent="general")
        assert ok is True

        msgs = await mem.load_recent(sid, limit=10)
        assert len(msgs) >= 1
        found = [m for m in msgs if m["content"] == "Hello"]
        assert len(found) == 1
        assert found[0]["role"] == "user"

    @pytest.mark.asyncio
    async def test_load_returns_latest_first(self):
        """load_recent 返回时间升序（最早→最新）"""
        mem = _service()
        sid = "test_session_02"
        await mem.save_message(sid, "user", "msg1")
        await mem.save_message(sid, "assistant", "msg2")
        await mem.save_message(sid, "user", "msg3")

        msgs = await mem.load_recent(sid, limit=10)
        contents = [m["content"] for m in msgs]
        assert contents == ["msg1", "msg2", "msg3"]

    @pytest.mark.asyncio
    async def test_profile_roundtrip(self):
        """画像 upsert + 读取"""
        mem = _service()
        sid = "test_session_03"
        assert await mem.load_profile(sid) is None
        ok = await mem.save_profile(sid, {"favorite_genres": "RPG", "favorite_games": "黑神话"})
        assert ok is True
        profile = await mem.load_profile(sid)
        assert profile["favorite_genres"] == "RPG"
        # 二次 upsert 覆盖
        await mem.save_profile(sid, {"favorite_genres": "动作", "favorite_games": "原神"})
        profile = await mem.load_profile(sid)
        assert profile["favorite_genres"] == "动作"


class TestProfileText:
    """画像拼接纯函数"""

    def test_empty_profile(self):
        assert build_profile_text({}) == ""

    def test_single_field(self):
        assert build_profile_text({"favorite_genres": "RPG"}) == "用户画像: 偏好类型: RPG。"

    def test_multiple_fields(self):
        result = build_profile_text({"favorite_genres": "RPG", "budget_range": "100-200"})
        assert result == "用户画像: 偏好类型: RPG；预算: 100-200。"


class TestServiceStateless:
    """服务无状态性"""
    def test_new_instance_has_no_db_state(self):
        m1 = ChatService()
        m2 = ChatService()
        assert m1 is not m2  # 不同实例
        assert m1._compress_llm is None