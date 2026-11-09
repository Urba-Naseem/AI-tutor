"""US-2.3 - password hashing, access tokens, refresh sessions and throttling."""
from __future__ import annotations

import hashlib
import re
import secrets
import time

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import HTTPException

from ..config import get_settings

# Standard argon2id parameters; the automated test suite uses cheaper ones for speed only.
_ph = PasswordHasher(time_cost=1, memory_cost=1024, parallelism=1) if get_settings().app_env == "test" else PasswordHasher()


def hash_password(pw: str) -> str:
    return _ph.hash(pw)


def verify_password(pw: str, hashed: str) -> bool:
    try:
        return _ph.verify(hashed, pw)
    except (VerifyMismatchError, Exception):
        return False


def check_password_policy(pw: str) -> None:
    if len(pw) < 10 or not re.search(r"[A-Za-z]", pw) or not re.search(r"\d", pw):
        raise HTTPException(422, "Password must be at least 10 characters and contain letters and digits")


def sha256(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def new_token() -> str:
    return secrets.token_urlsafe(32)


def _secret() -> str:
    s = get_settings().jwt_secret
    if len(s) < 32:
        raise RuntimeError("JWT_SECRET missing or too short - run: python -m app.cli init-keys")
    return s


def create_access_token(user_id: int, role: str, session_id: int) -> str:
    now = int(time.time())
    payload = {
        "sub": str(user_id),
        "role": role,
        "sid": session_id,
        "iat": now,
        "exp": now + get_settings().access_token_minutes * 60,
        "typ": "access",
    }
    return jwt.encode(payload, _secret(), algorithm="HS256")


def decode_access_token(token: str) -> dict:
    try:
        data = jwt.decode(token, _secret(), algorithms=["HS256"], options={"verify_iat": False})
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Session expired")
    except jwt.PyJWTError:
        raise HTTPException(401, "Invalid token")
    if data.get("typ") != "access":
        raise HTTPException(401, "Invalid token")
    return data
