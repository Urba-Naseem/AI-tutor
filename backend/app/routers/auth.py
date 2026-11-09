"""US-2.3 - Secure login and account recovery."""
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..core.crypto import get_keyring
from ..core.deps import client_ip, get_current_user
from ..core.security import (
    check_password_policy,
    create_access_token,
    hash_password,
    new_token,
    sha256,
    verify_password,
)
from ..db import get_db, utcnow
from ..models.user import AuthSession, LoginAttempt, OneTimeToken, User
from ..services.email import send_email

router = APIRouter(prefix="/api/auth", tags=["auth"])
COOKIE = "aitutor_refresh"


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class ForgotIn(BaseModel):
    email: EmailStr


class ResetIn(BaseModel):
    token: str
    new_password: str


class ChangePwIn(BaseModel):
    current_password: str
    new_password: str


def user_out(u: User) -> dict:
    return {
        "id": u.id,
        "email": u.email,
        "full_name": u.full_name,
        "role": u.role,
        "student_number": u.student_number,
        "email_verified": u.email_verified,
        "program_code": u.program_code,
        "office_hours": u.office_hours,
        "office_location": u.office_location,
        "about": u.about,
    }


def _audit(db, *args, **kwargs):
    """Write an audit event (US-3.1) in the same transaction as the change."""
    from ..core.audit import record

    record(db, *args, **kwargs)


def _issue_session(db: Session, user: User, response: Response, ip: str, family: str | None = None) -> str:
    s = get_settings()
    raw = new_token()
    sess = AuthSession(
        user_id=user.id,
        token_hash=sha256(raw),
        family=family or new_token()[:24],
        expires_at=utcnow() + timedelta(days=s.refresh_token_days),
        ip=ip,
    )
    db.add(sess)
    db.flush()
    response.set_cookie(
        COOKIE, raw, httponly=True, secure=True, samesite="strict", path="/api/auth",
        max_age=s.refresh_token_days * 86400,
    )
    return create_access_token(user.id, user.role, sess.id)


