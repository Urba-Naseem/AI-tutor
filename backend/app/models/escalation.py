"""US-6.4 - Escalations for learners in repeated difficulty, and recorded interventions."""
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base, utcnow


class Escalation(Base):
    __tablename__ = "escalations"
    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), index=True)
    clo_id: Mapped[int | None] = mapped_column(ForeignKey("clos.id"), nullable=True, index=True)
    trigger: Mapped[str] = mapped_column(String(30))  # reteach_exhausted | repeated_failure | manual
    summary: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="open", index=True)  # open | acknowledged | resolved
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    acknowledged_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    resolved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    resolution: Mapped[str | None] = mapped_column(Text, nullable=True)


class Intervention(Base):
    """What an instructor did for a learner, and why. Overrides always carry a reason."""

    __tablename__ = "interventions"
    id: Mapped[int] = mapped_column(primary_key=True)
    escalation_id: Mapped[int | None] = mapped_column(ForeignKey("escalations.id"), nullable=True, index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), index=True)
    clo_id: Mapped[int | None] = mapped_column(ForeignKey("clos.id"), nullable=True)
    instructor_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    # note | meeting | reset_attempts | override_advance | mastery_override
    action: Mapped[str] = mapped_column(String(30))
    reason: Mapped[str] = mapped_column(Text)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
