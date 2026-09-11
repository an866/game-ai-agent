"""工具调用签名回归 —— agent 框架可能传入多余 kwargs（如 args）不得炸"""

import pytest
from pydantic import BaseModel

from src.tools.cheapshark import CheapSharkDealsTool
from src.tools.isthereanydeal import ITADLookupTool, ITADPricesTool
from src.tools.steam_api import SteamDetailTool, SteamSearchTool


class _NoRedis:
    async def get(self, key):
        return None

    async def setex(self, key, ttl, value):
        return True


@pytest.fixture
def no_redis(monkeypatch):
    async def _get():
        return _NoRedis()

    monkeypatch.setattr("src.tools.base.get_redis", _get)


class TestArgsSchema:
    def test_cheapshark_has_args_schema(self):
        schema = CheapSharkDealsTool().args_schema
        assert issubclass(schema, BaseModel)
        assert "title" in schema.model_fields

    def test_ainvoke_with_spurious_args_key(self, no_redis, monkeypatch):
        """P1-001 回归：ainvoke 带 args 键时不应 TypeError"""
        tool = CheapSharkDealsTool()

        async def _fake_search(title, on_sale=True, upper_price=None):
            return [{"title": title, "sale_price": 1.0}]

        monkeypatch.setattr(tool, "_search_deals", _fake_search)

        import asyncio

        result = asyncio.run(tool.ainvoke({"title": "黑神话", "args": []}))
        assert result[0]["title"] == "黑神话"

    def test_ainvoke_args_list_without_title(self, no_redis, monkeypatch):
        """LLM 可能只传 args:['游戏名'] —— 应解析为 title"""
        tool = CheapSharkDealsTool()

        async def _fake_search(title, on_sale=True, upper_price=None):
            return [{"title": title}]

        monkeypatch.setattr(tool, "_search_deals", _fake_search)

        import asyncio

        result = asyncio.run(tool.ainvoke({"args": ["Black Myth: Wukong"]}))
        assert result[0]["title"] == "Black Myth: Wukong"

    def test_itad_lookup_args_list_without_title(self, no_redis, monkeypatch):
        """P1-001b：ITADLookupTool 缺 title 时同上"""
        tool = ITADLookupTool()

        async def _fake_lookup(title):
            return [{"title": title, "plain": "x"}]

        monkeypatch.setattr(tool, "_lookup", _fake_lookup)

        import asyncio

        result = asyncio.run(tool.ainvoke({"args": ["Black Myth: Wukong"]}))
        assert result[0]["title"] == "Black Myth: Wukong"

    def test_itad_prices_args_list(self, no_redis, monkeypatch):
        tool = ITADPricesTool()

        async def _fake(game_plain):
            return {"game": game_plain, "prices": []}

        monkeypatch.setattr(tool, "_get_prices", _fake)

        import asyncio

        result = asyncio.run(tool.ainvoke({"args": ["black-myth-wukong"]}))
        assert result["game"] == "black-myth-wukong"

    def test_steam_tools_absorb_extra_kwargs(self, no_redis, monkeypatch):
        search = SteamSearchTool()
        detail = SteamDetailTool()

        async def _s(q):
            return []

        async def _d(appid):
            return {"appid": appid}

        monkeypatch.setattr(search, "_search", _s)
        monkeypatch.setattr(detail, "_get_details", _d)

        import asyncio

        assert asyncio.run(search.ainvoke({"query": "x", "args": []})) == []
        assert asyncio.run(detail.ainvoke({"appid": 1, "args": []})) == {"appid": 1}

    def test_steam_detail_args_list_without_appid(self, no_redis, monkeypatch):
        detail = SteamDetailTool()

        async def _d(appid):
            return {"appid": appid}

        monkeypatch.setattr(detail, "_get_details", _d)

        import asyncio

        assert asyncio.run(detail.ainvoke({"args": [730]})) == {"appid": 730}
