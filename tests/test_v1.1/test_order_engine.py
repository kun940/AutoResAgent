"""出单引擎 OrderEngine 单元测试"""
import re
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.core.order_engine import OrderEngine
from shared.constants import (
    OrderType, OrderStatus, OrderTicketStatus,
    ORDER_TYPE_PREFIX, ORDER_TYPE_LABELS,
    IssueCategory, UrgencyLevel,
)


@pytest.fixture
def engine():
    return OrderEngine()


# ============================================================
# 纯单元测试 - 不依赖数据库
# ============================================================

class TestBuildMaterialList:
    """物料清单构建测试"""

    def test_replacement_material(self, engine):
        data = {"model_number": "Pro-Max-V2", "batch_code": "B2026-03"}
        result = engine._build_material_list("Replacement", data)
        assert len(result) == 1
        assert result[0]["item_code"] == "PART-Pro-Max-V2"
        assert "配件套件" in result[0]["item_name"]
        assert result[0]["quantity"] == 1

    def test_repair_material(self, engine):
        data = {"model_number": "Pro-Max-V2", "batch_code": "B2026-03"}
        result = engine._build_material_list("Repair", data)
        assert len(result) == 1
        assert result[0]["item_code"] == "DEVICE-Pro-Max-V2"
        assert "待维修设备" in result[0]["item_name"]

    def test_return_exchange_material(self, engine):
        data = {"model_number": "Pro-Max-V2", "batch_code": "B2026-03"}
        result = engine._build_material_list("Return_Exchange", data)
        assert len(result) == 2
        assert result[0]["item_code"] == "DEVICE-Pro-Max-V2"
        assert result[1]["item_code"] == "NEW-Pro-Max-V2"
        assert "退换设备" in result[0]["item_name"]
        assert "新设备" in result[1]["item_name"]

    def test_tech_support_material_empty(self, engine):
        data = {"model_number": "Pro-Max-V2", "batch_code": "B2026-03"}
        result = engine._build_material_list("Tech_Support", data)
        assert result == [], "技术支援单不应有物料清单"

    def test_qc_material(self, engine):
        data = {"model_number": "Pro-Max-V2", "batch_code": "B2026-03"}
        result = engine._build_material_list("QC", data)
        assert len(result) == 1
        assert result[0]["item_code"] == "QC-Pro-Max-V2-B2026-03"
        assert "待检产品" in result[0]["item_name"]
        assert "B2026-03" in result[0]["item_name"]

    def test_unknown_type_returns_empty(self, engine):
        result = engine._build_material_list("Unknown_Type", {})
        assert result == []

    def test_missing_model_uses_unknown(self, engine):
        result = engine._build_material_list("Replacement", {})
        assert "UNKNOWN" in result[0]["item_code"]

    def test_none_model_uses_unknown(self, engine):
        result = engine._build_material_list("Replacement", {"model_number": None})
        assert "UNKNOWN" in result[0]["item_code"]

    def test_empty_string_model_uses_unknown(self, engine):
        result = engine._build_material_list("Replacement", {"model_number": ""})
        assert "UNKNOWN" in result[0]["item_code"]


class TestGetDefaultDepartment:
    """默认部门获取测试"""

    def test_replacement_department(self, engine):
        assert engine._get_default_department("Replacement") == "售后服务部"

    def test_repair_department(self, engine):
        assert engine._get_default_department("Repair") == "技术维修部"

    def test_return_exchange_department(self, engine):
        assert engine._get_default_department("Return_Exchange") == "售后服务部"

    def test_tech_support_department(self, engine):
        assert engine._get_default_department("Tech_Support") == "技术支持部"

    def test_qc_department(self, engine):
        assert engine._get_default_department("QC") == "质量管理部"

    def test_unknown_type_defaults_to_after_sales(self, engine):
        assert engine._get_default_department("Unknown") == "售后服务部"


class TestGetDefaultSlaHours:
    """默认SLA时长测试"""

    def test_high_priority_sla(self, engine):
        assert engine._get_default_sla_hours("High_Priority") == 24

    def test_medium_priority_sla(self, engine):
        assert engine._get_default_sla_hours("Medium_Priority") == 48

    def test_low_priority_sla(self, engine):
        assert engine._get_default_sla_hours("Low_Priority") == 72

    def test_unknown_urgency_defaults_48(self, engine):
        assert engine._get_default_sla_hours("Unknown") == 48


# ============================================================
# 单据编号生成测试
# ============================================================

