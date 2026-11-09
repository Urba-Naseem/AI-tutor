"""US-3.1 - Capture learning and audit events.

Every event is attributable (actor + role), timestamped, linked to the entity it
concerns, and chained with SHA-256 (each record stores the previous record's
hash) so any tampering is detectable with `verify_chain`.
"""
from __future__ import annotations

import hashlib
import json
from contextvars import ContextVar
from itertools import count

from sqlalchemy import event, select, text
from sqlalchemy.orm import Session

from ..db import utcnow
from ..models.audit import AuditEvent

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)

GENESIS = "0" * 64
CATEGORY_BY_PREFIX = {"auth.": "security", "authz.": "security", "learn.": "learning", "ai.": "ai"}
_seq = count()


def _digest(prev: str, ev: AuditEvent) -> str:
    payload = json.dumps(
        [prev, ev.at.isoformat(), ev.category, ev.action, ev.actor_id, ev.actor_role, ev.entity_type,
         ev.entity_id, ev.course_id, ev.details],
        sort_keys=True, default=str,
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def _pending(db: Session) -> list:
    """Audit events of this transaction not yet in the database: they are added only at commit, under the chain
    lock, so a long request (slow AI call, early flushes) can never fork the chain with a background job."""
    return db.info.setdefault("audit_pending", [])


def _last_hash(db: Session) -> str:
    pending = _pending(db) or [o for o in db.new if isinstance(o, AuditEvent)]
    if pending:
        return max(pending, key=lambda e: e._seq).hash
    return db.scalar(select(AuditEvent.hash).order_by(AuditEvent.id.desc()).limit(1)) or GENESIS


AUDIT_CHAIN_LOCK = 0x41554454  # advisory-lock key for appending to the audit chain ("AUDT")


def _lock_chain(session: Session) -> None:
    """Hold the chain until this transaction commits, so two requests can never link to the same previous event."""
    name = session.get_bind().dialect.name
    if name == "postgresql":
        session.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": AUDIT_CHAIN_LOCK})
    elif name == "sqlite":
        # a no-op write takes SQLite's write lock now instead of at flush time
        session.execute(text("UPDATE audit_events SET id = id WHERE 0"))


@event.listens_for(Session, "before_commit")
def _chain_at_commit(session: Session) -> None:
    """Re-link this transaction's new audit events to the latest committed one, under the chain lock. The lock is
    taken only here, at commit, so it is held for the final flush and commit alone."""
    pending = sorted(session.info.pop("audit_pending", []) + [o for o in session.new if isinstance(o, AuditEvent)],
                     key=lambda e: e._seq)
    if not pending:
        return
    _lock_chain(session)
    with session.no_autoflush:  # the pending events must not be written before they are re-linked
        prev = session.scalar(select(AuditEvent.hash).order_by(AuditEvent.id.desc()).limit(1)) or GENESIS
    for ev in pending:
        ev.prev_hash = prev
        ev.hash = _digest(prev, ev)
        prev = ev.hash
        if ev not in session:
            session.add(ev)  # written by this commit's flush, right after the lock


@event.listens_for(Session, "after_rollback")
def _drop_pending(session: Session) -> None:
    session.info.pop("audit_pending", None)  # a rolled-back change leaves no audit record


def record(db: Session, actor, action: str, entity_type: str | None = None, entity_id: int | None = None,
           details: dict | None = None, course_id: int | None = None, category: str | None = None) -> AuditEvent:
    """Add an event to the session (committed together with the change it describes)."""
    if category is None:
        category = next((c for p, c in CATEGORY_BY_PREFIX.items() if action.startswith(p)), "audit")
    ev = AuditEvent(
        at=utcnow(), category=category, action=action,
        actor_id=getattr(actor, "id", None), actor_role=getattr(actor, "role", None),
        entity_type=entity_type, entity_id=entity_id, course_id=course_id,
        details=json.loads(json.dumps(details or {}, default=str)), request_id=request_id_var.get(),
    )
    ev.prev_hash = _last_hash(db)
    ev.hash = _digest(ev.prev_hash, ev)
    ev._seq = next(_seq)
    _pending(db).append(ev)  # added to the session at commit (see _chain_at_commit)
    return ev


def learning(db: Session, student, action: str, entity_type: str, entity_id: int | None, details: dict | None = None,
             course_id: int | None = None) -> AuditEvent:
    """Learning activity (answers, hints, page views, path decisions)."""
    name = action if action.startswith("learn.") else f"learn.{action}"
    return record(db, student, name, entity_type, entity_id, details, course_id, category="learning")


def verify_chain(db: Session) -> dict:
    """Walk the chain. Any record whose contents do not match its own hash = tampering (BROKEN). A record whose
    contents are intact but which links to an EARLIER record instead of the one just before it is a fork: two
    records were saved at the same moment (possible before the commit-time chain lock). Forks are reported by
    record number but do not hide tampering - the walk continues and still stops at any altered record."""
    prev = GENESIS
    seen = {GENESIS}
    forks: list[int] = []
    n = 0
    for ev in db.scalars(select(AuditEvent).order_by(AuditEvent.id)):
        intact = _digest(ev.prev_hash, ev) == ev.hash
        if not intact:
            return {"valid": False, "broken_at": ev.id, "checked": n, "forks": forks}
        if ev.prev_hash != prev:
            if ev.prev_hash not in seen:  # links to nothing we have seen: a record was removed or replaced
                return {"valid": False, "broken_at": ev.id, "checked": n, "forks": forks}
            forks.append(ev.id)
        prev = ev.hash
        seen.add(ev.hash)
        n += 1
    return {"valid": True, "checked": n, "forks": forks}
