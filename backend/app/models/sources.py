"""NB-2 - Approved teaching sources (reference material for grounded AI generation)."""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base, utcnow


class Source(Base):
    __tablename__ = "sources"
    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(30))  # textbook | lecture_notes | slides | reference | other
    license_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    filename: Mapped[str] = mapped_column(String(255))
    mime: Mapped[str] = mapped_column(String(100))
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    file_ref: Mapped[str] = mapped_column(String(100))
    extracted_markdown: Mapped[str] = mapped_column(Text)
    version_no: Mapped[int] = mapped_column(Integer, default=1)
    supersedes_id: Mapped[int | None] = mapped_column(ForeignKey("sources.id"), nullable=True)
    # pending -> approved | rejected ; approved -> retired
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    uploaded_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)


class SourceChunk(Base):
    __tablename__ = "source_chunks"
    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"), index=True)
    ordinal: Mapped[int] = mapped_column(Integer)
    heading: Mapped[str | None] = mapped_column(String(300), nullable=True)
    text: Mapped[str] = mapped_column(Text)
