"""US-4.1 - Diagnostic attempts, responses and per-CLO readiness."""
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base, utcnow


class DiagnosticAttempt(Base):
    __tablename__ = "diagnostic_attempts"
    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="in_progress", index=True)  # in_progress | completed | void
    items_per_clo: Mapped[int] = mapped_column(Integer)
    current_item_id: Mapped[int | None] = mapped_column(ForeignKey("items.id"), nullable=True)
    draft_choice: Mapped[int | None] = mapped_column(Integer, nullable=True)  # autosaved, not yet submitted
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    last_saved_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    void_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class DiagnosticResponse(Base):
    __tablename__ = "diagnostic_responses"
    id: Mapped[int] = mapped_column(primary_key=True)
    attempt_id: Mapped[int] = mapped_column(ForeignKey("diagnostic_attempts.id", ondelete="CASCADE"), index=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"))
    item_version: Mapped[int] = mapped_column(Integer)
    clo_id: Mapped[int] = mapped_column(ForeignKey("clos.id"), index=True)
    difficulty: Mapped[int] = mapped_column(Integer)
    chosen: Mapped[int] = mapped_column(Integer)
    correct: Mapped[bool] = mapped_column(Boolean)
    seq: Mapped[int] = mapped_column(Integer)
    answered_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class ReadinessResult(Base):
    __tablename__ = "readiness_results"
    id: Mapped[int] = mapped_column(primary_key=True)
    attempt_id: Mapped[int] = mapped_column(ForeignKey("diagnostic_attempts.id", ondelete="CASCADE"), index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), index=True)
    clo_id: Mapped[int] = mapped_column(ForeignKey("clos.id"), index=True)
    score_pct: Mapped[float] = mapped_column(Float)
    level: Mapped[str] = mapped_column(String(20))  # ready | developing | not_ready
    answered: Mapped[int] = mapped_column(Integer)
    correct: Mapped[int] = mapped_column(Integer)
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
