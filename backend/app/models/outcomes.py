"""US-1.2 - Reviewed academic structure: programmes, PLOs, courses, units, CLOs."""
from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base, utcnow


class Program(Base):
    __tablename__ = "programs"
    id: Mapped[int] = mapped_column(primary_key=True)
    curriculum_version_id: Mapped[int] = mapped_column(ForeignKey("curriculum_versions.id"), index=True)
    code: Mapped[str] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(String(200))


class PLO(Base):
    __tablename__ = "plos"
    id: Mapped[int] = mapped_column(primary_key=True)
    program_id: Mapped[int] = mapped_column(ForeignKey("programs.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(String(20))
    description: Mapped[str] = mapped_column(Text)


class Course(Base):
    __tablename__ = "courses"
    id: Mapped[int] = mapped_column(primary_key=True)
    program_id: Mapped[int] = mapped_column(ForeignKey("programs.id", ondelete="CASCADE"), index=True)
    curriculum_version_id: Mapped[int] = mapped_column(ForeignKey("curriculum_versions.id"), index=True)
    code: Mapped[str] = mapped_column(String(20), index=True)
    title: Mapped[str] = mapped_column(String(200))
    credits: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Semester of the programme roadmap (study plan) in which students take this course; None = not limited
    semester: Mapped[int | None] = mapped_column(Integer, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    prerequisites: Mapped[list] = mapped_column(JSON, default=list)  # course codes
    # draft -> approved -> active ; superseded when a newer curriculum version is approved
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)
    doc_mappings: Mapped[list] = mapped_column(JSON, default=list)  # CLO-PLO pairs stated in the document
    activated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    activated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)


class Unit(Base):
    __tablename__ = "units"
    __table_args__ = (UniqueConstraint("course_id", "number"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), index=True)
    number: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(200))


class CLO(Base):
    __tablename__ = "clos"
    __table_args__ = (UniqueConstraint("course_id", "code"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), index=True)
    unit_id: Mapped[int | None] = mapped_column(ForeignKey("units.id", ondelete="SET NULL"), nullable=True, index=True)
    code: Mapped[str] = mapped_column(String(20))
    description: Mapped[str] = mapped_column(Text)
    bloom: Mapped[str | None] = mapped_column(String(20), nullable=True)
    weight: Mapped[float | None] = mapped_column(Float, nullable=True)  # CLO weight in percent, if the document states it


class ReviewAck(Base):
    """A reviewer's explicit acknowledgement of an advisory warning."""

    __tablename__ = "review_acks"
    __table_args__ = (UniqueConstraint("curriculum_version_id", "issue_key"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    curriculum_version_id: Mapped[int] = mapped_column(ForeignKey("curriculum_versions.id"), index=True)
    issue_key: Mapped[str] = mapped_column(String(64))
    message: Mapped[str] = mapped_column(Text)
    note: Mapped[str] = mapped_column(Text)
    by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
