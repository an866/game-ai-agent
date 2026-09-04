"""src.llm 工厂测试 —— 角色温度表、单例、覆盖参数"""

import pytest

from src.llm import ROLE_TEMPERATURES, ROLE_STREAMING, clear_llm_cache, get_llm
from config.settings import settings_override


@pytest.fixture(autouse=True)
def _clean():
    # 测试不依赖用户 .env：固定 key/model/reasoning ——
    # 注意 langchain 按模型名前缀(gpt-5/o*系列)自动判定推理模型并强制 temperature=None
    clear_llm_cache()
    with settings_override(openai_api_key="test-key", llm_reasoning_effort="",
                           llm_model="gpt-4o-mini"):
        yield
    clear_llm_cache()


class TestRoles:
    def test_temperature_table_complete(self):
        """8 个角色都应登记温度（与 agents.yaml 删除前一致）"""
        assert ROLE_TEMPERATURES["router"] == 0.1
        assert ROLE_TEMPERATURES["query"] == 0.3
        assert ROLE_TEMPERATURES["price"] == 0.3
        assert ROLE_TEMPERATURES["recommend"] == 0.7
        assert ROLE_TEMPERATURES["news"] == 0.3
        assert ROLE_TEMPERATURES["general"] == 0.5
        assert ROLE_TEMPERATURES["compress"] == 0.3
        assert ROLE_TEMPERATURES["profile_extract"] == 0.0

    def test_streaming_only_general_and_recommend(self):
        assert ROLE_STREAMING.get("general") is True
        assert ROLE_STREAMING.get("recommend") is True
        assert ROLE_STREAMING.get("query", False) is False

    def test_role_defaults_applied(self):
        llm = get_llm("query")
        assert llm.temperature == 0.3
        assert llm.streaming is False

    def test_explicit_overrides(self):
        llm = get_llm("query", temperature=0.7, streaming=True)
        assert llm.temperature == 0.7
        assert llm.streaming is True

    def test_compress_max_tokens(self):
        llm = get_llm("compress", max_tokens=200)
        assert llm.max_tokens == 200

    def test_reasoning_effort_passthrough(self):
        """settings.llm_reasoning_effort 非空时作为显式参数传入"""
        with settings_override(llm_reasoning_effort="xhigh"):
            clear_llm_cache()
            llm = get_llm("query")
        assert llm.reasoning_effort == "xhigh"
        # 注意：temperature 是否被强制 None 由模型名决定（gpt-5/o* 前缀），
        # 与 reasoning_effort 参数无关；此处不对此做断言

    def test_reasoning_effort_empty_no_kwargs(self):
        """留空时不携带 reasoning_effort（默认行为不变）"""
        llm = get_llm("query")
        assert not getattr(llm, "reasoning_effort", None)


class TestCaching:
    def test_same_params_same_instance(self):
        assert get_llm("router") is get_llm("router")

    def test_different_role_different_instance(self):
        assert get_llm("router") is not get_llm("query")

    def test_clear_rebuilds(self):
        first = get_llm("router")
        clear_llm_cache()
        assert get_llm("router") is not first

    def test_settings_change_invalidates(self):
        """settings 变更后应拿到新配置的 LLM（key 含 api_key/model）"""
        llm1 = get_llm("router")
        with settings_override(openai_base_url="http://localhost:11434/v1"):
            clear_llm_cache()
            llm2 = get_llm("router")
        assert llm2 is not llm1
        assert "localhost" in llm2.openai_api_base