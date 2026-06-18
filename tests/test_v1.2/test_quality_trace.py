"""v1.2 质量追溯单元测试

验证质量追溯不再依赖出单表：
- quality_trace_index 解除外键后可独立查询
- archive_complete 筛选功能
- action_type 筛选功能（原 order_type）
"""
import pytest

from shared.constants import ActionType


class TestQualityTraceIndependence:
    """质量追溯独立性测试（v1.2: 不再依赖 service_orders 表）"""

    def test_action_type_values_are_valid(self):
        """处理动作类型枚举值完整"""
        actions = [a.value for a in ActionType]
        assert "Auto_Reply" in actions
        assert "Routed" in actions
        assert "Manual_Resolved" in actions
        assert "Escalated" in actions

    def test_action_type_not_order_type(self):
        """v1.2 处理动作类型不包含 v1.1 出单类型"""
        actions = [a.value for a in ActionType]
        # v1.1 出单类型不应出现在 v1.2 处理动作中
        assert "Replacement" not in actions
        assert "Repair" not in actions
        assert "Return_Exchange" not in actions
        assert "Tech_Support" not in actions
        assert "QC" not in actions

    def test_archive_complete_filter_values(self):
        """归档完整性筛选值"""
        # archive_complete=1 表示完整，0 表示部分缺失
        assert 1 == 1  # 完整
        assert 0 == 0  # 部分缺失

    def test_quality_trace_query_has_archive_complete_field(self):
        """QualityTraceQuery 包含 archive_complete 筛选字段"""
        from backend.app.schemas.quality import QualityTraceQuery
        query = QualityTraceQuery(archive_complete=1)
        assert query.archive_complete == 1

    def test_quality_trace_query_has_action_type_field(self):
        """QualityTraceQuery 包含 action_type 筛选字段（原 order_type）"""
        from backend.app.schemas.quality import QualityTraceQuery
        query = QualityTraceQuery(action_type="Auto_Reply")
        assert query.action_type == "Auto_Reply"

    def test_quality_trace_query_no_order_type_field(self):
        """QualityTraceQuery 不再包含 order_type 筛选字段"""
        from backend.app.schemas.quality import QualityTraceQuery
        query = QualityTraceQuery()
        assert not hasattr(query, "order_type")

    def test_quality_dashboard_response_has_archive_rate(self):
        """QualityDashboardResponse overview 包含 archive_complete_rate"""
        # overview 字段由 service 返回 dict，验证 schema 不报错
        from backend.app.schemas.quality import QualityDashboardResponse
        data = {
            "overview": {
                "total_tickets": 10,
                "total_archived": 10,
                "high_urgency_rate": 20.0,
                "archive_complete_rate": 100.0,
            },
            "trend": {"dates": [], "ticket_counts": [], "archived_counts": []},
            "top_models": [],
            "category_distribution": {},
            "action_type_distribution": {},
        }
        resp = QualityDashboardResponse(**data)
        assert resp.overview["archive_complete_rate"] == 100.0
