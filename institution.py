"""Institution admin: CBK credentials and settings, users, audit log."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import current_institution, current_user, require
from app.models import AuditEvent, Institution, Role, User
from app.schemas import InstitutionOut, InstitutionSettingsIn, Page, UserCreate, UserOut, UserUpdate
from app.security import encrypt_secret, hash_password, password_problem
from app.services import audit
from app.services.cbk_client import CBKError
from app.services.submissions import client_for

router = APIRouter(prefix="/api/institution", tags=["institution"])
INSTITUTION_ROLES = {Role.admin, Role.maker, Role.checker, Role.viewer}


@router.get("", response_model=InstitutionOut)
def get_institution(user: User = Depends(current_user), inst: Institution = Depends(current_institution)):
    return inst


@router.put("/settings", response_model=InstitutionOut)
def update_settings(body: InstitutionSettingsIn, user: User = Depends(require(Role.admin)),
                    inst: Institution = Depends(current_institution), db: Session = Depends(get_db)):
    changes = body.model_dump(exclude_unset=True)
    secret = changes.pop("cbk_client_secret", None)
    for k, v in changes.items():
        setattr(inst, k, v.strip() if isinstance(v, str) else v)
    if secret:
        inst.cbk_client_secret_enc = encrypt_secret(secret.strip())
    audit.record(db, user=user, action="institution.settings_updated", entity_type="institution", entity_id=inst.id,
                 fields=sorted(list(changes) + (["cbk_client_secret"] if secret else [])))
    db.commit()
    return inst


@router.post("/test-connection")
async def test_connection(user: User = Depends(require(Role.admin)), inst: Institution = Depends(current_institution),
                          db: Session = Depends(get_db)):
    if not inst.has_credentials:
        raise HTTPException(400, "Save a CBK client ID and secret first.")
    try:
        await client_for(inst).check_login()
        ok, message = True, f"Signed in to CBK {inst.environment.upper()} successfully."
    except (CBKError, RuntimeError) as exc:
        ok, message = False, str(exc)
    audit.record(db, user=user, action="institution.connection_tested", entity_type="institution", entity_id=inst.id, ok=ok)
    db.commit()
    return {"ok": ok, "message": message}


# --- users --------------------------------------------------------------------
@router.get("/users", response_model=list[UserOut])
def list_users(user: User = Depends(require(Role.admin)), inst: Institution = Depends(current_institution),
               db: Session = Depends(get_db)):
    return db.scalars(select(User).where(User.institution_id == inst.id).order_by(User.full_name)).all()


@router.post("/users", response_model=UserOut, status_code=201)
def create_user(body: UserCreate, user: User = Depends(require(Role.admin)), inst: Institution = Depends(current_institution),
                db: Session = Depends(get_db)):
    if body.role not in INSTITUTION_ROLES:
        raise HTTPException(400, "Choose admin, maker, checker or viewer.")
    if problem := password_problem(body.password):
        raise HTTPException(400, problem)
    email = body.email.strip().lower()
    if "@" not in email:
        raise HTTPException(400, "Enter a valid email address.")
    if db.scalar(select(User).where(func.lower(User.email) == email)):
        raise HTTPException(409, "A user with this email already exists.")
    new = User(institution_id=inst.id, email=email, full_name=body.full_name.strip(), role=body.role.value,
               password_hash=hash_password(body.password))
    db.add(new)
    db.flush()
    audit.record(db, user=user, action="user.created", entity_type="user", entity_id=new.id, email=email, role=new.role)
    db.commit()
    return new


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(user_id: str, body: UserUpdate, user: User = Depends(require(Role.admin)),
                inst: Institution = Depends(current_institution), db: Session = Depends(get_db)):
    target = db.get(User, user_id)
    if target is None or target.institution_id != inst.id:
        raise HTTPException(404, "User not found.")
    changes = body.model_dump(exclude_unset=True)
    if target.id == user.id and (changes.get("is_active") is False or changes.get("role") not in (None, Role.admin)):
        raise HTTPException(400, "You can't deactivate yourself or remove your own admin role.")
    if "role" in changes and changes["role"] is not None:
        if changes["role"] not in INSTITUTION_ROLES:
            raise HTTPException(400, "Choose admin, maker, checker or viewer.")
        target.role = changes["role"].value
    if changes.get("full_name"):
        target.full_name = changes["full_name"].strip()
    if "is_active" in changes and changes["is_active"] is not None:
        target.is_active = changes["is_active"]
    if changes.get("password"):
        if problem := password_problem(changes["password"]):
            raise HTTPException(400, problem)
        target.password_hash = hash_password(changes["password"])
    audit.record(db, user=user, action="user.updated", entity_type="user", entity_id=target.id,
                 fields=sorted(k for k in changes if k != "password") + (["password"] if changes.get("password") else []))
    db.commit()
    return target


# --- audit log ------------------------------------------------------------------
@router.get("/audit", response_model=Page)
def audit_log(page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200),
              user: User = Depends(require(Role.admin, Role.checker)), inst: Institution = Depends(current_institution),
              db: Session = Depends(get_db)):
    stmt = select(AuditEvent).where(AuditEvent.institution_id == inst.id)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(AuditEvent.created_at.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    items = [{"id": e.id, "at": e.created_at, "action": e.action, "entity_type": e.entity_type, "entity_id": e.entity_id,
              "by": e.user.full_name if e.user else "System", "detail": e.detail} for e in rows]
    return Page(items=items, total=total, page=page, page_size=page_size)
