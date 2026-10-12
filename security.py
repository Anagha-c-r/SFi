"""Password hashing, login tokens and encryption of CBK client secrets."""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone

import jwt
from cryptography.fernet import Fernet, InvalidToken

from app.config import settings

# --- passwords (scrypt, standard library) ---------------------------------
_N, _R, _P = 2**14, 8, 1


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=_N, r=_R, p=_P, dklen=32)
    return f"scrypt${_N}${_R}${_P}${base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, n, r, p, salt_b64, digest_b64 = stored.split("$")
        digest = hashlib.scrypt(password.encode(), salt=base64.b64decode(salt_b64), n=int(n), r=int(r), p=int(p), dklen=32)
        return hmac.compare_digest(digest, base64.b64decode(digest_b64))
    except (ValueError, TypeError):
        return False


def password_problem(password: str) -> str | None:
    if len(password) < 10:
        return "Password must be at least 10 characters."
    if password.lower() == password or password.upper() == password or not any(c.isdigit() for c in password):
        return "Password must mix upper- and lower-case letters and include a number."
    return None


# --- login tokens -----------------------------------------------------------
def create_access_token(user_id: str, role: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": user_id, "role": role, "iat": now, "exp": now + timedelta(minutes=settings.jwt_minutes)}
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_access_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None


# --- secrets at rest --------------------------------------------------------
def _fernet() -> Fernet:
    key = settings.encryption_key
    if not key:
        if settings.is_production:
            raise RuntimeError("ENCRYPTION_KEY must be set in production.")
        # development fallback derived from the JWT secret so restarts keep working
        key = base64.urlsafe_b64encode(hashlib.sha256(settings.jwt_secret.encode()).digest()).decode()
    return Fernet(key.encode())


def encrypt_secret(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt_secret(value: str) -> str:
    try:
        return _fernet().decrypt(value.encode()).decode()
    except InvalidToken as exc:
        raise RuntimeError("Stored CBK secret cannot be decrypted; was ENCRYPTION_KEY changed?") from exc
