"""US-4.3 / US-4.5 / US-4.4 - Versioned learning paths."""
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base, utcnow


class LearningPath(Base):
    """Each change creates a new version; older versions are kept (superseded) and can be restored."""

    __tablename__ = "learning_paths"
    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), index=True)
    version_no: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)  # active | superseded
    trigger: Mapped[str] = mapped_column(String(30))  # diagnostic | prerequisite | no_diagnostic | adaptation | override | restore
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str] = mapped_column(Text)
    locked: Mapped[bool] = mapped_column(Boolean, default=False)
    lock_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    locked_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    restored_from: Mapped[int | None] = mapped_column(Integer, nullable=True)


class PathStep(Base):
    __tablename__ = "path_steps"
    id: Mapped[int] = mapped_column(primary_key=True)
    path_id: Mapped[int] = mapped_column(ForeignKey("learning_paths.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    unit_id: Mapped[int] = mapped_column(ForeignKey("units.id"))
    clo_id: Mapped[int] = mapped_column(ForeignKey("clos.id"), index=True)
    step_type: Mapped[str] = mapped_column(String(20))  # remedial | learn | practice | review | reteach
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending | done | skipped
    rationale: Mapped[str] = mapped_column(Text)
    rule: Mapped[str] = mapped_column(String(40))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)


class PathDecision(Base):
    """US-4.5 - Every automatic (or blocked) adaptation decision, with its inputs."""

    __tablename__ = "path_decisions"
    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), index=True)
    clo_id: Mapped[int] = mapped_column(ForeignKey("clos.id"), index=True)
    from_path_id: Mapped[int] = mapped_column(ForeignKey("learning_paths.id"))
    to_path_id: Mapped[int | None] = mapped_column(ForeignKey("learning_paths.id"), nullable=True)
    rule: Mapped[str] = mapped_column(String(30))
    decision: Mapped[str] = mapped_column(String(20))  # advance | repeat | remedial | review_fail | locked
    inputs: Mapped[dict] = mapped_column(JSON)
    message: Mapped[str] = mapped_column(Text)
    quiz_attempt_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
