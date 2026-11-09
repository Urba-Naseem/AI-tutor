"""US-13.2 - AI call trace and review routing."""
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..core.crypto import EncryptedString
from ..db import Base, utcnow


class AICall(Base):
    """Every model call (or attempted call): who, why, what was sent and received."""

    __tablename__ = "ai_calls"
    id: Mapped[int] = mapped_column(primary_key=True)
    at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    user_role: Mapped[str | None] = mapped_column(String(20), nullable=True)
    purpose: Mapped[str] = mapped_column(String(60), index=True)
    course_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    model: Mapped[str] = mapped_column(String(80))
    # ok | fallback (model unavailable, offline result used) | refused (no grounding) | blocked (guard tripped) | error
    status: Mapped[str] = mapped_column(String(20), index=True)
    prompt_sha256: Mapped[str] = mapped_column(String(64))
    prompt: Mapped[str] = mapped_column(EncryptedString())  # may contain student text -> encrypted
    response: Mapped[str | None] = mapped_column(EncryptedString(), nullable=True)
    source_chunk_ids: Mapped[list] = mapped_column(JSON, default=list)
    guard_flags: Mapped[list] = mapped_column(JSON, default=list)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(40), nullable=True)


class ReviewTask(Base):
    """Something that needs a human (instructor) decision. Routed by course: whoever
    currently teaches the course sees it, so hand-overs re-route automatically."""

    __tablename__ = "review_tasks"
    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(40), index=True)  # diagnostic_item | content | mapping | tutor_answer | ...
    ref_type: Mapped[str] = mapped_column(String(40))
    ref_id: Mapped[int] = mapped_column(Integer, index=True)
    course_id: Mapped[int] = mapped_column(Integer, index=True)
    title: Mapped[str] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)  # pending | approved | rejected | resolved
    ai_call_id: Mapped[int | None] = mapped_column(ForeignKey("ai_calls.id"), nullable=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    decided_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
