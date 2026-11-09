"""US-2.1 - Register and verify students (unique identity, institutional e-mail, consent)."""
import hashlib
import re
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..core.audit import record
from ..core.crypto import get_keyring
from ..core.deps import client_ip, get_current_user
from ..core.security import check_password_policy, hash_password, new_token, sha256
from ..db import get_db, utcnow
from ..models.consent import ConsentRecord
from ..models.user import OneTimeToken, User
from ..services.email import send_email

router = APIRouter(prefix="/api/auth", tags=["registration"])

CONSENT_TEXT = """AI Tutor - Student data and learning analytics consent

By creating an account you agree that the university may:
1. Store your name, student number and institutional e-mail (encrypted) to provide this service.
2. Record your learning activity (answers, attempts, hints, progress) to measure attainment of course outcomes.
3. Send parts of your questions to an AI model (Google Gemini) to generate tutoring responses grounded in approved course material. No answer keys or grades are shared.
4. Show your progress to the instructors of the courses you are enrolled in and to authorised staff.

You can withdraw consent at any time from "My account"; learning features are then paused until you consent again.
Your records are retained according to the university's records policy."""
STUDENT_NO = re.compile(r"^[A-Za-z0-9-]{4,20}$")


def consent_hash() -> str:
    return hashlib.sha256(CONSENT_TEXT.encode()).hexdigest()


def domain_allowed(email: str) -> bool:
    dom = email.rsplit("@", 1)[-1].lower()
    allowed = get_settings().allowed_email_domain.lower()
    return dom == allowed or dom.endswith("." + allowed)


class RegisterIn(BaseModel):
    student_number: str
    full_name: str
    email: EmailStr
    password: str
    consent: bool
    consent_version: str
    program_code: str | None = None  # department; required once departments exist


@router.get("/programs")
def public_programs(db: Session = Depends(get_db)):
    """Departments a new student can choose (public: shown on the registration form)."""
    from ..services import departments

    return departments.programs(db)


class TokenIn(BaseModel):
    token: str


class EmailIn(BaseModel):
    email: EmailStr


class ConsentIn(BaseModel):
    consent_version: str


def _send_verification(db: Session, user: User):
    s = get_settings()
    raw = new_token()
    db.add(OneTimeToken(user_id=user.id, purpose="verify", token_hash=sha256(raw),
                        expires_at=utcnow() + timedelta(hours=s.verify_token_hours)))
    send_email(user.email, "Verify your AI Tutor account",
               f"Hello {user.full_name},\n\nConfirm your institutional e-mail to activate your account "
               f"(valid {s.verify_token_hours} hours):\n{s.frontend_url}/verify-email?token={raw}\n")


@router.get("/consent")
def consent_text():
    return {"version": get_settings().consent_version, "text": CONSENT_TEXT, "allowed_domain": get_settings().allowed_email_domain}


@router.post("/register", status_code=201)
def register(body: RegisterIn, request: Request, db: Session = Depends(get_db)):
    s = get_settings()
    if not domain_allowed(body.email):
        raise HTTPException(422, f"Use your institutional e-mail address (@{s.allowed_email_domain})")
    if not STUDENT_NO.match(body.student_number.strip()):
        raise HTTPException(422, "Student number must be 4-20 letters, digits or dashes")
    if len(body.full_name.strip()) < 2:
        raise HTTPException(422, "Enter your full name")
    if not body.consent or body.consent_version != s.consent_version:
        raise HTTPException(422, "You must accept the current consent statement to register")
    check_password_policy(body.password)
    from ..services import departments

    choices = departments.programs(db)
    if choices and not departments.valid(db, body.program_code):
        raise HTTPException(422, "Choose your department")
    eh = get_keyring().blind_index(body.email)
    sn = body.student_number.strip().upper()
    if db.scalar(select(User).where(User.email_hash == eh)):
        raise HTTPException(409, "An account with this e-mail already exists")
    if db.scalar(select(User).where(User.student_number == sn)):
        raise HTTPException(409, "This student number is already registered")
    now = utcnow()
    u = User(role="student", email=body.email.lower(), email_hash=eh, full_name=body.full_name.strip(), student_number=sn,
             password_hash=hash_password(body.password), email_verified=False, consent_version=s.consent_version, consent_at=now,
             program_code=body.program_code if choices else None)
    db.add(u)
    db.flush()
    db.add(ConsentRecord(user_id=u.id, version=s.consent_version, text_sha256=consent_hash(), accepted_at=now, ip=client_ip(request)))
    _send_verification(db, u)
    record(db, u, "student.registered", "user", u.id, {"consent_version": s.consent_version, "program_code": u.program_code})
    db.commit()
    return {"ok": True, "message": "Check your institutional e-mail to verify your account."}


@router.post("/verify-email")
def verify_email(body: TokenIn, db: Session = Depends(get_db)):
    tok = db.scalar(select(OneTimeToken).where(OneTimeToken.token_hash == sha256(body.token), OneTimeToken.purpose == "verify"))
    if not tok or tok.used_at or tok.expires_at < utcnow():
        raise HTTPException(400, "Verification link is invalid or has expired - request a new one")
    u = db.get(User, tok.user_id)
    u.email_verified = True
    tok.used_at = utcnow()
    record(db, u, "student.email_verified", "user", u.id, {})
    db.commit()
    return {"ok": True}


@router.post("/resend-verification")
def resend(body: EmailIn, db: Session = Depends(get_db)):
    u = db.scalar(select(User).where(User.email_hash == get_keyring().blind_index(body.email)))
    if u and not u.email_verified:
        _send_verification(db, u)
        db.commit()
    return {"ok": True, "message": "If the account needs verification, a new link has been sent."}


@router.get("/my-consent")
def my_consent(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    hist = db.scalars(select(ConsentRecord).where(ConsentRecord.user_id == user.id).order_by(ConsentRecord.id.desc())).all()
    return {"current_version": get_settings().consent_version, "consented": consent_ok(user),
            "history": [{"version": c.version, "accepted_at": c.accepted_at, "withdrawn_at": c.withdrawn_at} for c in hist]}


@router.post("/my-consent/withdraw")
def withdraw(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    for c in db.scalars(select(ConsentRecord).where(ConsentRecord.user_id == user.id, ConsentRecord.withdrawn_at.is_(None))):
        c.withdrawn_at = utcnow()
    user.consent_at = None
    user.consent_version = None
    record(db, user, "student.consent_withdrawn", "user", user.id, {})
    db.commit()
    return {"ok": True}


@router.post("/my-consent/accept")
def accept(body: ConsentIn, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    s = get_settings()
    if body.consent_version != s.consent_version:
        raise HTTPException(422, "Accept the current consent version")
    now = utcnow()
    db.add(ConsentRecord(user_id=user.id, version=s.consent_version, text_sha256=consent_hash(), accepted_at=now, ip=client_ip(request)))
    user.consent_at, user.consent_version = now, s.consent_version
    record(db, user, "student.consent_given", "user", user.id, {"version": s.consent_version})
    db.commit()
    return {"ok": True}


def consent_ok(user: User) -> bool:
    return user.role != "student" or (user.consent_at is not None and user.consent_version == get_settings().consent_version)


def require_consent(user: User = Depends(get_current_user)) -> User:
    """Dependency for learning features: students must hold current consent."""
    if not consent_ok(user):
        raise HTTPException(403, "Please review and accept the current consent statement in My account to continue learning")
    return user
