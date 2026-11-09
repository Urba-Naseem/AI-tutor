"""US-3.1 - Search the audit / learning event trail (admins and exam staff)."""
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..core.audit import verify_chain
from ..core.rbac import require
from ..db import get_db
from ..models.audit import AuditEvent
from ..models.user import User

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get("")
def search(
    record_id: int | None = None,
    record_from: int | None = None,
    record_to: int | None = None,
    category: str | None = None,
    action: str | None = None,
    actor_id: int | None = None,
    entity_type: str | None = None,
    entity_id: int | None = None,
    course_id: int | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    limit: int = Query(100, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
    _=Depends(require("audit:read")),
):
    q = select(AuditEvent)
    for col, val in ((AuditEvent.category, category), (AuditEvent.actor_id, actor_id),
                     (AuditEvent.entity_type, entity_type), (AuditEvent.entity_id, entity_id),
                     (AuditEvent.course_id, course_id)):
        if val is not None:
            q = q.where(col == val)
    if record_id is not None:  # "record #" - the event's number in the chain
        q = q.where(AuditEvent.id == record_id)
    if record_from is not None:
        q = q.where(AuditEvent.id >= record_from)
    if record_to is not None:
        q = q.where(AuditEvent.id <= record_to)
    if action:
        q = q.where(AuditEvent.action.like(f"{action}%"))
    if since:
        q = q.where(AuditEvent.at >= since)
    if until:
        q = q.where(AuditEvent.at <= until)
    total = db.scalar(select(func.count()).select_from(q.subquery()))
    rows = db.scalars(q.order_by(AuditEvent.id.desc()).limit(limit).offset(offset)).all()
    ids = {r.actor_id for r in rows if r.actor_id}
    names = {u.id: u.full_name for u in db.scalars(select(User).where(User.id.in_(ids)))} if ids else {}
    return {
        "total": total,
        "items": [
            {"id": r.id, "at": r.at, "category": r.category, "action": r.action, "actor_id": r.actor_id,
             "actor_name": names.get(r.actor_id), "actor_role": r.actor_role, "entity_type": r.entity_type,
             "entity_id": r.entity_id, "course_id": r.course_id, "details": r.details, "hash": r.hash[:12],
             "request_id": r.request_id}
            for r in rows
        ],
    }


@router.get("/verify")
def verify(db: Session = Depends(get_db), _=Depends(require("audit:read"))):
    return verify_chain(db)
