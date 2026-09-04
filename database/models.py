"""
GmailAI Assistant - SQLAlchemy Database Models
"""
import datetime
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Boolean,
    Float,
    DateTime,
    ForeignKey,
    Index,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


def _utcnow() -> datetime.datetime:
    """Returns a naive UTC datetime for SQLite storage (timezone-aware internally)."""
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)


class Account(Base):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    display_name = Column(String(255), nullable=True)
    token_encrypted = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    last_synced_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_utcnow)

    emails = relationship("EmailRecord", back_populates="account", cascade="all, delete-orphan")


class EmailRecord(Base):
    __tablename__ = "emails"

    id = Column(Integer, primary_key=True, autoincrement=True)
    message_id = Column(String(128), unique=True, nullable=False, index=True)
    thread_id = Column(String(128), nullable=True, index=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=True)

    sender = Column(String(255), nullable=False, index=True)
    sender_name = Column(String(255), nullable=True)
    recipient = Column(String(255), nullable=True)
    subject = Column(String(512), nullable=False)
    snippet = Column(Text, nullable=True)
    body_plain = Column(Text, nullable=True)
    body_html = Column(Text, nullable=True)
    received_at = Column(DateTime, nullable=False, index=True)

    # Gmail State Flags
    is_unread = Column(Boolean, default=True, index=True)
    is_starred = Column(Boolean, default=False)
    is_trash = Column(Boolean, default=False)
    is_archived = Column(Boolean, default=False)
    labels_json = Column(Text, default="[]")  # JSON encoded list of label IDs/names

    # AI Intelligence Fields
    category = Column(String(64), nullable=True, index=True)
    importance_score = Column(Integer, default=50, index=True)  # 0 to 100
    urgency_score = Column(Integer, default=50)                 # 0 to 100
    risk_level = Column(String(32), default="LOW")
    ai_source = Column(String(64), nullable=True)
    ai_confidence = Column(Float, default=0.0)
    ai_reasoning = Column(Text, nullable=True)
    suggested_action = Column(String(64), nullable=True)
    action_items_json = Column(Text, default="[]")              # Extracted to-dos

    # Attachments
    has_attachments = Column(Boolean, default=False)
    attachments_json = Column(Text, default="[]")

    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    account = relationship("Account", back_populates="emails")
    cleanup_suggestions = relationship("CleanupSuggestion", back_populates="email", cascade="all, delete-orphan")

    @property
    def reasoning(self) -> str:
        return self.ai_reasoning or ""

    @property
    def action_items(self) -> str:
        return self.action_items_json or "[]"

    __table_args__ = (
        Index("idx_email_account_received", "account_id", "received_at"),
        Index("idx_email_category_importance", "category", "importance_score"),
    )


class CleanupSuggestion(Base):
    __tablename__ = "cleanup_suggestions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email_id = Column(Integer, ForeignKey("emails.id"), nullable=False)
    action_type = Column(String(64), nullable=False)
    category = Column(String(64), nullable=False)
    reason = Column(Text, nullable=True)
    confidence = Column(Float, default=0.0)
    status = Column(String(32), default="PENDING", index=True)  # PENDING, APPROVED, REJECTED, EXECUTED
    created_at = Column(DateTime, default=_utcnow)
    executed_at = Column(DateTime, nullable=True)

    email = relationship("EmailRecord", back_populates="cleanup_suggestions")


class SenderProfile(Base):
    __tablename__ = "sender_profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    domain = Column(String(255), nullable=False, index=True)
    name = Column(String(255), nullable=True)
    total_received = Column(Integer, default=0)
    total_opened = Column(Integer, default=0)
    total_replied = Column(Integer, default=0)
    is_vip = Column(Boolean, default=False)
    override_category = Column(String(64), nullable=True)
    learned_importance = Column(Integer, default=50)
    last_interacted_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)


class ActionAuditLog(Base):
    __tablename__ = "action_audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    action_type = Column(String(64), nullable=False)
    email_message_id = Column(String(128), nullable=True)
    account_email = Column(String(255), nullable=True)
    subject = Column(String(512), nullable=True)
    sender = Column(String(255), nullable=True)
    reason = Column(Text, nullable=True)
    user_approved = Column(Boolean, default=True)
    double_confirmed = Column(Boolean, default=False)
    executed_at = Column(DateTime, default=_utcnow, index=True)
    is_undone = Column(Boolean, default=False)


class DailyDigestRecord(Base):
    __tablename__ = "daily_digests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    digest_date = Column(String(32), unique=True, nullable=False, index=True)  # YYYY-MM-DD
    total_emails = Column(Integer, default=0)
    important_count = Column(Integer, default=0)
    need_reply_count = Column(Integer, default=0)
    meetings_count = Column(Integer, default=0)
    cleanup_suggested_count = Column(Integer, default=0)
    summary_markdown = Column(Text, nullable=False)
    stats_json = Column(Text, default="{}")
    created_at = Column(DateTime, default=_utcnow)


class UserSafetyRule(Base):
    __tablename__ = "user_safety_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    rule_type = Column(String(64), nullable=False)  # DOMAIN_PROTECT, NEVER_DELETE, VIP
    pattern = Column(String(255), nullable=False)
    description = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=_utcnow)
