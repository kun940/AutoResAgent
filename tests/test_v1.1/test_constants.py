"""v1.1 常量与枚举单元测试"""
import pytest

from shared.constants import (
    OrderType, OrderStatus, OrderTicketStatus,
    ORDER_TYPE_PREFIX, ORDER_TYPE_LABELS,
    ORDER_STATUS_TRANSITIONS, DEFAULT_ORDER_MAPPING,
    IssueCategory, UrgencyLevel,
    NotificationType, TicketAction, UserRole,
)


class TestOrderType:
    """出单类型枚举测试"""

    def test_order_type_values(self):
        assert OrderType.REPLACEMENT.value == "Replacement"
        assert OrderType.REPAIR.value == "Repair"
        assert OrderType.RETURN_EXCHANGE.value == "Return_Exchange"
        assert OrderType.TECH_SUPPORT.value == "Tech_Support"
        assert OrderType.QC.value == "QC"

    def test_order_type_count(self):
        assert len(list(OrderType)) == 5

    def test_order_type_from_value(self):
        assert OrderType("Replacement") == OrderType.REPLACEMENT
        assert OrderType("QC") == OrderType.QC

    def test_order_type_invalid_value(self):
        with pytest.raises(ValueError):
            OrderType("invalid_type")


class TestOrderStatus:
    """出单状态枚举测试"""

    def test_status_values(self):
        assert OrderStatus.PENDING.value == "pending"
        assert OrderStatus.PROCESSING.value == "processing"
        assert OrderStatus.EXECUTING.value == "executing"
        assert OrderStatus.COMPLETED.value == "completed"
        assert OrderStatus.CANCELLED.value == "cancelled"

    def test_status_count(self):
        assert len(list(OrderStatus)) == 5


class TestOrderTicketStatus:
    """工单出单状态枚举测试"""

    def test_values(self):
        assert OrderTicketStatus.NONE.value == "none"
        assert OrderTicketStatus.PENDING_MANUAL.value == "pending_manual"
        assert OrderTicketStatus.ORDERED.value == "ordered"


class TestOrderTypePrefix:
    """出单类型前缀映射测试"""

    def test_all_types_have_prefix(self):
        for ot in OrderType:
            assert ot in ORDER_TYPE_PREFIX, f"{ot} 缺少前缀定义"

    def test_prefix_values(self):
        assert ORDER_TYPE_PREFIX[OrderType.REPLACEMENT] == "REP"
        assert ORDER_TYPE_PREFIX[OrderType.REPAIR] == "RPR"
        assert ORDER_TYPE_PREFIX[OrderType.RETURN_EXCHANGE] == "RTE"
        assert ORDER_TYPE_PREFIX[OrderType.TECH_SUPPORT] == "TCH"
        assert ORDER_TYPE_PREFIX[OrderType.QC] == "QCI"

    def test_prefix_uniqueness(self):
        prefixes = list(ORDER_TYPE_PREFIX.values())
        assert len(prefixes) == len(set(prefixes)), "前缀存在重复"


class TestOrderTypeLabels:
    """出单类型中文标签测试"""

    def test_all_types_have_labels(self):
        for ot in OrderType:
            assert ot in ORDER_TYPE_LABELS, f"{ot} 缺少中文标签"

    def test_label_values(self):
        assert ORDER_TYPE_LABELS[OrderType.REPLACEMENT] == "补发单"
        assert ORDER_TYPE_LABELS[OrderType.REPAIR] == "维修单"
        assert ORDER_TYPE_LABELS[OrderType.RETURN_EXCHANGE] == "退换单"
        assert ORDER_TYPE_LABELS[OrderType.TECH_SUPPORT] == "技术支援单"
        assert ORDER_TYPE_LABELS[OrderType.QC] == "质检单"


