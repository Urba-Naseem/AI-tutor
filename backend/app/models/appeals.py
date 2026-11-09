"""NB-4 - Assessment appeals and user notifications."""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base, utcnow


class Appeal(Base):
    __tablename__ = "appeals"
    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), index=True)
    clo_id: Mapped[int] = mapped_column(ForeignKey("clos.id"))
    quiz_attempt_id: Mapped[int] = mapped_column(ForeignKey("quiz_attempts.id"), index=True)
    evidence_id: Mapped[int] = mapped_column(ForeignKey("mastery_evidence.id"))
    item_id: Mapped[int | None] = mapped_column(ForeignKey("items.id"), nullable=True)
    reason: Mapped[str] = mapped_column(Text)
    # submitted -> under_review -> upheld | rejected
    status: Mapped[str] = mapped_column(String(20), default="submitted", index=True)
    original_score: Mapped[str] = mapped_column(String(20))
    resolution: Mapped[str | None] = mapped_column(Text, nullable=True)
    amended_score: Mapped[str | None] = mapped_column(String(20), nullable=True)
    amended_evidence_id: Mapped[int | None] = mapped_column(ForeignKey("mastery_evidence.id"), nullable=True)
    reviewer_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    link: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    read_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
