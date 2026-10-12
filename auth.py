from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import current_user
from app.models import User, utcnow
from app.schemas import ChangePasswordIn, LoginIn, TokenOut, UserOut
from app.security import create_access_token, hash_password, password_problem, verify_password
from app.services import audit

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Simple per-email lockout. For several API workers, move this to Redis.
_failures: dict[str, list[float]] = {}
MAX_FAILURES, WINDOW = 5, 15 * 60


def _locked(email: str) -> bool:
    now = time.time()
    recent = [t for t in _failures.get(email, []) if now - t < WINDOW]
    _failures[email] = recent
    return len(recent) >= MAX_FAILURES


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, db: Session = Depends(get_db)):
    email = body.email.strip().lower()
    if _locked(email):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many failed attempts. Try again in 15 minutes.")
    user = db.scalar(select(User).where(func.lower(User.email) == email))
    if user is None or not verify_password(body.password, user.password_hash) or not user.is_active:
        _failures.setdefault(email, []).append(time.time())
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Email or password is incorrect.")
    if user.institution is not None and not user.institution.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Your institution's account is disabled.")
    _failures.pop(email, None)
    user.last_login_at = utcnow()
    audit.record(db, user=user, action="user.login", entity_type="user", entity_id=user.id)
    db.commit()
    return TokenOut(access_token=create_access_token(user.id, user.role), user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user)):
    return user


@router.post("/change-password", status_code=204)
def change_password(body: ChangePasswordIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Current password is incorrect.")
    if problem := password_problem(body.new_password):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, problem)
    user.password_hash = hash_password(body.new_password)
    audit.record(db, user=user, action="user.password_changed", entity_type="user", entity_id=user.id)
    db.commit()
