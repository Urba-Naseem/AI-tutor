import pytest
from sqlalchemy.orm import Session
from sqlalchemy.exc import InternalError
from app.db.session import SessionLocal, engine, Base
from app.models.activity_event import ActivityEvent
from app.services.audit_service import AuditService

@pytest.fixture(scope="module")
def db():
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    yield session
    session.close()

def test_event_insertion_and_hash_generation(db: Session):
    """Verifies that inserting an event generates valid prev_hash and hash via trigger."""
    event = ActivityEvent(
        event_type="TEST_INITIALIZATION",
        details={"test_key": "test_value"},
        prev_hash="",
        hash=""
    )
    db.add(event)
    db.commit()
    db.refresh(event)

    assert event.id is not None
    assert len(event.prev_hash) == 64
    assert len(event.hash) == 64

def test_prevent_update_operation(db: Session):
    """AIT-47: Asserts that UPDATE queries fail via database trigger."""
    event = db.query(ActivityEvent).first()
    assert event is not None

    with pytest.raises(InternalError) as exc_info:
        event.event_type = "ILLEGAL_MODIFICATION"
        db.commit()
    
    db.rollback()
    assert "append-only" in str(exc_info.value)

def test_prevent_delete_operation(db: Session):
    """AIT-47: Asserts that DELETE queries fail via database trigger."""
    event = db.query(ActivityEvent).first()
    assert event is not None

    with pytest.raises(InternalError) as exc_info:
        db.delete(event)
        db.commit()

    db.rollback()
    assert "append-only" in str(exc_info.value)

def test_hash_chain_integrity_verification(db: Session):
    """AIT-47: Verifies that a valid sequential log returns SECURE status."""
    # Insert secondary event
    event2 = ActivityEvent(
        event_type="TEST_SECOND_EVENT",
        details={"step": 2},
        prev_hash="",
        hash=""
    )
    db.add(event2)
    db.commit()

    verification = AuditService.verify_chain_integrity(db)
    assert verification["status"] == "SECURE"
    assert verification["total_records_verified"] >= 2