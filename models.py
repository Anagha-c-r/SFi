from __future__ import annotations

import enum
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base, JSONType


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return uuid.uuid4().hex


class Role(str, enum.Enum):
    platform_admin = "platform_admin"  # Finoworks staff: manages institutions
    admin = "admin"  # institution admin: users, CBK credentials, settings
    maker = "maker"  # uploads and prepares submissions
    checker = "checker"  # approves submissions before they go to CBK
    viewer = "viewer"  # read-only


class Status(str, enum.Enum):
    invalid = "invalid"  # failed validation, cannot be sent
    validated = "validated"  # passed validation, not yet sent for approval
    pending_approval = "pending_approval"
    rejected = "rejected"  # rejected by a checker in the portal
    queued = "queued"  # approved, waiting to be sent
    sending = "sending"
    submitted = "submitted"  # CBK accepted the request and returned a RequestNo
    failed = "failed"  # the call to CBK failed; can be retried
    cbk_accepted = "cbk_accepted"  # CBK's emailed validation result: accepted
    cbk_rejected = "cbk_rejected"  # CBK's emailed validation result: rejected


class Environment(str, enum.Enum):
    uat = "uat"
    prod = "prod"


class Institution(Base):
    __tablename__ = "institutions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200))
    institution_code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    category: Mapped[str] = mapped_column(String(40), default="commercial_bank")
    environment: Mapped[str] = mapped_column(String(10), default=Environment.uat.value)
    cbk_client_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    cbk_client_secret_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    cbk_scope: Mapped[str | None] = mapped_column(Text, nullable=True)
    notification_email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    four_eyes: Mapped[bool] = mapped_column(Boolean, default=True)  # maker cannot approve own upload
    date_format: Mapped[str] = mapped_column(String(20), default="%d-%b-%Y")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    users: Mapped[list[User]] = relationship(back_populates="institution")

    @property
    def has_credentials(self) -> bool:
        return bool(self.cbk_client_id and self.cbk_client_secret_enc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    institution_id: Mapped[str | None] = mapped_column(ForeignKey("institutions.id"), nullable=True, index=True)
    email: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(200))
    password_hash: Mapped[str] = mapped_column(String(300))
    role: Mapped[str] = mapped_column(String(20), default=Role.maker.value)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    institution: Mapped[Institution | None] = relationship(back_populates="users")


class Submission(Base):
    __tablename__ = "submissions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    institution_id: Mapped[str] = mapped_column(ForeignKey("institutions.id"), index=True)
    dataset_code: Mapped[str] = mapped_column(String(80), index=True)
    reporting_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), index=True)
    original_filename: Mapped[str | None] = mapped_column(String(300), nullable=True)
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    warning_count: Mapped[int] = mapped_column(Integer, default=0)
    rows: Mapped[list] = mapped_column(JSONType, default=list)
    issues: Mapped[list] = mapped_column(JSONType, default=list)
    column_map: Mapped[dict] = mapped_column(JSONType, default=dict)
    override_request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    transport: Mapped[str] = mapped_column(String(10), default="json")  # json | csv
    environment: Mapped[str] = mapped_column(String(10), default=Environment.uat.value)

    cbk_request_no: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    cbk_status_text: Mapped[str | None] = mapped_column(String(200), nullable=True)
    cbk_http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cbk_response: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_by_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    approved_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_by: Mapped[User] = relationship(foreign_keys=[created_by_id])
    approved_by: Mapped[User | None] = relationship(foreign_keys=[approved_by_id])


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    institution_id: Mapped[str | None] = mapped_column(ForeignKey("institutions.id"), nullable=True, index=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(60))
    entity_type: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    detail: Mapped[dict] = mapped_column(JSONType, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)

    user: Mapped[User | None] = relationship()
