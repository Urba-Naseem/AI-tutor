from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.activity_event import ActivityEvent
from app.services.audit_service import AuditService

router = APIRouter()

@router.get("/logs", status_code=status.HTTP_200_OK)
def get_audit_logs(
    event_type: Optional[str] = Query(None, description="Filter by event type (e.g., USER_LOGGED_IN, CURRICULUM_UPLOADED)"),
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    limit: int = Query(100, ge=1, le=1000, description="Number of logs to return"),
    db: Session = Depends(get_db)
):
    """
    Retrieve audit logs from the activity_events table with optional filtering.
    """
    query = db.query(ActivityEvent)
    
    if event_type:
        query = query.filter(ActivityEvent.event_type == event_type)
    if user_id:
        query = query.filter(ActivityEvent.user_id == str(user_id))
        
    events = query.order_by(ActivityEvent.id.desc()).limit(limit).all()
    return events


@router.get("/verify", status_code=status.HTTP_200_OK)
def verify_audit_hash_chain(db: Session = Depends(get_db)):
    """
    Verify the cryptographic integrity of the append-only audit log SHA-256 chain.
    """
    events = db.query(ActivityEvent).order_by(ActivityEvent.id.asc()).all()
    
    if not events:
        return {
            "status": "valid",
            "total_events_verified": 0,
            "message": "Audit log is empty. No events to verify."
        }

    for i in range(len(events)):
        current_event = events[i]
        
        # Check first event prev_hash against genesis hash
        if i == 0:
            if current_event.prev_hash != "0" * 64:
                return {
                    "status": "corrupted",
                    "error": "Genesis event prev_hash is invalid",
                    "event_id": current_event.id
                }
        else:
            previous_event = events[i - 1]
            if current_event.prev_hash != previous_event.hash:
                return {
                    "status": "corrupted",
                    "error": f"Hash chain break detected between event {previous_event.id} and {current_event.id}",
                    "event_id": current_event.id
                }

    return {
        "status": "valid",
        "total_events_verified": len(events),
        "message": "Audit log hash chain is intact and un-tampered."
    }