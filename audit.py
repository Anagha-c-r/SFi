from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import AuditEvent, User


def record(db: Session, *, user: User | None, action: str, entity_type: str, entity_id: str | None = None,
           institution_id: str | None = None, **detail) -> None:
    db.add(AuditEvent(
        institution_id=institution_id if institution_id is not None else (user.institution_id if user else None),
        user_id=user.id if user else None,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        detail=detail,
    ))
