"""US-3.1 - Append-only audit and learning event records."""
from datetime import datetime

from sqlalchemy import JSON, DateTime, Integer, String, event, text
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base, utcnow


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    category: Mapped[str] = mapped_column(String(20), index=True)  # audit | learning | ai | security
    action: Mapped[str] = mapped_column(String(80), index=True)
    actor_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    actor_role: Mapped[str | None] = mapped_column(String(20), nullable=True)
    entity_type: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    course_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    request_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    prev_hash: Mapped[str] = mapped_column(String(64))
    hash: Mapped[str] = mapped_column(String(64))


@event.listens_for(AuditEvent, "before_update")
def _no_update(*_):
    raise PermissionError("Audit events are append-only")


@event.listens_for(AuditEvent, "before_delete")
def _no_delete(*_):
    raise PermissionError("Audit events are append-only")


def install_guards(engine):
    """Database triggers so even raw SQL cannot alter or remove audit records."""
    if engine.dialect.name == "postgresql":
        with engine.begin() as conn:
            conn.execute(text(
                "CREATE OR REPLACE FUNCTION audit_append_only() RETURNS trigger LANGUAGE plpgsql AS "
                "$$ BEGIN RAISE EXCEPTION 'audit_events is append-only'; END; $$"))
            have = set(conn.execute(text("SELECT tgname FROM pg_trigger WHERE tgrelid = 'audit_events'::regclass")).scalars())
            for op in ("UPDATE", "DELETE"):
                # only create what is missing: dropping and re-creating needs an exclusive lock on the table at
                # every start, which waits for any open reader
                if f"audit_no_{op.lower()}" not in have:
                    conn.execute(text(
                        f"CREATE TRIGGER audit_no_{op.lower()} BEFORE {op} ON audit_events "
                        "FOR EACH ROW EXECUTE FUNCTION audit_append_only()"))
        return
    if engine.dialect.name != "sqlite":
        return
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TRIGGER IF NOT EXISTS audit_no_update BEFORE UPDATE ON audit_events "
            "BEGIN SELECT RAISE(ABORT, 'audit_events is append-only'); END;"))
        conn.execute(text(
            "CREATE TRIGGER IF NOT EXISTS audit_no_delete BEFORE DELETE ON audit_events "
            "BEGIN SELECT RAISE(ABORT, 'audit_events is append-only'); END;"))
