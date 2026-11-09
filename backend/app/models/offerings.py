"""NB-1 - Academic offerings: terms, sections and instructor assignments (with history)."""
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base, utcnow


class Term(Base):
    __tablename__ = "terms"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(60), unique=True)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)


class Section(Base):
    __tablename__ = "sections"
    __table_args__ = (UniqueConstraint("course_id", "term_id", "code"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), index=True)
    term_id: Mapped[int] = mapped_column(ForeignKey("terms.id"), index=True)
    code: Mapped[str] = mapped_column(String(20))
    capacity: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="open")  # open | closed


class InstructorAssignment(Base):
    """Who teaches a section and when. Ended rows are kept as history."""

    __tablename__ = "instructor_assignments"
    id: Mapped[int] = mapped_column(primary_key=True)
    section_id: Mapped[int] = mapped_column(ForeignKey("sections.id"), index=True)
    instructor_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    role: Mapped[str] = mapped_column(String(20), default="primary")  # primary | assistant
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    assigned_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