@router.post("/login")
def login(body: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    s = get_settings()
    ip = client_ip(request)
    eh = get_keyring().blind_index(body.email)
    now = utcnow()

    # throttle by source address: too many failures from one IP in the window
    window = now - timedelta(minutes=s.login_lock_minutes)
    ip_fails = db.scalar(
        select(func.count()).select_from(LoginAttempt).where(
            LoginAttempt.ip == ip, LoginAttempt.success.is_(False), LoginAttempt.at >= window
        )
    )
    if ip_fails >= s.ip_max_failures:
        raise HTTPException(429, "Too many failed attempts from this address. Try again later.")

    user = db.scalar(select(User).where(User.email_hash == eh))
    if user and user.locked_until and user.locked_until > now:
        mins = int((user.locked_until - now).total_seconds() // 60) + 1
        db.add(LoginAttempt(email_hash=eh, ip=ip, success=False))
        db.commit()
        raise HTTPException(423, f"Account temporarily locked. Try again in {mins} minute(s) or reset your password.")

    if not user or not verify_password(body.password, user.password_hash):
        db.add(LoginAttempt(email_hash=eh, ip=ip, success=False))
        if user:
            user.failed_logins += 1
            if user.failed_logins >= s.login_max_attempts:
                user.locked_until = now + timedelta(minutes=s.login_lock_minutes)
                user.failed_logins = 0
                _audit(db, user, "auth.account_locked", "user", user.id, {"ip": ip})
            _audit(db, user, "auth.login_failed", "user", user.id, {"ip": ip})
        db.commit()
        raise HTTPException(401, "Invalid email or password")

    if not user.is_active:
        raise HTTPException(403, "Account is disabled")
    if user.role == "student" and not user.email_verified:
        raise HTTPException(403, "Please verify your institutional e-mail before signing in")

    user.failed_logins = 0
    user.locked_until = None
    user.last_login_at = now
    db.add(LoginAttempt(email_hash=eh, ip=ip, success=True))
    token = _issue_session(db, user, response, ip)
    _audit(db, user, "auth.login", "user", user.id, {"ip": ip})
    db.commit()
    return {"access_token": token, "token_type": "bearer", "user": user_out(user)}


@router.post("/refresh")
def refresh(request: Request, response: Response, db: Session = Depends(get_db)):
    raw = request.cookies.get(COOKIE)
    if not raw:
        raise HTTPException(401, "No session")
    sess = db.scalar(select(AuthSession).where(AuthSession.token_hash == sha256(raw)))
    if not sess:
        raise HTTPException(401, "Invalid session")
    if sess.revoked_at is not None:
        # refresh-token reuse => possible theft: revoke the whole token family
        for other in db.scalars(select(AuthSession).where(AuthSession.family == sess.family)):
            other.revoked_at = other.revoked_at or utcnow()
        db.commit()
        raise HTTPException(401, "Session revoked")
    if sess.expires_at < utcnow():
        raise HTTPException(401, "Session expired")
    user = db.get(User, sess.user_id)
    if not user or not user.is_active:
        raise HTTPException(401, "Account disabled")
    sess.revoked_at = utcnow()  # rotate
    token = _issue_session(db, user, response, client_ip(request), family=sess.family)
    db.commit()
    return {"access_token": token, "token_type": "bearer", "user": user_out(user)}


@router.post("/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    raw = request.cookies.get(COOKIE)
    if raw:
        sess = db.scalar(select(AuthSession).where(AuthSession.token_hash == sha256(raw)))
        if sess and not sess.revoked_at:
            sess.revoked_at = utcnow()
            user = db.get(User, sess.user_id)
            _audit(db, user, "auth.logout", "user", sess.user_id, {})
            db.commit()
    response.delete_cookie(COOKIE, path="/api/auth")
    return {"ok": True}


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    from ..core.rbac import PERMISSIONS

    return {**user_out(user), "permissions": sorted(PERMISSIONS.get(user.role, set()))}


class ProfileIn(BaseModel):
    office_hours: str | None = None
    office_location: str | None = None
    about: str | None = None


@router.patch("/profile")
def update_profile(body: ProfileIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Staff contact details shown to their students (office hours, office, a short introduction)."""
    if user.role not in ("instructor", "admin"):
        raise HTTPException(403, "Only staff have a public profile")
    u = db.get(User, user.id)
    u.office_hours = (body.office_hours or "").strip()[:200] or None
    u.office_location = (body.office_location or "").strip()[:200] or None
    u.about = (body.about or "").strip()[:1500] or None
    _audit(db, u, "user.profile_updated", "user", u.id, {})
    db.commit()
    return user_out(u)


@router.post("/forgot-password")
def forgot_password(body: ForgotIn, db: Session = Depends(get_db)):
    """Always answers the same way so it cannot be used to discover accounts."""
    s = get_settings()
    user = db.scalar(select(User).where(User.email_hash == get_keyring().blind_index(body.email)))
    if user and user.is_active:
        raw = new_token()
        db.add(OneTimeToken(user_id=user.id, purpose="reset", token_hash=sha256(raw),
                            expires_at=utcnow() + timedelta(minutes=s.reset_token_minutes)))
        _audit(db, user, "auth.reset_requested", "user", user.id, {})
        db.commit()
        send_email(user.email, "AI Tutor password reset",
                   f"Hello {user.full_name},\n\nReset your password (valid {s.reset_token_minutes} minutes, single use):\n"
                   f"{s.frontend_url}/reset-password?token={raw}\n\nIf you did not ask for this, ignore this e-mail.")
    return {"ok": True, "message": "If the account exists, a reset link has been sent."}


@router.post("/reset-password")
def reset_password(body: ResetIn, db: Session = Depends(get_db)):
    tok = db.scalar(select(OneTimeToken).where(OneTimeToken.token_hash == sha256(body.token), OneTimeToken.purpose == "reset"))
    if not tok or tok.used_at or tok.expires_at < utcnow():
        raise HTTPException(400, "Reset link is invalid or has expired")
    check_password_policy(body.new_password)
    user = db.get(User, tok.user_id)
    user.password_hash = hash_password(body.new_password)
    user.failed_logins = 0
    user.locked_until = None
    tok.used_at = utcnow()
    for sess in db.scalars(select(AuthSession).where(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None))):
        sess.revoked_at = utcnow()
    _audit(db, user, "auth.password_reset", "user", user.id, {})
    db.commit()
    return {"ok": True}


@router.post("/change-password")
def change_password(body: ChangePwIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(400, "Current password is incorrect")
    check_password_policy(body.new_password)
    user = db.merge(user)
    user.password_hash = hash_password(body.new_password)
    _audit(db, user, "auth.password_changed", "user", user.id, {})
    db.commit()
    return {"ok": True}
