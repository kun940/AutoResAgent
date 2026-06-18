from enum import Enum


class UrgencyLevel(str, Enum):
    LOW = "Low_Priority"
    MEDIUM = "Medium_Priority"
    HIGH = "High_Priority"


class TicketStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    ROUTED = "routed"
    RESOLVED = "resolved"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class UserRole(str, Enum):
    ADMIN = "admin"
    FRONTLINE_STAFF = "frontline_staff"
    DEPARTMENT_MANAGER = "department_manager"
    GENERAL_MANAGER = "general_manager"
    QC_STAFF = "qc_staff"


class IssueCategory(str, Enum):
    MISSING_PARTS = "Missing_Parts"
    OPERATION_ERROR = "Operation_Error"
    SOFTWARE_BUG = "Software_Bug"
    HARDWARE_MALFUNCTION = "Hardware_Malfunction"
    HARDWARE_THERMAL_RUNAWAY = "Hardware_Thermal_Runaway"
    ELECTRICAL_LEAKAGE = "Electrical_Leakage"
    BATCH_DEFECT = "Batch_Defect"
    SAFETY_HAZARD = "Safety_Hazard"
    OTHER = "Other"


class BusinessImpact(str, Enum):
    NO_IMPACT = "No_Impact"
    MINOR_INCONVENIENCE = "Minor_Inconvenience"
    FUNCTIONAL_LOSS = "Functional_Loss"
    PRODUCTION_DOWN = "Production_Down"
    SAFETY_HAZARD = "Safety_Hazard"
    GROUP_RISK = "Group_Risk"


class WarrantyStatus(str, Enum):
    IN_WARRANTY = "In_Warranty"
    OUT_OF_WARRANTY = "Out_of_Warranty"
    UNKNOWN = "Unknown"


class FileType(str, Enum):
    IMAGE = "image"
    VIDEO = "video"
    DOCUMENT = "document"


class NotificationType(str, Enum):
    NEW_TICKET = "new_ticket"
    ESCALATION = "escalation"
    SLA_WARNING = "sla_warning"
    REASSIGN = "reassign"
    # ORDER_CREATED 保留用于历史日志兼容，v1.2 不再产生新值
    ORDER_CREATED = "order_created"


class TicketAction(str, Enum):
    STATUS_CHANGE = "status_change"
    ESCALATION = "escalation"
    REASSIGN = "reassign"
    NOTE = "note"
    # ORDER_CREATED 保留用于历史日志兼容，v1.2 不再产生新值
    ORDER_CREATED = "order_created"


TICKET_STATUS_TRANSITIONS = {
    TicketStatus.PENDING: [TicketStatus.PROCESSING, TicketStatus.CANCELLED],
    TicketStatus.PROCESSING: [TicketStatus.ROUTED, TicketStatus.CANCELLED],
    TicketStatus.ROUTED: [TicketStatus.RESOLVED, TicketStatus.CANCELLED],
    TicketStatus.RESOLVED: [TicketStatus.CLOSED],
    TicketStatus.CLOSED: [],
    TicketStatus.CANCELLED: [],
}

URGENCY_ROUTING_MAP = {
    UrgencyLevel.LOW: "frontline_staff_queue",
    UrgencyLevel.MEDIUM: "department_manager_queue",
    UrgencyLevel.HIGH: "general_manager_dashboard",
}

ESCALATION_RULES = {
    (UrgencyLevel.LOW, UrgencyLevel.MEDIUM): 48,
    (UrgencyLevel.MEDIUM, UrgencyLevel.HIGH): 24,
}

MANUAL_ESCALATION_PERMISSIONS = {
    UserRole.FRONTLINE_STAFF: [UrgencyLevel.MEDIUM],
    UserRole.DEPARTMENT_MANAGER: [UrgencyLevel.HIGH],
    UserRole.ADMIN: [UrgencyLevel.LOW, UrgencyLevel.MEDIUM, UrgencyLevel.HIGH],
}


# ============================================================
# v1.2: 出单相关常量已删除（OrderType/OrderStatus/OrderTicketStatus/
#        ORDER_TYPE_PREFIX/ORDER_TYPE_LABELS/ORDER_STATUS_TRANSITIONS/
#        DEFAULT_ORDER_MAPPING）。质量追溯表的 order_type 字段语义
#        已变更为「处理动作类型」，见下方 ACTION_TYPE 定义。
# ============================================================

class ActionType(str, Enum):
    """工单处理动作类型（v1.2 质量追溯 order_type 字段新语义）"""
    AUTO_REPLY = "Auto_Reply"
    ROUTED = "Routed"
    MANUAL_RESOLVED = "Manual_Resolved"
    ESCALATED = "Escalated"
