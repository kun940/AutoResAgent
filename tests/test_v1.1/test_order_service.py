"""出单服务 OrderService 单元测试"""
import re
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.app.services.order_service import OrderService, _generate_order_no
from backend.app.models.models import ServiceOrder, OrderMappingRule
from shared.constants import OrderStatus, OrderType, ORDER_TYPE_PREFIX


@pytest.fixture
def service():
    return OrderService()


# ============================================================
# 纯单元测试 - 不依赖数据库
# ============================================================

class TestGenerateOrderNo:
    """出单编号生成函数测试"""

    def test_format_correct(self):
        no = _generate_order_no("Replacement")
        # REP-YYYYMMDD-XXXX
        assert re.match(r"REP-\d{8}-\d{4}", no), f"格式错误: {no}"

    def test_prefix_mapping(self):
        type_prefix_pairs = [
            ("Replacement", "REP"),
            ("Repair", "RPR"),
            ("Return_Exchange", "RTE"),
            ("Tech_Support", "TCH"),
            ("QC", "QCI"),
        ]
        for order_type, expected_prefix in type_prefix_pairs:
            no = _generate_order_no(order_type)
            assert no.startswith(f"{expected_prefix}-"), \
                f"类型 {order_type} 前缀应为 {expected_prefix}, 实际: {no}"

    def test_unknown_type_uses_ORD_prefix(self):
        no = _generate_order_no("Unknown")
        assert no.startswith("ORD-"), f"未知类型应使用ORD前缀, 实际: {no}"

    def test_seq_is_4_digits(self):
        no = _generate_order_no("Replacement")
        parts = no.split("-")
        assert len(parts) == 3
        assert len(parts[2]) == 4, f"序号应为4位, 实际: {parts[2]}"


class TestUpdateOrderStatusValidation:
    """出单状态流转校验测试"""

    def _make_mock_db(self):
        """创建模拟db session"""
        mock_db = MagicMock()
        mock_db.flush = AsyncMock()
        mock_db.refresh = AsyncMock()
        return mock_db

    @pytest.mark.asyncio
    async def test_valid_transition_pending_to_processing(self, service):
        """pending -> processing 合法"""
        mock_order = MagicMock()
        mock_order.id = 1
        mock_order.status = "pending"
        mock_order.order_no = "SO-REP-20260617-0001"
        mock_order.ticket_id = "CS-TEST-001"

        mock_db = self._make_mock_db()
        with patch.object(service, "get_order", new_callable=AsyncMock, return_value=mock_order):
            result = await service.update_order_status(mock_db, 1, "processing")
            assert result is not None
            assert result.status == OrderStatus.PROCESSING

    @pytest.mark.asyncio
    async def test_valid_transition_processing_to_executing(self, service):
        """processing -> executing 合法"""
        mock_order = MagicMock()
        mock_order.id = 1
        mock_order.status = "processing"
        mock_order.order_no = "SO-REP-20260617-0001"
        mock_order.ticket_id = "CS-TEST-001"

        mock_db = self._make_mock_db()
        with patch.object(service, "get_order", new_callable=AsyncMock, return_value=mock_order):
            result = await service.update_order_status(mock_db, 1, "executing")
            assert result.status == OrderStatus.EXECUTING

    @pytest.mark.asyncio
    async def test_valid_transition_executing_to_completed(self, service):
        """executing -> completed 合法，且记录完成信息"""
        mock_order = MagicMock()
        mock_order.id = 1
        mock_order.status = "executing"
        mock_order.order_no = "SO-REP-20260617-0001"
        mock_order.ticket_id = "CS-TEST-001"
        mock_order.completed_at = None
        mock_order.completed_by = None

        mock_db = self._make_mock_db()
        with patch.object(service, "get_order", new_callable=AsyncMock, return_value=mock_order):
            result = await service.update_order_status(mock_db, 1, "completed", user_id=99)
            assert result.status == OrderStatus.COMPLETED
            assert result.completed_at is not None
            assert result.completed_by == 99

    @pytest.mark.asyncio
    async def test_valid_transition_pending_to_cancelled(self, service):
        """pending -> cancelled 合法"""
        mock_order = MagicMock()
        mock_order.id = 1
        mock_order.status = "pending"
        mock_order.order_no = "SO-REP-20260617-0001"
        mock_order.ticket_id = "CS-TEST-001"

        mock_db = self._make_mock_db()
        with patch.object(service, "get_order", new_callable=AsyncMock, return_value=mock_order):
            result = await service.update_order_status(mock_db, 1, "cancelled")
            assert result.status == OrderStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_invalid_transition_pending_to_completed(self, service):
        """pending -> completed 非法"""
        mock_order = MagicMock()
        mock_order.id = 1
        mock_order.status = "pending"
        mock_order.order_no = "SO-REP-20260617-0001"
        mock_order.ticket_id = "CS-TEST-001"

        mock_db = self._make_mock_db()
        with patch.object(service, "get_order", new_callable=AsyncMock, return_value=mock_order):
            with pytest.raises(ValueError, match="非法状态流转"):
                await service.update_order_status(mock_db, 1, "completed")

    @pytest.mark.asyncio
    async def test_invalid_transition_completed_to_pending(self, service):
        """completed -> pending 非法（终态不可流转）"""
        mock_order = MagicMock()
        mock_order.id = 1
        mock_order.status = "completed"
        mock_order.order_no = "SO-REP-20260617-0001"
        mock_order.ticket_id = "CS-TEST-001"

        mock_db = self._make_mock_db()
        with patch.object(service, "get_order", new_callable=AsyncMock, return_value=mock_order):
            with pytest.raises(ValueError, match="非法状态流转"):
                await service.update_order_status(mock_db, 1, "pending")

    @pytest.mark.asyncio
    async def test_invalid_transition_cancelled_to_processing(self, service):
        """cancelled -> processing 非法（终态不可流转）"""
        mock_order = MagicMock()
        mock_order.id = 1
        mock_order.status = "cancelled"
        mock_order.order_no = "SO-REP-20260617-0001"
        mock_order.ticket_id = "CS-TEST-001"

        mock_db = self._make_mock_db()
        with patch.object(service, "get_order", new_callable=AsyncMock, return_value=mock_order):
            with pytest.raises(ValueError, match="非法状态流转"):
                await service.update_order_status(mock_db, 1, "processing")

    @pytest.mark.asyncio
    async def test_order_not_found_returns_none(self, service):
        """出单不存在时返回 None"""
        with patch.object(service, "get_order", new_callable=AsyncMock, return_value=None):
            result = await service.update_order_status(MagicMock(), 999, "processing")
            assert result is None


