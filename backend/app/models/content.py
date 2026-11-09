"""US-5.4 / US-5.1 - Learning content with full version history, and learner error reports."""
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base, utcnow


class ContentDoc(Base):
    """A teaching document for a unit (lesson) or an alternate explanation for one CLO (used for reteaching)."""

    __tablename__ = "content_docs"
    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), index=True)
    unit_id: Mapped[int] = mapped_column(ForeignKey("units.id"), index=True)
    clo_id: Mapped[int | None] = mapped_column(ForeignKey("clos.id"), nullable=True, index=True)
    kind: Mapped[str] = mapped_column(String(20), default="lesson")  # lesson | alternate
    title: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class ContentVersion(Base):
    __tablename__ = "content_versions"
    id: Mapped[int] = mapped_column(primary_key=True)
    doc_id: Mapped[int] = mapped_column(ForeignKey("content_docs.id", ondelete="CASCADE"), index=True)
    version_no: Mapped[int] = mapped_column(Integer)
    body_md: Mapped[str] = mapped_column(Text)
    # pending -> approved | rejected ; approved -> superseded when a newer version is approved
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    origin: Mapped[str] = mapped_column(String(20))  # ai | offline | manual
    change_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_chunk_ids: Mapped[list] = mapped_column(JSON, default=list)
    ai_call_id: Mapped[int | None] = mapped_column(ForeignKey("ai_calls.id"), nullable=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)


class ContentErrorReport(Base):
    """US-5.1 - A learner reports a mistake or accessibility problem in approved material."""

    __tablename__ = "content_error_reports"
    id: Mapped[int] = mapped_column(primary_key=True)
    version_id: Mapped[int] = mapped_column(ForeignKey("content_versions.id"), index=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    category: Mapped[str] = mapped_column(String(30))  # error | unclear | accessibility | other
    message: Mapped[str] = mapped_column(Text)
    excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="open", index=True)  # open | resolved
    resolution: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    resolved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class StudentLesson(Base):
    """A lecture + notes written by the AI for ONE student and ONE CLO, pitched to that student's level
    (from their diagnostic and mastery). Kept so the material stays stable until their level changes."""

    __tablename__ = "student_lessons"
    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), index=True)
    clo_id: Mapped[int] = mapped_column(ForeignKey("clos.id", ondelete="CASCADE"), index=True)
    level: Mapped[str] = mapped_column(String(20))  # foundations | standard | extension
    lecture_md: Mapped[str] = mapped_column(Text)
    notes_md: Mapped[str] = mapped_column(Text)
    origin: Mapped[str] = mapped_column(String(20))  # ai (offline notes are never stored)
    source_chunk_ids: Mapped[list] = mapped_column(JSON, default=list)
    ai_call_id: Mapped[int | None] = mapped_column(ForeignKey("ai_calls.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    # topic lessons (one per student, topic and level); instructors can edit a lesson or have it rewritten
    topic_id: Mapped[int | None] = mapped_column(ForeignKey("topics.id", ondelete="SET NULL"), nullable=True, index=True)
    instructor_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    slides: Mapped[list | None] = mapped_column(JSON, nullable=True)  # the same lesson as slides (None: article only)
    edited_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    edited_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
