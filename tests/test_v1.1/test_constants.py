"""v1.2 常量与枚举单元测试"""
import pytest

from shared.constants import (
    ActionType,
    IssueCategory, UrgencyLevel,
    NotificationType, TicketAction, UserRole,
)


class TestActionType:
    """v1.2 处理动作类型枚举测试"""

    def test_action_type_values(self):
        assert ActionType.AUTO_REPLY.value == "Auto_Reply"
        assert ActionType.ROUTED.value == "Routed"
        assert ActionType.MANUAL_RESOLVED.value == "Manual_Resolved"
        assert ActionType.ESCALATED.value == "Escalated"

    def test_action_type_count(self):
        assert len(list(ActionType)) == 4

    def test_action_type_from_value(self):
        assert ActionType("Auto_Reply") == ActionType.AUTO_REPLY
        assert ActionType("Routed") == ActionType.ROUTED

    def test_action_type_invalid_value(self):
        with pytest.raises(ValueError):
            ActionType("invalid_type")


class TestExtendedEnums:
    """枚举值测试"""

    def test_notification_type_has_order_created(self):
        # v1.2: ORDER_CREATED 保留用于历史日志兼容
        assert NotificationType.ORDER_CREATED.value == "order_created"

    def test_ticket_action_has_order_created(self):
        # v1.2: ORDER_CREATED 保留用于历史日志兼容
        assert TicketAction.ORDER_CREATED.value == "order_created"

    def test_user_role_has_qc_staff(self):
        assert UserRole.QC_STAFF.value == "qc_staff"
