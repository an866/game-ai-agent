"""路由映射单源测试 —— INTENT_ROUTE 与节点集合/标签一致"""

from src.agents.graph import INTENT_ROUTE, NODE_LABELS, route_by_intent


class TestIntentRoute:
    def test_all_intents_map_to_existing_nodes(self):
        # 条件边目标必须是有实际实现的节点（router/aggregator 之外的中间节点）
        assert set(INTENT_ROUTE.values()) == {"query", "price", "recommend", "news", "general_chat"}

    def test_route_by_intent_uses_same_map(self):
        assert route_by_intent({"intent": "game_query"}) == "query"
        assert route_by_intent({"intent": "price_check"}) == "price"
        assert route_by_intent({"intent": "recommend"}) == "recommend"
        assert route_by_intent({"intent": "news"}) == "news"
        assert route_by_intent({"intent": "general"}) == "general_chat"

    def test_unknown_intent_falls_back_to_general(self):
        assert route_by_intent({"intent": "unknown_thing"}) == "general_chat"
        assert route_by_intent({}) == "general_chat"

    def test_node_labels_cover_all_route_targets(self):
        """流式进度的 NODE_LABELS 必须覆盖全部路由目标（防漏标签）"""
        assert set(INTENT_ROUTE.values()).issubset(set(NODE_LABELS))

    def test_router_has_agents_config_import(self):
        """build_router_chain 在函数体内使用 get_agents_config —— 防 C13 重写丢 import 回归"""
        from src.agents.router import get_agents_config as router_imported
        from config.loader import get_agents_config
        assert router_imported is get_agents_config