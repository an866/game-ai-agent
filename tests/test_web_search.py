"""search_web 搜索链测试 —— DDG 成功 / 回退 Tavily / 双失败降级"""

import pytest

from src.tools import web_search as ws


class FakeResponse:
    def __init__(self, text, raise_error=None):
        self.text = text
        self._error = raise_error

    def raise_for_status(self):
        if self._error:
            raise self._error


class FakeClient:
    def __init__(self, responses):
        self.responses = list(responses)

    async def get(self, url, params=None):
        resp = self.responses.pop(0)
        if isinstance(resp, Exception):
            raise resp
        return resp


DDG_HTML = """<html>
  <div class="result">
    <a class="result__a" href="https://example.com/game">Example Game</a>
    <span class="result__snippet">A great game</span>
  </div>
</html>"""


@pytest.mark.asyncio
async def test_ddg_success_returns_results(monkeypatch):
    monkeypatch.setattr(ws, "get_http_client", lambda: FakeClient([FakeResponse(DDG_HTML)]))
    results = await ws.search_web("黑神话", max_results=5)
    assert results[0]["title"] == "Example Game"
    assert results[0]["url"].startswith("https://example.com")


@pytest.mark.asyncio
async def test_ddg_empty_triggers_tavily_fallback(monkeypatch):
    """DDG 空结果（验证页）→ Tavily 回退"""
    calls = {"tavily": 0}

    async def fake_tavily(query, max_results=5):
        calls["tavily"] += 1
        return [{"title": "T1", "snippet": "s", "url": "https://t.example"}]

    monkeypatch.setattr(ws, "get_http_client", lambda: FakeClient([FakeResponse("<html>no results</html>")]))
    monkeypatch.setattr(ws, "_search_tavily", fake_tavily)

    results = await ws.search_web("原神")
    assert calls["tavily"] == 1
    assert results[0]["title"] == "T1"


@pytest.mark.asyncio
async def test_ddg_http_error_triggers_tavily(monkeypatch):
    import httpx

    async def fake_tavily(query, max_results=5):
        return [{"title": "T2", "snippet": "s", "url": "https://t2.example"}]

    monkeypatch.setattr(ws, "get_http_client", lambda: FakeClient([httpx.HTTPStatusError("403")]))
    monkeypatch.setattr(ws, "_search_tavily", fake_tavily)

    results = await ws.search_web("黑神话")
    assert results[0]["title"] == "T2"


@pytest.mark.asyncio
async def test_both_fail_returns_graceful_message(monkeypatch):
    """DDG 与 Tavily 全部失败 → 降级文案"""
    async def fake_tavily(query, max_results=5):
        raise RuntimeError("tavily down")

    monkeypatch.setattr(ws, "get_http_client", lambda: FakeClient([RuntimeError("ddg down")]))
    monkeypatch.setattr(ws, "_search_tavily", fake_tavily)

    results = await ws.search_web("测试")
    assert results[0]["title"] == "搜索失败"


@pytest.mark.asyncio
async def test_tavily_without_key_raises(monkeypatch):
    from config.settings import settings_override

    with settings_override(tavily_api_key=""):
        with pytest.raises(ValueError):
            await ws._search_tavily("q")