"""Course topics (a semester's worth of teaching units below the CLO level) and AI practice sets.

* Topic - one teachable topic of a course (about 4 per credit hour, 12 when credits are unknown), linked to the CLOs
  it serves (and through them to PLOs). Drafted by the AI from the approved CLOs and published straight away; the
  instructor can edit, hide or add topics at any time.
* PracticeSet - AI practice questions for one student before a formative quiz. Ungraded: they never count toward
  mastery and are never taken from (or added to) the approved question bank, so practising cannot reveal the
  formative questions.
"""
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base, utcnow


class Topic(Base):
    __tablename__ = "topics"
    __table_args__ = (UniqueConstraint("course_id", "number"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), index=True)
    unit_id: Mapped[int | None] = mapped_column(ForeignKey("units.id", ondelete="SET NULL"), nullable=True, index=True)
    number: Mapped[int] = mapped_column(Integer)  # teaching order within the course (1 = first)
    title: Mapped[str] = mapped_column(String(200))
    summary: Mapped[str] = mapped_column(Text, default="")
    clo_ids: Mapped[list] = mapped_column(JSON, default=list)  # first id = the CLO this topic mainly serves
    status: Mapped[str] = mapped_column(String(20), default="published")  # published | hidden
    origin: Mapped[str] = mapped_column(String(20), default="ai")  # ai | fallback | instructor
    edited_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    edited_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class PracticeSet(Base):
    __tablename__ = "practice_sets"
    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), index=True)
    clo_id: Mapped[int] = mapped_column(ForeignKey("clos.id", ondelete="CASCADE"), index=True)
    topic_id: Mapped[int | None] = mapped_column(ForeignKey("topics.id", ondelete="SET NULL"), nullable=True)
    questions: Mapped[list] = mapped_column(JSON, default=list)  # [{stem, options, answer_index, explanation}]
    answers: Mapped[dict] = mapped_column(JSON, default=dict)  # {"0": chosen_index, ...}
    ai_call_id: Mapped[int | None] = mapped_column(ForeignKey("ai_calls.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class StudentNote(Base):
    """A student's own note or flashcard (saved from the in-lesson tutor or typed), per course and topic."""

    __tablename__ = "student_notes"
    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), index=True)
    topic_id: Mapped[int | None] = mapped_column(ForeignKey("topics.id", ondelete="SET NULL"), nullable=True, index=True)
    kind: Mapped[str] = mapped_column(String(20), default="note")  # note | flashcard
    front: Mapped[str] = mapped_column(Text)
    back: Mapped[str] = mapped_column(Text, default="")
    section: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