class TestUpdateMappingRule:
    """映射规则更新测试"""

    @pytest.mark.asyncio
    async def test_update_specific_fields_only(self, service):
        """只更新传入的字段"""
        mock_rule = MagicMock()
        mock_rule.id = 1
        mock_rule.order_type = "Replacement"
        mock_rule.department = "售后服务部"
        mock_rule.sla_hours = 48
        mock_rule.is_active = 1
        mock_rule.priority = 0
        mock_rule.description = None

        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_rule
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.flush = AsyncMock()
        mock_db.refresh = AsyncMock()

        await service.update_mapping_rule(mock_db, 1, {"sla_hours": 72, "description": "更新测试"})

        assert mock_rule.sla_hours == 72
        assert mock_rule.description == "更新测试"
        # 未传入的字段不变
        assert mock_rule.order_type == "Replacement"

    @pytest.mark.asyncio
    async def test_update_rule_not_found(self, service):
        """规则不存在时返回 None"""
        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await service.update_mapping_rule(mock_db, 999, {"sla_hours": 72})
        assert result is None


class TestDeleteMappingRule:
    """映射规则软删除测试"""

    @pytest.mark.asyncio
    async def test_soft_delete_sets_inactive(self, service):
        """软删除设置 is_active=0"""
        mock_rule = MagicMock()
        mock_rule.id = 1
        mock_rule.is_active = 1

        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_rule
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.flush = AsyncMock()
        mock_db.refresh = AsyncMock()

        result = await service.delete_mapping_rule(mock_db, 1)
        assert result is not None
        assert mock_rule.is_active == 0

    @pytest.mark.asyncio
    async def test_delete_rule_not_found(self, service):
        """规则不存在时返回 None"""
        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await service.delete_mapping_rule(mock_db, 999)
        assert result is None


# ============================================================
# 数据库集成测试
# ============================================================

@pytest.mark.integration
class TestOrderServiceIntegration:
    """出单服务数据库集成测试"""

    @pytest.fixture(autouse=True)
    def check_db(self, check_db_ready):
        if not check_db_ready:
            pytest.skip("数据库不可用")

    @pytest.mark.asyncio
    async def test_get_orders_pagination(self, service, db_session):
        """测试出单列表分页"""
        orders, total = await service.get_orders(db_session, page=1, page_size=5)
        assert isinstance(orders, list)
        assert isinstance(total, int)
        assert total >= 0
        assert len(orders) <= 5

    @pytest.mark.asyncio
    async def test_get_orders_filter_by_type(self, service, db_session):
        """测试按类型筛选出单"""
        orders, total = await service.get_orders(db_session, order_type="Replacement")
        for order in orders:
            assert order.order_type == "Replacement"

    @pytest.mark.asyncio
    async def test_get_mapping_rules(self, service, db_session):
        """测试查询映射规则"""
        rules = await service.get_mapping_rules(db_session, is_active=1)
        assert len(rules) > 0
        for rule in rules:
            assert rule.is_active == 1

    @pytest.mark.asyncio
    async def test_get_mapping_rules_filter_by_category(self, service, db_session):
        """测试按问题分类筛选映射规则"""
        rules = await service.get_mapping_rules(db_session, issue_category="Missing_Parts")
        assert len(rules) > 0
        for rule in rules:
            assert rule.issue_category == "Missing_Parts"

    @pytest.mark.asyncio
    async def test_find_mapping_rule(self, service, db_session):
        """测试查找单条映射规则"""
        rule = await service._find_mapping_rule(db_session, "Missing_Parts", "Medium_Priority")
        assert rule is not None
        assert rule.order_type == "Replacement"
        assert rule.department == "售后服务部"
        assert rule.sla_hours == 48
