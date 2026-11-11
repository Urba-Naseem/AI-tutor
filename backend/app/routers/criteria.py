"""US-1.4 - Configure attainment criteria (60% default, scoped overrides, versioned)."""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.audit import record
from ..core.rbac import ensure_course_access, require
from ..db import get_db
from ..models.criteria import AttainmentCriterion
from ..models.outcomes import CLO, Course
from ..models.user import User
from ..services import criteria as svc

router = APIRouter(prefix="/api/criteria", tags=["criteria"])


class CriterionIn(BaseModel):
    scope_type: str  # global | program | course | clo
    ref_id: int | None = None  # programme / course / CLO id (not needed for global)
    threshold: float = Field(ge=1, le=100)
    reason: str


class RemoveIn(BaseModel):
    reason: str


def out(r: AttainmentCriterion, names: dict | None = None) -> dict:
    return {"id": r.id, "scope_type": r.scope_type, "scope_key": r.scope_key, "version_no": r.version_no,
            "threshold": r.threshold, "reason": r.reason, "created_by": r.created_by,
            "created_by_name": (names or {}).get(r.created_by), "effective_from": r.effective_from,
            "superseded_at": r.superseded_at, "current": r.superseded_at is None}


@router.get("")
def list_criteria(db: Session = Depends(get_db), _=Depends(require("criteria:manage", "reports:read"))):
    svc.ensure_default(db)
    db.commit()
    rows = db.scalars(select(AttainmentCriterion).order_by(AttainmentCriterion.scope_key, AttainmentCriterion.version_no.desc())).all()
    names = {u.id: u.full_name for u in db.scalars(select(User))}
    return {"current": [out(r, names) for r in rows if r.superseded_at is None and r.threshold is not None],
            "history": [out(r, names) for r in rows]}


@router.post("", status_code=201)
def set_criterion(body: CriterionIn, db: Session = Depends(get_db), user: User = Depends(require("criteria:manage"))):
    if body.scope_type not in svc.ORDER:
        raise HTTPException(422, f"scope_type must be one of {svc.ORDER}")
    if len(body.reason.strip()) < 5:
        raise HTTPException(422, "A reason is required for every criteria change")
    key = svc.scope_key(db, body.scope_type, body.ref_id)
    if not key:
        raise HTTPException(404, "Scope not found")
    svc.ensure_default(db)
    before = svc.in_force(db, key)
    row = svc.set_criterion(db, body.scope_type, key, body.threshold, body.reason, user.id)
    record(db, user, "criteria.changed", "attainment_criterion", row.id,
           {"scope_key": key, "before": before.threshold if before else None, "after": body.threshold,
            "version_no": row.version_no, "reason": body.reason})
    db.commit()
    return out(row)


@router.post("/remove/{scope_type}/{ref_id}")
def remove_override(scope_type: str, ref_id: int, body: RemoveIn, db: Session = Depends(get_db), user: User = Depends(require("criteria:manage"))):
    """Remove an override: a new version with no threshold, so the wider scope applies again."""
    if scope_type == "global":
        raise HTTPException(409, "The institutional default cannot be removed, only changed")
    key = svc.scope_key(db, scope_type, ref_id)
    cur = svc.in_force(db, key) if key else None
    if not cur or cur.threshold is None:
        raise HTTPException(404, "No override in force for this scope")
    row = svc.set_criterion(db, scope_type, key, None, body.reason, user.id)
    record(db, user, "criteria.override_removed", "attainment_criterion", row.id, {"scope_key": key, "reason": body.reason})
    db.commit()
    return out(row)


@router.get("/effective/course/{course_id}")
def effective_for_course(course_id: int, at: datetime | None = None, db: Session = Depends(get_db),
                         user: User = Depends(require("criteria:manage", "reports:read", "learn"))):
    """Threshold that applies to each CLO of a course - now, or at a past moment (`at`)."""
    c = db.get(Course, course_id)
    if not c:
        raise HTTPException(404, "Course not found")
    ensure_course_access(db, user, course_id)
    res = []
    for clo in db.scalars(select(CLO).where(CLO.course_id == course_id).order_by(CLO.code)):
        r = svc.resolve(db, clo, at)
        res.append({"clo_id": clo.id, "clo_code": clo.code, **r})
    db.commit()
    return {"course_id": c.id, "course_code": c.code, "at": at, "clos": res}