class TestOrderStatusTransitions:
    """出单状态流转规则测试"""

    def test_pending_can_transition_to(self):
        allowed = ORDER_STATUS_TRANSITIONS[OrderStatus.PENDING]
        assert OrderStatus.PROCESSING in allowed
        assert OrderStatus.CANCELLED in allowed
        assert OrderStatus.COMPLETED not in allowed

    def test_processing_can_transition_to(self):
        allowed = ORDER_STATUS_TRANSITIONS[OrderStatus.PROCESSING]
        assert OrderStatus.EXECUTING in allowed
        assert OrderStatus.CANCELLED in allowed

    def test_executing_can_transition_to(self):
        allowed = ORDER_STATUS_TRANSITIONS[OrderStatus.EXECUTING]
        assert OrderStatus.COMPLETED in allowed
        assert OrderStatus.CANCELLED in allowed

    def test_completed_is_terminal(self):
        assert ORDER_STATUS_TRANSITIONS[OrderStatus.COMPLETED] == []

    def test_cancelled_is_terminal(self):
        assert ORDER_STATUS_TRANSITIONS[OrderStatus.CANCELLED] == []

    def test_all_statuses_have_transitions(self):
        for status in OrderStatus:
            assert status in ORDER_STATUS_TRANSITIONS, f"{status} 缺少流转规则定义"


class TestDefaultOrderMapping:
    """默认出单映射规则测试"""

    def test_missing_parts_maps_to_replacement(self):
        assert OrderType.REPLACEMENT in DEFAULT_ORDER_MAPPING[IssueCategory.MISSING_PARTS]

    def test_hardware_maps_to_repair(self):
        assert OrderType.REPAIR in DEFAULT_ORDER_MAPPING[IssueCategory.HARDWARE_MALFUNCTION]
        assert OrderType.REPAIR in DEFAULT_ORDER_MAPPING[IssueCategory.HARDWARE_THERMAL_RUNAWAY]
        assert OrderType.REPAIR in DEFAULT_ORDER_MAPPING[IssueCategory.ELECTRICAL_LEAKAGE]

    def test_batch_defect_maps_to_dual_orders(self):
        rules = DEFAULT_ORDER_MAPPING[IssueCategory.BATCH_DEFECT]
        assert OrderType.RETURN_EXCHANGE in rules
        assert OrderType.QC in rules
        assert len(rules) == 2, "批次缺陷应同时生成退换单和质检单"

    def test_safety_hazard_maps_to_dual_orders(self):
        rules = DEFAULT_ORDER_MAPPING[IssueCategory.SAFETY_HAZARD]
        assert OrderType.RETURN_EXCHANGE in rules
        assert OrderType.QC in rules
        assert len(rules) == 2, "安全隐患应同时生成退换单和质检单"

    def test_operation_error_maps_to_tech_support(self):
        assert OrderType.TECH_SUPPORT in DEFAULT_ORDER_MAPPING[IssueCategory.OPERATION_ERROR]

    def test_software_bug_maps_to_tech_support(self):
        assert OrderType.TECH_SUPPORT in DEFAULT_ORDER_MAPPING[IssueCategory.SOFTWARE_BUG]

    def test_all_categories_have_mapping(self):
        for cat in IssueCategory:
            assert cat in DEFAULT_ORDER_MAPPING, f"{cat} 缺少默认映射规则"

    def test_all_mapped_types_are_valid(self):
        for cat, types in DEFAULT_ORDER_MAPPING.items():
            for t in types:
                assert isinstance(t, OrderType), f"{cat} 映射了无效类型 {t}"


class TestExtendedEnums:
    """v1.1 扩展的枚举值测试"""

    def test_notification_type_has_order_created(self):
        assert NotificationType.ORDER_CREATED.value == "order_created"

    def test_ticket_action_has_order_created(self):
        assert TicketAction.ORDER_CREATED.value == "order_created"

    def test_user_role_has_qc_staff(self):
        assert UserRole.QC_STAFF.value == "qc_staff"
