"""US-6.3 - Reteach cycles for a CLO below mastery."""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base, utcnow


class ReteachCycle(Base):
    __tablename__ = "reteach_cycles"
    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), index=True)
    clo_id: Mapped[int] = mapped_column(ForeignKey("clos.id"), index=True)
    attempts_used: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    # active -> passed | exhausted (advanced with instructor follow-up)
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)
    explanation_source: Mapped[str] = mapped_column(String(30))  # approved_alternate | ai_grounded | ai_curriculum | offline_extract | offline_note
    explanation_md: Mapped[str] = mapped_column(Text)
    ai_call_id: Mapped[int | None] = mapped_column(ForeignKey("ai_calls.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
