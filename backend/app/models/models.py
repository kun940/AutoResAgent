from datetime import datetime, date
from typing import Optional, List

from sqlalchemy import String, Text, Integer, BigInteger, DateTime, Date, JSON, Enum as SQLEnum, SmallInteger, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.mysql import TINYINT

from backend.app.database import Base
from shared.constants import UserRole, TicketStatus, UrgencyLevel, IssueCategory, NotificationType, TicketAction, FileType


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False, default=UserRole.FRONTLINE_STAFF)
    department: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    is_active: Mapped[int] = mapped_column(SmallInteger, default=1)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=datetime.now)

    tickets_assigned = relationship("Ticket", back_populates="assignee", foreign_keys="Ticket.assigned_to")
    notifications = relationship("Notification", back_populates="target_user")
    ticket_logs = relationship("TicketLog", back_populates="operator")


class Ticket(Base):
    __tablename__ = "tickets"
    __table_args__ = (
        Index("idx_status", "status"),
        Index("idx_urgency_level", "urgency_level"),
        Index("idx_issue_category", "issue_category"),
        Index("idx_created_at", "created_at"),
        Index("idx_routing_decision", "routing_decision"),
    )

    ticket_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    customer_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    customer_phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    raw_input: Mapped[str] = mapped_column(Text, nullable=False)
    extracted_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    agent_business_assessment: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    urgency_level: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    issue_category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    warranty_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    routing_decision: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    auto_reply_sent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sop_applied: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default=TicketStatus.PENDING)
    assigned_to: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=datetime.now)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)

    assignee = relationship("User", back_populates="tickets_assigned", foreign_keys=[assigned_to])
    evidence_files = relationship("EvidenceFile", back_populates="ticket", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="ticket")
    logs = relationship("TicketLog", back_populates="ticket", cascade="all, delete-orphan")


class EvidenceFile(Base):
    __tablename__ = "evidence_files"
    __table_args__ = (
        Index("idx_ticket_id", "ticket_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ticket_id: Mapped[str] = mapped_column(String(50), ForeignKey("tickets.ticket_id"), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    thumbnail_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    file_type: Mapped[str] = mapped_column(String(20), nullable=False)
    file_size: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    uploaded_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=datetime.now)

    ticket = relationship("Ticket", back_populates="evidence_files")


class SopKnowledge(Base):
    __tablename__ = "sop_knowledge_base"
    __table_args__ = (
        Index("idx_issue_category", "issue_category"),
        Index("idx_urgency_level", "urgency_level"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    issue_category: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    urgency_level: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    keywords: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    is_active: Mapped[int] = mapped_column(SmallInteger, default=1)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)


class WarrantyRecord(Base):
    __tablename__ = "warranty_records"
    __table_args__ = (
        Index("idx_sn_code", "sn_code"),
        Index("idx_model_number", "model_number"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    sn_code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    model_number: Mapped[str] = mapped_column(String(100), nullable=False)
    batch_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    warranty_start: Mapped[date] = mapped_column(Date, nullable=False)
    warranty_end: Mapped[date] = mapped_column(Date, nullable=False)
    customer_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    order_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=datetime.now)


class RoutingRule(Base):
    __tablename__ = "routing_rules"
    __table_args__ = (
        Index("idx_urgency_level", "urgency_level"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    urgency_level: Mapped[str] = mapped_column(String(50), nullable=False)
    target_role: Mapped[str] = mapped_column(String(100), nullable=False)
    target_department: Mapped[str] = mapped_column(String(100), nullable=False)
    sla_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=24)
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    is_active: Mapped[int] = mapped_column(SmallInteger, default=1)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=datetime.now)


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        Index("idx_ticket_id", "ticket_id"),
        Index("idx_target_user_id", "target_user_id"),
        Index("idx_is_read", "is_read"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ticket_id: Mapped[str] = mapped_column(String(50), ForeignKey("tickets.ticket_id"), nullable=False)
    target_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    type: Mapped[str] = mapped_column(String(30), nullable=False)
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_read: Mapped[int] = mapped_column(SmallInteger, default=0)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=datetime.now)

    ticket = relationship("Ticket", back_populates="notifications")
    target_user = relationship("User", back_populates="notifications")


class EscalationRule(Base):
    __tablename__ = "escalation_rules"
    __table_args__ = (
        Index("idx_from_level", "from_level"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    from_level: Mapped[str] = mapped_column(String(50), nullable=False)
    to_level: Mapped[str] = mapped_column(String(50), nullable=False)
    trigger_condition: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    auto_escalate_hours: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)


class TicketLog(Base):
    __tablename__ = "ticket_logs"
    __table_args__ = (
        Index("idx_ticket_id", "ticket_id"),
        Index("idx_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ticket_id: Mapped[str] = mapped_column(String(50), ForeignKey("tickets.ticket_id"), nullable=False)
    action: Mapped[str] = mapped_column(String(30), nullable=False)
    operator_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=True)
    detail: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=datetime.now)

    ticket = relationship("Ticket", back_populates="logs")
    operator = relationship("User", back_populates="ticket_logs")
