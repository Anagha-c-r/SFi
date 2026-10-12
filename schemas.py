"""Request and response models for the HTTP API."""
from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models import Role


class LoginIn(BaseModel):
    email: str
    password: str


class InstitutionBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    institution_code: str
    environment: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    email: str
    full_name: str
    role: str
    is_active: bool
    institution: InstitutionBrief | None = None
    last_login_at: datetime | None = None
    created_at: datetime


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: str


class UserCreate(BaseModel):
    email: str
    full_name: str = Field(min_length=1, max_length=200)
    role: Role
    password: str


class UserUpdate(BaseModel):
    full_name: str | None = None
    role: Role | None = None
    is_active: bool | None = None
    password: str | None = None


class InstitutionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    institution_code: str
    category: str
    environment: str
    cbk_client_id: str | None
    has_credentials: bool
    cbk_scope: str | None
    notification_email: str | None
    four_eyes: bool
    date_format: str
    is_active: bool
    created_at: datetime


class InstitutionCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    institution_code: str = Field(min_length=1, max_length=32)
    category: str = "commercial_bank"
    environment: str = "uat"
    admin_email: str
    admin_full_name: str
    admin_password: str


class InstitutionUpdate(BaseModel):
    name: str | None = None
    category: str | None = None
    is_active: bool | None = None


class InstitutionSettingsIn(BaseModel):
    environment: str | None = Field(default=None, pattern="^(uat|prod)$")
    cbk_client_id: str | None = None
    cbk_client_secret: str | None = None  # write-only; never returned
    cbk_scope: str | None = None
    notification_email: str | None = None
    four_eyes: bool | None = None
    date_format: str | None = Field(default=None, pattern="^(%d-%b-%Y|%Y-%m-%d|%d/%m/%Y|%m/%d/%Y)$")


class SubmissionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    dataset_code: str
    dataset_title: str = ""
    reporting_date: date
    status: str
    original_filename: str | None
    row_count: int
    error_count: int
    warning_count: int
    override_request_id: str | None
    transport: str
    environment: str
    cbk_request_no: str | None
    cbk_status_text: str | None
    cbk_http_status: int | None
    last_error: str | None
    attempts: int
    review_note: str | None
    created_by_name: str = ""
    approved_by_name: str | None = None
    created_by_id: str
    created_at: datetime
    updated_at: datetime
    submitted_at: datetime | None


class SubmissionDetail(SubmissionOut):
    issues: list[dict]
    column_map: dict
    cbk_response: dict | None
    preview_rows: list[dict]
    events: list[dict]


class Page(BaseModel):
    items: list
    total: int
    page: int
    page_size: int


class RejectIn(BaseModel):
    note: str = Field(min_length=1, max_length=2000)


class OutcomeIn(BaseModel):
    accepted: bool
    note: str | None = None
