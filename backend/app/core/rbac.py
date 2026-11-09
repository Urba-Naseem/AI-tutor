"""US-11.1 - Roles and scopes, enforced on the server for every endpoint.

* Role -> permission table (what kind of action).
* Course scope (which data): admins see everything, exam staff can *read*
  everything, instructors only courses they are assigned to, students only
  courses they are enrolled in. Features register scope providers below.
"""
from __future__ import annotations

from typing import Callable

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..db import get_db
from ..models.user import User
from .deps import get_current_user

# Role definitions agreed with the product owner (2026-11-12):
# * admin - access control, curriculum upload/validate/version, attainment rules, academic setup (offerings,
#   prerequisites, terms, sections, faculty assignment, enrolment), mastery policy, audit and AI logs.
#   No teaching work: sources, content/question approval, console, reviews, escalations, paths, appeals and
#   mappings belong to instructors. reports:read keeps read-only views (e.g. rosters) available to setup pages.
# * instructor - teaching sources, content and question approval, AI review queue, console, escalations,
#   path control, appeals, CLO/unit corrections and CLO-PLO mappings (with course activation).
# * student - account, enrolment, diagnostic, path, content (+ error reports), quizzes, hints, reteach,
#   progress (+ download), appeals. Students and instructors keep the "Ask the tutor" chat (ai:use).
# * exam_staff - read-only: audit, reports, AI logs.
PERMISSIONS: dict[str, set[str]] = {
    "admin": {
        "users:manage", "audit:read", "ai:logs", "curriculum:manage", "outcomes:review", "criteria:manage",
        "offerings:manage", "enrollment:manage", "mastery:recalc", "reports:read",
    },
    "instructor": {
        "outcomes:review", "sources:manage", "sources:approve", "ai:use", "mappings:manage", "items:manage",
        "content:manage", "reports:read", "console:view", "paths:manage", "interventions:manage",
        "appeals:resolve", "course:activate",
    },
    "student": {"learn", "ai:use", "enroll:self", "appeals:submit", "progress:self"},
    "exam_staff": {"audit:read", "reports:read", "ai:logs"},
}


def has_perm(user: User, perm: str) -> bool:
    return perm in PERMISSIONS.get(user.role, set())


def _deny(db: Session, user: User | None, what: str, request: Request | None = None):
    from .audit import record

    record(db, user, "authz.denied", "permission", None,
           {"required": what, "path": request.url.path if request else None})
    db.commit()
    raise HTTPException(403, f"You do not have permission for this action ({what})")


def require(*perms: str) -> Callable:
    """Dependency: the current user must hold at least one of `perms`."""

    def dep(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> User:
        if not any(has_perm(user, p) for p in perms):
            _deny(db, user, " or ".join(perms), request)
        return user

    return dep


# ---- course scope ------------------------------------------------------
ScopeProvider = Callable[[Session, User], set[int]]
SCOPE_PROVIDERS: dict[str, list[ScopeProvider]] = {"instructor": [], "student": []}


def register_scope(role: str, fn: ScopeProvider | None = None):
    """Register a provider; usable directly or as a decorator."""

    def add(f: ScopeProvider) -> ScopeProvider:
        SCOPE_PROVIDERS.setdefault(role, []).append(f)
        return f

    return add(fn) if fn else add


def accessible_course_ids(db: Session, user: User) -> set[int] | None:
    """None means unrestricted."""
    if user.role in ("admin", "exam_staff"):
        return None
    ids: set[int] = set()
    for fn in SCOPE_PROVIDERS.get(user.role, []):
        ids |= fn(db, user)
    return ids


def ensure_course_access(db: Session, user: User, course_id: int, write: bool = False):
    if user.role == "admin":
        return
    if user.role == "exam_staff":
        if write:
            _deny(db, user, f"write course {course_id}")
        return
    ids = accessible_course_ids(db, user)
    if course_id not in ids:
        _deny(db, user, f"course {course_id} scope")