class TestGenerateOrderNo:
    """单据编号生成测试"""

    @pytest.mark.asyncio
    async def test_order_no_format(self, engine):
        """测试编号格式: SO-{PREFIX}-{YYYYMMDD}-{SEQ}"""
        with patch.object(engine, "_get_next_seq", new_callable=AsyncMock, return_value=1):
            order_no = await engine._generate_order_no("Replacement")
            # SO-REP-20260617-0001
            assert re.match(r"SO-REP-\d{8}-\d{4}", order_no), f"编号格式错误: {order_no}"

    @pytest.mark.asyncio
    async def test_order_no_prefix_mapping(self, engine):
        """测试各类型前缀正确"""
        type_prefix_pairs = [
            ("Replacement", "REP"),
            ("Repair", "RPR"),
            ("Return_Exchange", "RTE"),
            ("Tech_Support", "TCH"),
            ("QC", "QCI"),
        ]
        for order_type, expected_prefix in type_prefix_pairs:
            with patch.object(engine, "_get_next_seq", new_callable=AsyncMock, return_value=1):
                order_no = await engine._generate_order_no(order_type)
                assert f"SO-{expected_prefix}-" in order_no, \
                    f"类型 {order_type} 前缀应为 {expected_prefix}, 实际: {order_no}"

    @pytest.mark.asyncio
    async def test_order_no_seq_padding(self, engine):
        """测试序号4位补零"""
        with patch.object(engine, "_get_next_seq", new_callable=AsyncMock, return_value=42):
            order_no = await engine._generate_order_no("Replacement")
            assert order_no.endswith("-0042"), f"序号补零错误: {order_no}"

    @pytest.mark.asyncio
    async def test_order_no_unknown_type(self, engine):
        """测试未知类型使用 UNK 前缀"""
        with patch.object(engine, "_get_next_seq", new_callable=AsyncMock, return_value=1):
            order_no = await engine._generate_order_no("Unknown_Type")
            assert "SO-UNK-" in order_no


# ============================================================
# 映射规则解析测试 - 回退到默认规则
# ============================================================

class TestResolveMappingFallback:
    """映射规则解析 - 回退到默认规则测试"""

    @pytest.mark.asyncio
    async def test_fallback_missing_parts(self, engine):
        """配件缺失回退到补发单"""
        with patch("backend.app.database.async_session", side_effect=Exception("DB unavailable")):
            rules = await engine._resolve_mapping("Missing_Parts", "Medium_Priority")
            assert len(rules) >= 1
            assert rules[0]["order_type"] == "Replacement"
            assert rules[0]["department"] == "售后服务部"

    @pytest.mark.asyncio
    async def test_fallback_hardware_malfunction(self, engine):
        """硬件故障回退到维修单"""
        with patch("backend.app.database.async_session", side_effect=Exception("DB unavailable")):
            rules = await engine._resolve_mapping("Hardware_Malfunction", "High_Priority")
            assert any(r["order_type"] == "Repair" for r in rules)

    @pytest.mark.asyncio
    async def test_fallback_batch_defect_dual_orders(self, engine):
        """批次缺陷回退生成退换单+质检单"""
        with patch("backend.app.database.async_session", side_effect=Exception("DB unavailable")):
            rules = await engine._resolve_mapping("Batch_Defect", "High_Priority")
            order_types = [r["order_type"] for r in rules]
            assert "Return_Exchange" in order_types
            assert "QC" in order_types
            assert len(rules) == 2

    @pytest.mark.asyncio
    async def test_fallback_safety_hazard_dual_orders(self, engine):
        """安全隐患回退生成退换单+质检单"""
        with patch("backend.app.database.async_session", side_effect=Exception("DB unavailable")):
            rules = await engine._resolve_mapping("Safety_Hazard", "High_Priority")
            order_types = [r["order_type"] for r in rules]
            assert "Return_Exchange" in order_types
            assert "QC" in order_types

    @pytest.mark.asyncio
    async def test_fallback_unknown_category(self, engine):
        """未知分类回退到 Other -> 技术支援单"""
        with patch("backend.app.database.async_session", side_effect=Exception("DB unavailable")):
            rules = await engine._resolve_mapping("Unknown_Category", "Medium_Priority")
            assert any(r["order_type"] == "Tech_Support" for r in rules)

    @pytest.mark.asyncio
    async def test_fallback_sla_by_urgency(self, engine):
        """回退规则中SLA按紧急度设置"""
        with patch("backend.app.database.async_session", side_effect=Exception("DB unavailable")):
            rules_high = await engine._resolve_mapping("Missing_Parts", "High_Priority")
            rules_low = await engine._resolve_mapping("Missing_Parts", "Low_Priority")
            assert rules_high[0]["sla_hours"] == 24
            assert rules_low[0]["sla_hours"] == 72


