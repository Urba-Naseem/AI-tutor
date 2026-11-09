"""US-11.1 - Administrators manage accounts and roles."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.crypto import get_keyring
from ..core.rbac import PERMISSIONS, require
from ..core.security import check_password_policy, hash_password
from ..db import get_db
from ..models.user import ROLES, AuthSession, User
from .auth import _audit, user_out

router = APIRouter(prefix="/api/users", tags=["users"])


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str
    role: str
    password: str
    student_number: str | None = None
    program_code: str | None = None


class UserUpdate(BaseModel):
    role: str | None = None
    is_active: bool | None = None
    full_name: str | None = None
    program_code: str | None = None
    reason: str | None = None  # required when moving a student to another department


def _full(u: User) -> dict:
    return {**user_out(u), "is_active": u.is_active, "created_at": u.created_at, "last_login_at": u.last_login_at,
            "locked": bool(u.locked_until)}


@router.get("")
def list_users(role: str | None = None, program: str | None = None, db: Session = Depends(get_db), _=Depends(require("users:manage"))):
    q = select(User).order_by(User.id)
    if role:
        q = q.where(User.role == role)
    if program == "none":
        q = q.where(User.role == "student", User.program_code.is_(None))
    elif program:
        q = q.where(User.program_code == program)
    return [_full(u) for u in db.scalars(q)]


@router.get("/programs")
def admin_programs(db: Session = Depends(get_db), _=Depends(require("users:manage"))):
    from ..services import departments

    return departments.programs(db)


@router.get("/roles")
def roles(_=Depends(require("users:manage"))):
    return {r: sorted(PERMISSIONS[r]) for r in ROLES}


@router.post("", status_code=201)
def create_user(body: UserCreate, db: Session = Depends(get_db), admin: User = Depends(require("users:manage"))):
    if body.role not in ROLES:
        raise HTTPException(422, f"Role must be one of {ROLES}")
    check_password_policy(body.password)
    eh = get_keyring().blind_index(body.email)
    if db.scalar(select(User).where(User.email_hash == eh)):
        raise HTTPException(409, "E-mail already in use")
    if body.student_number and db.scalar(select(User).where(User.student_number == body.student_number)):
        raise HTTPException(409, "Student number already in use")
    from ..services import departments

    if body.role == "student" and departments.programs(db) and not departments.valid(db, body.program_code):
        raise HTTPException(422, "Choose the student's department")
    u = User(role=body.role, email=body.email, email_hash=eh, full_name=body.full_name,
             password_hash=hash_password(body.password), email_verified=True, student_number=body.student_number,
             program_code=body.program_code if body.role == "student" else None)
    db.add(u)
    db.flush()
    _audit(db, admin, "user.created", "user", u.id, {"role": body.role, "program_code": u.program_code})
    db.commit()
    return _full(u)


@router.patch("/{user_id}")
def update_user(user_id: int, body: UserUpdate, db: Session = Depends(get_db), admin: User = Depends(require("users:manage"))):
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(404, "User not found")
    changes = {}
    if body.role is not None:
        if body.role not in ROLES:
            raise HTTPException(422, f"Role must be one of {ROLES}")
        if u.id == admin.id and body.role != "admin":
            raise HTTPException(400, "You cannot remove your own admin role")
        changes["role"] = [u.role, body.role]
        u.role = body.role
    if body.is_active is not None:
        if u.id == admin.id and not body.is_active:
            raise HTTPException(400, "You cannot deactivate yourself")
        changes["is_active"] = [u.is_active, body.is_active]
        u.is_active = body.is_active
    if body.full_name:
        u.full_name = body.full_name
        changes["full_name"] = "updated"
    if body.program_code is not None and body.program_code != u.program_code:
        from ..services import departments

        if u.role != "student":
            raise HTTPException(422, "Only students belong to a department")
        if not departments.valid(db, body.program_code):
            raise HTTPException(422, "Unknown department")
        if u.program_code and len((body.reason or "").strip()) < 5:
            raise HTTPException(422, "Give a reason for moving the student to another department")
        changes["program_code"] = [u.program_code, body.program_code]
        if body.reason:
            changes["reason"] = body.reason.strip()
        u.program_code = body.program_code
    if "role" in changes or body.is_active is False:
        # role or status change: existing sessions must re-authenticate
        for s in db.scalars(select(AuthSession).where(AuthSession.user_id == u.id, AuthSession.revoked_at.is_(None))):
            from ..db import utcnow

            s.revoked_at = utcnow()
    _audit(db, admin, "user.updated", "user", u.id, changes)
    db.commit()
    return _full(u)


@router.post("/{user_id}/unlock")
def unlock(user_id: int, db: Session = Depends(get_db), admin: User = Depends(require("users:manage"))):
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(404, "User not found")
    u.locked_until = None
    u.failed_logins = 0
    _audit(db, admin, "user.unlocked", "user", u.id, {})
    db.commit()
    return _full(u)
