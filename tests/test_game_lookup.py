"""game_lookup 降级：RAWG 不可用时 Steam/联网仍能出结果"""

import pytest

from src.services import game_lookup


class _BoomRAWG:
    async def _arun(self, *a, **k):
        raise RuntimeError("RAWG_API_KEY 未配置")


class _EmptySteam:
    async def _arun(self, query, **k):
        return []


class _FakeSteam:
    async def _arun(self, query, **k):
        return [{"appid": 1, "name": f"{query}-steam", "type": "steam"}]


@pytest.mark.asyncio
async def test_search_games_falls_back_to_steam(monkeypatch):
    import src.tools.rawg as rawg_mod
    import src.tools.steam_api as steam_mod
    monkeypatch.setattr(rawg_mod, "RAWGGameSearchTool", lambda: _BoomRAWG())
    monkeypatch.setattr(steam_mod, "SteamSearchTool", lambda: _FakeSteam())
    results = await game_lookup.search_games("测试游戏")
    assert results and results[0]["name"] == "测试游戏-steam"
    assert results[0]["source"] == "steam"


@pytest.mark.asyncio
async def test_recommend_falls_back_to_web(monkeypatch):
    import src.tools.rawg as rawg_mod
    import src.tools.steam_api as steam_mod
    import src.tools.web_search as web_mod

    class _Boom:
        async def _arun(self, *a, **k):
            raise RuntimeError("no rawg")

    async def _fake_web(q, max_results=5):
        return [
            {"title": "Celeste", "snippet": "fun platformer", "url": ""},
            {"title": "10 Best Games Like Hades", "snippet": "list", "url": ""},
        ]

    monkeypatch.setattr(rawg_mod, "RAWGGameSearchTool", lambda: _Boom())
    monkeypatch.setattr(rawg_mod, "RAWGGameRecommendationsTool", lambda: _Boom())
    monkeypatch.setattr(rawg_mod, "RAWGGameDetailTool", lambda: _Boom())
    monkeypatch.setattr(steam_mod, "SteamSearchTool", lambda: _EmptySteam())
    monkeypatch.setattr(web_mod, "search_web", _fake_web)

    recs, seed = await game_lookup.recommend_games("Hades")
    assert recs and recs[0]["name"] == "Celeste"
    assert recs[0]["source"] == "web"
    assert all("Best Games" not in r["name"] for r in recs)


def test_expand_queries_cn_alias():
    assert "Hollow Knight" in game_lookup.expand_queries("空洞骑士")
    assert not any("Silksong" in q for q in game_lookup.expand_queries("空洞骑士"))
    assert any("Silksong" in q for q in game_lookup.expand_queries("丝之歌"))
