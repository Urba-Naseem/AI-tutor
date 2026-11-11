"""US-1.4 - Resolve which attainment criterion applies to a CLO (now or at a past moment)."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..db import utcnow
from ..models.criteria import DEFAULT_THRESHOLD, AttainmentCriterion
from ..models.outcomes import CLO, Course, Program

ORDER = ("clo", "course", "program", "global")


def scope_keys_for_clo(db: Session, clo: CLO) -> dict[str, str]:
    course = db.get(Course, clo.course_id)
    program = db.get(Program, course.program_id)
    return {
        "clo": f"clo:{course.code}/{clo.code}",
        "course": f"course:{course.code}",
        "program": f"program:{program.code}",
        "global": "global",
    }


def in_force(db: Session, scope_key: str, at: datetime | None = None) -> AttainmentCriterion | None:
    at = at or utcnow()
    return db.scalar(
        select(AttainmentCriterion)
        .where(AttainmentCriterion.scope_key == scope_key, AttainmentCriterion.effective_from <= at,
               or_(AttainmentCriterion.superseded_at.is_(None), AttainmentCriterion.superseded_at > at))
        .order_by(AttainmentCriterion.version_no.desc())
        .limit(1)
    )


def ensure_default(db: Session) -> AttainmentCriterion:
    row = db.scalar(select(AttainmentCriterion).where(AttainmentCriterion.scope_key == "global").limit(1))
    if row is None:
        row = AttainmentCriterion(scope_type="global", scope_key="global", version_no=1, threshold=DEFAULT_THRESHOLD,
                                  reason="Institutional default (60%)", created_by=None,
                                  effective_from=datetime(2000, 1, 1))
        db.add(row)
        db.flush()
    return row


def resolve(db: Session, clo: CLO, at: datetime | None = None) -> dict:
    """Most specific criterion in force: CLO > course > programme > global."""
    ensure_default(db)
    keys = scope_keys_for_clo(db, clo)
    chain = []
    chosen = None
    for level in ORDER:
        row = in_force(db, keys[level], at)
        chain.append({"level": level, "scope_key": keys[level],
                      "threshold": row.threshold if row else None, "criterion_id": row.id if row else None})
        if chosen is None and row is not None and row.threshold is not None:
            chosen = row
    return {"threshold": chosen.threshold, "criterion_id": chosen.id, "version_no": chosen.version_no,
            "scope_key": chosen.scope_key, "chain": chain}


def set_criterion(db: Session, scope_type: str, scope_key: str, threshold: float | None, reason: str, user_id: int | None) -> AttainmentCriterion:
    now = utcnow()
    current = in_force(db, scope_key, now)
    last = db.scalar(select(AttainmentCriterion.version_no).where(AttainmentCriterion.scope_key == scope_key)
                     .order_by(AttainmentCriterion.version_no.desc()).limit(1)) or 0
    if current:
        current.superseded_at = now
    row = AttainmentCriterion(scope_type=scope_type, scope_key=scope_key, version_no=last + 1, threshold=threshold,
                              reason=reason, created_by=user_id, effective_from=now)
    db.add(row)
    db.flush()
    return row


def scope_key(db: Session, scope_type: str, ref_id: int | None) -> str:
    if scope_type == "global":
        return "global"
    if scope_type == "program":
        p = db.get(Program, ref_id)
        return f"program:{p.code}" if p else ""
    if scope_type == "course":
        c = db.get(Course, ref_id)
        return f"course:{c.code}" if c else ""
    if scope_type == "clo":
        o = db.get(CLO, ref_id)
        if not o:
            return ""
        return f"clo:{db.get(Course, o.course_id).code}/{o.code}"
    return ""
