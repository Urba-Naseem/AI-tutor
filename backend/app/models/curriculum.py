"""US-1.1 / US-1.2 - Curriculum versions and the structured outcomes parsed from them."""
from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base, utcnow


class CurriculumVersion(Base):
    """One uploaded curriculum document. Earlier versions are never deleted."""

    __tablename__ = "curriculum_versions"
    id: Mapped[int] = mapped_column(primary_key=True)
    program_key: Mapped[str] = mapped_column(String(40), index=True)  # groups versions of the same programme
    version_no: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(200))
    filename: Mapped[str] = mapped_column(String(255))
    mime: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    file_ref: Mapped[str] = mapped_column(String(100))  # encrypted file in the upload store
    # preview -> in_review -> approved -> superseded   (or preview -> discarded)
    status: Mapped[str] = mapped_column(String(20), default="preview", index=True)
    extraction_engine: Mapped[str] = mapped_column(String(40))
    extracted_markdown: Mapped[str] = mapped_column(Text)
    parser: Mapped[str] = mapped_column(String(40))
    parsed: Mapped[dict] = mapped_column(JSON)
    warnings: Mapped[list] = mapped_column(JSON, default=list)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    uploaded_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class RoadmapEntry(Base):
    """One course in the semester roadmap (study plan) of a curriculum version. `course_code` links it to a course
    of the curriculum (matched by code or name); roadmap-only courses (no CLOs) keep course_code = None."""

    __tablename__ = "roadmap_entries"
    id: Mapped[int] = mapped_column(primary_key=True)
    curriculum_version_id: Mapped[int] = mapped_column(ForeignKey("curriculum_versions.id", ondelete="CASCADE"), index=True)
    semester: Mapped[int] = mapped_column(Integer)
    position: Mapped[int] = mapped_column(Integer, default=0)
    name: Mapped[str] = mapped_column(String(300))
    credits: Mapped[int | None] = mapped_column(Integer, nullable=True)
    credits_text: Mapped[str | None] = mapped_column(String(20), nullable=True)  # e.g. "3+1"
    course_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    match_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    matched_by: Mapped[str] = mapped_column(String(20), default="none")  # code | exact | similar | ai | manual | none
    source_filename: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

