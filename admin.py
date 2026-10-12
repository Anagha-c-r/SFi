"""Platform admin (Finoworks staff): onboard and manage institutions."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require
from app.models import Institution, Role, Submission, User
from app.schemas import InstitutionCreate, InstitutionOut, InstitutionUpdate
from app.security import hash_password, password_problem
from app.services import audit

router = APIRouter(prefix="/api/admin", tags=["platform admin"])
admin_only = require(Role.platform_admin)


@router.get("/institutions")
def list_institutions(user: User = Depends(admin_only), db: Session = Depends(get_db)):
    counts = dict(db.execute(select(Submission.institution_id, func.count()).group_by(Submission.institution_id)).all())
    users = dict(db.execute(select(User.institution_id, func.count()).group_by(User.institution_id)).all())
    out = []
    for inst in db.scalars(select(Institution).order_by(Institution.name)).all():
        out.append({**InstitutionOut.model_validate(inst).model_dump(),
                    "submission_count": counts.get(inst.id, 0), "user_count": users.get(inst.id, 0)})
    return out


@router.post("/institutions", response_model=InstitutionOut, status_code=201)
def create_institution(body: InstitutionCreate, user: User = Depends(admin_only), db: Session = Depends(get_db)):
    code = body.institution_code.strip()
    if db.scalar(select(Institution).where(Institution.institution_code == code)):
        raise HTTPException(409, "An institution with this CBK code already exists.")
    email = body.admin_email.strip().lower()
    if db.scalar(select(User).where(func.lower(User.email) == email)):
        raise HTTPException(409, "A user with the admin email already exists.")
    if problem := password_problem(body.admin_password):
        raise HTTPException(400, problem)
    if body.environment not in ("uat", "prod"):
        raise HTTPException(400, "Environment must be uat or prod.")
    inst = Institution(name=body.name.strip(), institution_code=code, category=body.category, environment=body.environment)
    db.add(inst)
    db.flush()
    db.add(User(institution_id=inst.id, email=email, full_name=body.admin_full_name.strip(), role=Role.admin.value,
                password_hash=hash_password(body.admin_password)))
    audit.record(db, user=user, institution_id=inst.id, action="institution.created", entity_type="institution",
                 entity_id=inst.id, admin_email=email)
    db.commit()
    return inst


@router.patch("/institutions/{inst_id}", response_model=InstitutionOut)
def update_institution(inst_id: str, body: InstitutionUpdate, user: User = Depends(admin_only),
                       db: Session = Depends(get_db)):
    inst = db.get(Institution, inst_id)
    if inst is None:
        raise HTTPException(404, "Institution not found.")
    for k, v in body.model_dump(exclude_unset=True).items():
        if v is not None:
            setattr(inst, k, v)
    audit.record(db, user=user, institution_id=inst.id, action="institution.updated", entity_type="institution",
                 entity_id=inst.id, **body.model_dump(exclude_unset=True))
    db.commit()
    return inst
