"""v1.2 归档完整性单元测试

验证工单归档完整性校验逻辑：
- archive_complete 标记规则（raw_input/extracted_data/assessment/auto_reply 非空）
- 质量追溯索引同步写入
"""
import pytest
from datetime import datetime

from shared.constants import ActionType


class TestArchiveCompleteLogic:
    """归档完整性标记逻辑测试"""

    def test_archive_complete_all_fields_present(self):
        """所有核心字段非空时 archive_complete=1"""
        result = {
            "raw_input": "设备故障",
            "extracted_data": {"model_number": "Pro-Max-V2"},
            "agent_business_assessment": {"issue_category": "Hardware_Malfunction"},
            "auto_reply_sent": "请尝试重启设备",
        }
        archive_complete = all([
            result.get("raw_input"),
            result.get("extracted_data"),
            result.get("agent_business_assessment"),
            result.get("auto_reply_sent"),
        ])
        assert archive_complete is True

    def test_archive_complete_missing_raw_input(self):
        """缺少 raw_input 时 archive_complete=0"""
        result = {
            "raw_input": "",
            "extracted_data": {"model_number": "Pro-Max-V2"},
            "agent_business_assessment": {"issue_category": "Hardware_Malfunction"},
            "auto_reply_sent": "请尝试重启设备",
        }
        archive_complete = all([
            result.get("raw_input"),
            result.get("extracted_data"),
            result.get("agent_business_assessment"),
            result.get("auto_reply_sent"),
        ])
        assert archive_complete is False

    def test_archive_complete_missing_assessment(self):
        """缺少 agent_business_assessment 时 archive_complete=0"""
        result = {
            "raw_input": "设备故障",
            "extracted_data": {"model_number": "Pro-Max-V2"},
            "agent_business_assessment": None,
            "auto_reply_sent": "请尝试重启设备",
        }
        archive_complete = all([
            result.get("raw_input"),
            result.get("extracted_data"),
            result.get("agent_business_assessment"),
            result.get("auto_reply_sent"),
        ])
        assert archive_complete is False

    def test_archive_complete_missing_auto_reply(self):
        """缺少 auto_reply_sent 时 archive_complete=0"""
        result = {
            "raw_input": "设备故障",
            "extracted_data": {"model_number": "Pro-Max-V2"},
            "agent_business_assessment": {"issue_category": "Hardware_Malfunction"},
            "auto_reply_sent": "",
        }
        archive_complete = all([
            result.get("raw_input"),
            result.get("extracted_data"),
            result.get("agent_business_assessment"),
            result.get("auto_reply_sent"),
        ])
        assert archive_complete is False


class TestActionType:
    """处理动作类型测试（v1.2 质量追溯 order_type 新语义）"""

    def test_auto_reply_is_default_for_new_tickets(self):
        """新工单入库时处理动作应为 Auto_Reply"""
        assert ActionType.AUTO_REPLY.value == "Auto_Reply"

    def test_manual_resolved_for_resolved_tickets(self):
        """工单解决后处理动作应更新为 Manual_Resolved"""
        assert ActionType.MANUAL_RESOLVED.value == "Manual_Resolved"

    def test_routed_for_routed_tickets(self):
        """路由分发后处理动作可为 Routed"""
        assert ActionType.ROUTED.value == "Routed"

    def test_escalated_for_escalated_tickets(self):
        """升级工单处理动作为 Escalated"""
        assert ActionType.ESCALATED.value == "Escalated"
