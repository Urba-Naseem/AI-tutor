"""Identity: users, sessions, one-time tokens and login attempts."""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..core.crypto import EncryptedString
from ..db import Base, utcnow

ROLES = ("student", "instructor", "admin", "exam_staff")


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    role: Mapped[str] = mapped_column(String(20), index=True)
    # personal data is encrypted; email_hash (blind index) gives uniqueness + lookup
    email: Mapped[str] = mapped_column(EncryptedString())
    email_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(EncryptedString())
    student_number: Mapped[str | None] = mapped_column(String(32), unique=True, nullable=True)
    program_code: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)  # department (e.g. BSCS, BSSE)
    # what students see about their instructor (set by the instructor on their account page)
    office_hours: Mapped[str | None] = mapped_column(String(200), nullable=True)
    office_location: Mapped[str | None] = mapped_column(String(200), nullable=True)
    about: Mapped[str | None] = mapped_column(Text, nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    consent_version: Mapped[str | None] = mapped_column(String(20), nullable=True)
    consent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    failed_logins: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class AuthSession(Base):
    """A refresh-token session. Only a hash of the token is stored."""

    __tablename__ = "auth_sessions"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    family: Mapped[str] = mapped_column(String(32), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)


class OneTimeToken(Base):
    """Password-reset and e-mail verification tokens (hashed, single use, expiring)."""

    __tablename__ = "one_time_tokens"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    purpose: Mapped[str] = mapped_column(String(20))  # reset | verify
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class LoginAttempt(Base):
    __tablename__ = "login_attempts"
    id: Mapped[int] = mapped_column(primary_key=True)
    email_hash: Mapped[str] = mapped_column(String(64), index=True)
    ip: Mapped[str] = mapped_column(String(64), index=True)
    success: Mapped[bool] = mapped_column(Boolean)
    at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
