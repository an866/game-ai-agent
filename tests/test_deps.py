"""src.deps 组合根与 settings 可测化测试"""

import pytest

import src.deps as deps
from config.settings import get_settings, reset_settings, settings_override


@pytest.fixture(autouse=True)
def _clean_deps():
    deps.reset_all()
    yield
    deps.reset_all()


class TestDeps:
    def test_getters_register_defaults(self):
        # 首次 get 即注册全部生产工厂（不抛异常即可）
        assert deps.get_session_factory() is not None
        assert deps.get_engine() is not None
        # 同 key 幂等（单例）
        assert deps.get_engine() is deps.get_engine()

    def test_override_replaces_instance(self):
        assert deps.get_session_factory() is not None
        fake = object()
        with deps.override("session_factory", fake):
            assert deps.get_session_factory() is fake
        # 退出后还原
        assert deps.get_session_factory() is not fake

    def test_override_resets_cached_instance(self):
        """override 前已构造的实例不应泄漏到 with 块内"""
        original = deps.get_session_factory()
        fake = object()
        with deps.override("session_factory", fake):
            assert deps.get_session_factory() is fake
            assert deps.get_session_factory() is not original
        # with 块外恢复为重新构造（非旧对象——每次 reset 后工厂重跑）
        outside = deps.get_session_factory()
        assert outside is not fake

    def test_reset_all_clears_instances(self):
        first = deps.get_engine()
        deps.reset_all()
        second = deps.get_engine()
        assert first is not second


class TestSettingsOverride:
    def test_settings_override_roundtrip(self):
        get_settings()  # 固话初始配置
        with settings_override(redis_db=7):
            assert get_settings().redis_db == 7
        assert get_settings().redis_db == 0

    def test_settings_override_restores_env(self, monkeypatch):
        monkeypatch.setenv("REDIS_DB", "3")
        reset_settings()
        assert get_settings().redis_db == 3
        with settings_override(redis_db=9):
            assert get_settings().redis_db == 9
        assert get_settings().redis_db == 3  # 环境变量原值保留