# ============================================================
# decide_and_create 异常处理测试（不依赖真实数据库）
# ============================================================

class TestDecideAndCreateErrorHandling:
    """出单决策主入口 - 异常处理测试"""

    @pytest.mark.asyncio
    async def test_no_mapping_rule_returns_pending_manual(self, engine):
        """无映射规则时返回 pending_manual"""
        with patch.object(engine, "_resolve_mapping", new_callable=AsyncMock, return_value=[]):
            with patch.object(engine, "_update_ticket_order_status", new_callable=AsyncMock):
                result = await engine.decide_and_create(
                    ticket_id="CS-TEST-001",
                    issue_category="Unknown",
                    urgency_level="Medium_Priority",
                    extracted_data={},
                )
                assert result["success"] is False
                assert result["order_status"] == OrderTicketStatus.PENDING_MANUAL
                assert result["error"] == "no_mapping_rule"
                assert result["orders"] == []

    @pytest.mark.asyncio
    async def test_all_orders_failed_returns_pending_manual(self, engine):
        """所有单据创建失败时返回 pending_manual"""
        mock_rule = {"order_type": "Replacement", "department": "售后服务部", "sla_hours": 48}
        with patch.object(engine, "_resolve_mapping", new_callable=AsyncMock, return_value=[mock_rule]):
            with patch.object(engine, "_create_single_order", new_callable=AsyncMock, return_value=None):
                with patch.object(engine, "_update_ticket_order_status", new_callable=AsyncMock):
                    result = await engine.decide_and_create(
                        ticket_id="CS-TEST-002",
                        issue_category="Missing_Parts",
                        urgency_level="Medium_Priority",
                        extracted_data={},
                    )
                    assert result["success"] is False
                    assert result["order_status"] == OrderTicketStatus.PENDING_MANUAL
                    assert result["error"] == "all_orders_failed"

    @pytest.mark.asyncio
    async def test_exception_returns_pending_manual(self, engine):
        """主流程异常时返回 pending_manual"""
        with patch.object(engine, "_resolve_mapping", new_callable=AsyncMock, side_effect=RuntimeError("DB down")):
            with patch.object(engine, "_update_ticket_order_status", new_callable=AsyncMock):
                result = await engine.decide_and_create(
                    ticket_id="CS-TEST-003",
                    issue_category="Missing_Parts",
                    urgency_level="Medium_Priority",
                    extracted_data={},
                )
                assert result["success"] is False
                assert result["order_status"] == OrderTicketStatus.PENDING_MANUAL
                assert "DB down" in result["error"]

    @pytest.mark.asyncio
    async def test_successful_single_order(self, engine):
        """成功创建单张单据"""
        mock_rule = {"order_type": "Replacement", "department": "售后服务部", "sla_hours": 48}
        mock_order = {
            "order_no": "SO-REP-20260617-0001",
            "order_type": "Replacement",
            "order_type_label": "补发单",
            "department": "售后服务部",
            "sla_hours": 48,
            "status": "pending",
        }
        with patch.object(engine, "_resolve_mapping", new_callable=AsyncMock, return_value=[mock_rule]):
            with patch.object(engine, "_create_single_order", new_callable=AsyncMock, return_value=mock_order):
                with patch.object(engine, "_update_ticket_order_status", new_callable=AsyncMock):
                    with patch.object(engine, "_write_ticket_log", new_callable=AsyncMock):
                        with patch.object(engine, "_create_order_notification", new_callable=AsyncMock):
                            result = await engine.decide_and_create(
                                ticket_id="CS-TEST-004",
                                issue_category="Missing_Parts",
                                urgency_level="Medium_Priority",
                                extracted_data={"model_number": "Pro-Max-V2"},
                            )
                            assert result["success"] is True
                            assert result["order_status"] == OrderTicketStatus.ORDERED
                            assert len(result["orders"]) == 1
                            assert result["orders"][0]["order_no"] == "SO-REP-20260617-0001"

    @pytest.mark.asyncio
    async def test_successful_dual_orders(self, engine):
        """成功创建双单据（批次缺陷 -> 退换单+质检单）"""
        mock_rules = [
            {"order_type": "Return_Exchange", "department": "售后服务部", "sla_hours": 24},
            {"order_type": "QC", "department": "质量管理部", "sla_hours": 24},
        ]
        mock_orders = [
            {"order_no": "SO-RTE-20260617-0001", "order_type": "Return_Exchange", "order_type_label": "退换单", "department": "售后服务部", "sla_hours": 24, "status": "pending"},
            {"order_no": "SO-QCI-20260617-0001", "order_type": "QC", "order_type_label": "质检单", "department": "质量管理部", "sla_hours": 24, "status": "pending"},
        ]
        with patch.object(engine, "_resolve_mapping", new_callable=AsyncMock, return_value=mock_rules):
            with patch.object(engine, "_create_single_order", new_callable=AsyncMock, side_effect=mock_orders):
                with patch.object(engine, "_update_ticket_order_status", new_callable=AsyncMock):
                    with patch.object(engine, "_write_ticket_log", new_callable=AsyncMock):
                        with patch.object(engine, "_create_order_notification", new_callable=AsyncMock):
                            result = await engine.decide_and_create(
                                ticket_id="CS-TEST-005",
                                issue_category="Batch_Defect",
                                urgency_level="High_Priority",
                                extracted_data={"model_number": "Pro-Max-V2", "batch_code": "B2026-03"},
                            )
                            assert result["success"] is True
                            assert len(result["orders"]) == 2
                            order_types = [o["order_type"] for o in result["orders"]]
                            assert "Return_Exchange" in order_types
                            assert "QC" in order_types

    @pytest.mark.asyncio
    async def test_partial_failure_continues(self, engine):
        """部分单据创建失败时继续创建其他"""
        mock_rules = [
            {"order_type": "Return_Exchange", "department": "售后服务部", "sla_hours": 24},
            {"order_type": "QC", "department": "质量管理部", "sla_hours": 24},
        ]
        mock_order = {
            "order_no": "SO-RTE-20260617-0001",
            "order_type": "Return_Exchange",
            "order_type_label": "退换单",
            "department": "售后服务部",
            "sla_hours": 24,
            "status": "pending",
        }
        with patch.object(engine, "_resolve_mapping", new_callable=AsyncMock, return_value=mock_rules):
            # 第一张成功，第二张失败
            with patch.object(engine, "_create_single_order", new_callable=AsyncMock, side_effect=[mock_order, None]):
                with patch.object(engine, "_update_ticket_order_status", new_callable=AsyncMock):
                    with patch.object(engine, "_write_ticket_log", new_callable=AsyncMock):
                        with patch.object(engine, "_create_order_notification", new_callable=AsyncMock):
                            result = await engine.decide_and_create(
                                ticket_id="CS-TEST-006",
                                issue_category="Batch_Defect",
                                urgency_level="High_Priority",
                                extracted_data={},
                            )
                            assert result["success"] is True
                            assert len(result["orders"]) == 1


