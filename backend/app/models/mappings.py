"""US-1.3 - CLO to PLO mappings."""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base, utcnow


class CloPloMapping(Base):
    __tablename__ = "clo_plo_mappings"
    __table_args__ = (UniqueConstraint("clo_id", "plo_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), index=True)
    clo_id: Mapped[int] = mapped_column(ForeignKey("clos.id", ondelete="CASCADE"), index=True)
    plo_id: Mapped[int] = mapped_column(ForeignKey("plos.id", ondelete="CASCADE"), index=True)
    strength: Mapped[int] = mapped_column(Integer, default=2)  # 1 low, 2 medium, 3 high
    origin: Mapped[str] = mapped_column(String(20))  # document | ai | offline | manual
    status: Mapped[str] = mapped_column(String(20), default="suggested", index=True)  # suggested | approved | rejected
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    decided_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ai_call_id: Mapped[int | None] = mapped_column(ForeignKey("ai_calls.id"), nullable=True)
