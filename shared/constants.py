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
    ORDER_CREATED = "order_created"


class TicketAction(str, Enum):
    STATUS_CHANGE = "status_change"
    ESCALATION = "escalation"
    REASSIGN = "reassign"
    NOTE = "note"
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


class OrderType(str, Enum):
    REPLACEMENT = "Replacement"
    REPAIR = "Repair"
    RETURN_EXCHANGE = "Return_Exchange"
    TECH_SUPPORT = "Tech_Support"
    QC = "QC"


class OrderStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    EXECUTING = "executing"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class OrderTicketStatus(str, Enum):
    NONE = "none"
    PENDING_MANUAL = "pending_manual"
    ORDERED = "ordered"


ORDER_TYPE_PREFIX = {
    OrderType.REPLACEMENT: "REP",
    OrderType.REPAIR: "RPR",
    OrderType.RETURN_EXCHANGE: "RTE",
    OrderType.TECH_SUPPORT: "TCH",
    OrderType.QC: "QCI",
}

ORDER_TYPE_LABELS = {
    OrderType.REPLACEMENT: "补发单",
    OrderType.REPAIR: "维修单",
    OrderType.RETURN_EXCHANGE: "退换单",
    OrderType.TECH_SUPPORT: "技术支援单",
    OrderType.QC: "质检单",
}

ORDER_STATUS_TRANSITIONS = {
    OrderStatus.PENDING: [OrderStatus.PROCESSING, OrderStatus.CANCELLED],
    OrderStatus.PROCESSING: [OrderStatus.EXECUTING, OrderStatus.CANCELLED],
    OrderStatus.EXECUTING: [OrderStatus.COMPLETED, OrderStatus.CANCELLED],
    OrderStatus.COMPLETED: [],
    OrderStatus.CANCELLED: [],
}

DEFAULT_ORDER_MAPPING = {
    IssueCategory.MISSING_PARTS: [OrderType.REPLACEMENT],
    IssueCategory.OPERATION_ERROR: [OrderType.TECH_SUPPORT],
    IssueCategory.SOFTWARE_BUG: [OrderType.TECH_SUPPORT],
    IssueCategory.HARDWARE_MALFUNCTION: [OrderType.REPAIR],
    IssueCategory.HARDWARE_THERMAL_RUNAWAY: [OrderType.REPAIR],
    IssueCategory.ELECTRICAL_LEAKAGE: [OrderType.REPAIR],
    IssueCategory.BATCH_DEFECT: [OrderType.RETURN_EXCHANGE, OrderType.QC],
    IssueCategory.SAFETY_HAZARD: [OrderType.RETURN_EXCHANGE, OrderType.QC],
    IssueCategory.OTHER: [OrderType.TECH_SUPPORT],
}