# ============================================================
# 数据库集成测试 - 需要真实数据库
# ============================================================

@pytest.mark.integration
class TestOrderEngineIntegration:
    """出单引擎数据库集成测试"""

    @pytest.fixture(autouse=True)
    def check_db(self, check_db_ready):
        if not check_db_ready:
            pytest.skip("数据库不可用")

    @pytest.mark.asyncio
    async def test_resolve_mapping_from_db(self, engine, db_session):
        """测试从数据库查询映射规则"""
        rules = await engine._resolve_mapping("Missing_Parts", "Medium_Priority", db=db_session)
        assert len(rules) >= 1
        assert rules[0]["order_type"] == "Replacement"
        assert rules[0]["department"] == "售后服务部"
        assert rules[0]["sla_hours"] == 48

    @pytest.mark.asyncio
    async def test_resolve_mapping_batch_defect_from_db(self, engine, db_session):
        """测试批次缺陷从数据库查询到双单据规则"""
        rules = await engine._resolve_mapping("Batch_Defect", "High_Priority", db=db_session)
        order_types = [r["order_type"] for r in rules]
        assert "Return_Exchange" in order_types
        assert "QC" in order_types

    @pytest.mark.asyncio
    async def test_get_next_seq_returns_int(self, engine, db_session):
        """测试序号查询返回整数"""
        seq = await engine._get_next_seq("REP", "20260617", db=db_session)
        assert isinstance(seq, int)
        assert seq >= 1

    @pytest.mark.asyncio
    async def test_generate_order_no_unique_format(self, engine, db_session):
        """测试生成的单据编号格式正确"""
        no1 = await engine._generate_order_no("Replacement", db=db_session)
        assert re.match(r"SO-REP-\d{8}-\d{4}", no1), f"编号格式错误: {no1}"

        no2 = await engine._generate_order_no("Repair", db=db_session)
        assert re.match(r"SO-RPR-\d{8}-\d{4}", no2), f"编号格式错误: {no2}"

        # 不同类型的编号前缀不同
        assert no1.split("-")[1] != no2.split("-")[1], "不同类型的编号前缀应不同"
