from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Institution, Role, User
from app.security import decode_access_token

bearer = HTTPBearer(auto_error=False)


def current_user(creds: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)) -> User:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not signed in.")
    payload = decode_access_token(creds.credentials)
    user = db.get(User, payload["sub"]) if payload else None
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Your session has expired. Sign in again.")
    if user.institution is not None and not user.institution.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Your institution's account is disabled.")
    return user


def require(*roles: Role):
    allowed = {r.value for r in roles}

    def checker(user: User = Depends(current_user)) -> User:
        if user.role not in allowed:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "You don't have permission to do that.")
        return user

    return checker


def current_institution(user: User = Depends(current_user)) -> Institution:
    """The institution the signed-in user belongs to. Platform admins have none."""
    if user.institution is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This action needs an institution user account.")
    return user.institution
