"""chat_panel 测试 —— 消息持久化流水线（迁移自 _pages/chat.py 的 _after_message）"""

import asyncio

from src.ui.chat import chat_panel


class FakeService:
    def __init__(self):
        self.saved = []

    async def save_message(self, sid, role, content, intent=None):
        self.saved.append((sid, role, content))
        return True

    def should_compress(self, count, **kw):
        return count >= 3

    async def compress(self, messages, existing_summary=None, recent_keep=None):
        return messages[2:], "摘要"

    async def extract_profile(self, summary):
        return {"favorite_genres": "RPG"}

    async def save_profile(self, sid, profile):
        return True


def test_after_message_saves_and_compresses():
    svc = FakeService()
    sessions = {"s1": {"messages": [{"role": "u", "content": "1"}] * 4, "summary": None}, "active": "s1"}

    async def scenario():
        await chat_panel._after_message_logic(svc, sessions, "s1", "user", "新消息")

    asyncio.run(scenario())
    assert svc.saved[-1] == ("s1", "user", "新消息")
    assert len(sessions["s1"]["messages"]) == 2          # 压缩后保留 recent 部分
    assert sessions["s1"]["summary"] == "摘要"


def test_after_message_single_no_compress():
    svc = FakeService()
    sessions = {"s1": {"messages": [{"role": "u", "content": "1"}], "summary": None}, "active": "s1"}

    async def scenario():
        await chat_panel._after_message_logic(svc, sessions, "s1", "assistant", "回复")

    asyncio.run(scenario())
    assert len(sessions["s1"]["messages"]) == 2
    assert sessions["s1"]["summary"] is None


def test_after_message_no_double_append_when_pre_added():
    svc = FakeService()
    # 生产流程：UI 先 add_chat_session_message 再调 _after_message_logic —— 窗口末尾即新消息
    sessions = {"s1": {"messages": [
        {"role": "user", "content": "老消息"},
        {"role": "user", "content": "新消息"},
    ], "summary": None}, "active": "s1"}

    async def scenario():
        await chat_panel._after_message_logic(svc, sessions, "s1", "user", "新消息")

    asyncio.run(scenario())
    assert len(sessions["s1"]["messages"]) == 2  # 幂等：不再追加
    assert svc.saved[-1] == ("s1", "user", "新消息")


def test_after_message_no_append_when_compress_no_pre_add():
    svc = FakeService()
    sessions = {"s1": {"messages": [{"role": "u", "content": "1"}] * 4, "summary": None}, "active": "s1"}

    async def scenario():
        await chat_panel._after_message_logic(svc, sessions, "s1", "user", "新消息")

    asyncio.run(scenario())
    # 压缩路径：窗口 = 原 4 条截断为 2 条（不含"新消息"），消息已落库
    assert svc.saved[-1] == ("s1", "user", "新消息")
    assert len(sessions["s1"]["messages"]) == 2