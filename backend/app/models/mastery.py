"""NB-3 - Mastery evidence (versioned) and mastery decisions (history)."""
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base, utcnow


class MasteryEvidence(Base):
    """One scored piece of work for one CLO. Never edited in place: an amendment
    creates a new version and marks the old one superseded."""

    __tablename__ = "mastery_evidence"
    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), index=True)
    clo_id: Mapped[int] = mapped_column(ForeignKey("clos.id"), index=True)
    source: Mapped[str] = mapped_column(String(20))  # quiz | reteach
    source_ref: Mapped[str] = mapped_column(String(60))  # e.g. quiz_attempt:12
    correct: Mapped[int] = mapped_column(Integer)
    total: Mapped[int] = mapped_column(Integer)
    score_pct: Mapped[float] = mapped_column(Float)
    items: Mapped[list] = mapped_column(JSON, default=list)  # [{item_id, item_version, correct}]
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    version_no: Mapped[int] = mapped_column(Integer, default=1)
    supersedes_id: Mapped[int | None] = mapped_column(ForeignKey("mastery_evidence.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)  # active | superseded | void
    change_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    changed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)


class MasteryRecord(Base):
    """A mastery decision: what was calculated, from which evidence, under which criterion and rule."""

    __tablename__ = "mastery_records"
    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), index=True)
    clo_id: Mapped[int] = mapped_column(ForeignKey("clos.id"), index=True)
    mastery_pct: Mapped[float] = mapped_column(Float)
    attained: Mapped[bool] = mapped_column(Boolean)
    threshold: Mapped[float] = mapped_column(Float)
    criterion_id: Mapped[int] = mapped_column(ForeignKey("attainment_criteria.id"))
    criterion_version: Mapped[int] = mapped_column(Integer)
    rule_version: Mapped[str] = mapped_column(String(40))
    evidence_ids: Mapped[list] = mapped_column(JSON)
    attempts_counted: Mapped[int] = mapped_column(Integer)
    trigger: Mapped[str] = mapped_column(String(30))  # attempt | recalculation | amendment | override
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    calculated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    calculated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
