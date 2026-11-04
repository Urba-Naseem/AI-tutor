import json
import hashlib
from typing import Any, Dict, Optional
from fastapi import BackgroundTasks
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.models.activity_event import ActivityEvent

def log_audit_event(
    db: Session,
    event_type: str,
    user_id: Optional[str] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    ip_address: str = "127.0.0.1",
    **kwargs
) -> ActivityEvent:
    """Generates an attributable audit record protected by SHA-256 hash chaining (US-3.1)."""
    details = details or {}
    
    # 1. Fetch previous hash in chain
    last_event = db.query(ActivityEvent).order_by(ActivityEvent.id.desc()).first()
    prev_hash = last_event.hash if (last_event and last_event.hash) else "0" * 64

    details_str = json.dumps(details, sort_keys=True)

    # 2. Compute current event SHA-256 signature
    raw_payload = f"{user_id or ''}|{event_type}|{resource_type or ''}|{resource_id or ''}|{details_str}|{ip_address}|{prev_hash}"
    event_hash = hashlib.sha256(raw_payload.encode("utf-8")).hexdigest()

    # 3. Create database record
    audit_record = ActivityEvent(
        event_type=event_type,
        user_id=str(user_id) if user_id is not None else None,
        resource_type=resource_type,
        resource_id=str(resource_id) if resource_id is not None else None,
        details=details,
        ip_address=ip_address,
        prev_hash=prev_hash,
        hash=event_hash
    )
    db.add(audit_record)
    db.commit()
    db.refresh(audit_record)
    return audit_record


def _background_log_task(
    event_type: str,
    user_id: Optional[str] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    ip_address: str = "127.0.0.1"
):
    """Executes background audit logging with an isolated database session."""
    db = SessionLocal()
    try:
        log_audit_event(
            db=db,
            event_type=event_type,
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            ip_address=ip_address
        )
    finally:
        db.close()


class AuditService:
    @staticmethod
    def log_event(db: Session, *args, **kwargs):
        if "action" in kwargs and "event_type" not in kwargs:
            kwargs["event_type"] = kwargs.pop("action")
        return log_audit_event(db, *args, **kwargs)

    @staticmethod
    def emit_event_async(
        background_tasks: Optional[BackgroundTasks] = None,
        db: Optional[Session] = None,
        event_type: str = "GENERIC_EVENT",
        user_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        ip_address: str = "127.0.0.1",
        **kwargs
    ):
        """Asynchronous & background-safe audit logging gateway (US-3.1)."""
        action_type = kwargs.get("action", event_type)
        
        if background_tasks and isinstance(background_tasks, BackgroundTasks):
            background_tasks.add_task(
                _background_log_task,
                event_type=action_type,
                user_id=user_id,
                resource_type=resource_type,
                resource_id=resource_id,
                details=details,
                ip_address=ip_address
            )
        elif db:
            log_audit_event(
                db=db,
                event_type=action_type,
                user_id=user_id,
                resource_type=resource_type,
                resource_id=resource_id,
                details=details,
                ip_address=ip_address
            )
        else:
            _background_log_task(
                event_type=action_type,
                user_id=user_id,
                resource_type=resource_type,
                resource_id=resource_id,
                details=details,
                ip_address=ip_address
            )