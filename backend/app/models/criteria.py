"""US-1.4 - Versioned attainment criteria.

Scope keys use stable codes so they survive new curriculum versions:
    global | program:<CODE> | course:<CODE> | clo:<COURSE>/<CLO>
A row is in force from `effective_from` until `superseded_at`, so the
criterion that applied at any moment can be reproduced.
"""
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base, utcnow

DEFAULT_THRESHOLD = 60.0


class AttainmentCriterion(Base):
    __tablename__ = "attainment_criteria"
    id: Mapped[int] = mapped_column(primary_key=True)
    scope_type: Mapped[str] = mapped_column(String(10), index=True)  # global | program | course | clo
    scope_key: Mapped[str] = mapped_column(String(80), index=True)
    version_no: Mapped[int] = mapped_column(Integer)
    threshold: Mapped[float | None] = mapped_column(Float, nullable=True)  # None = override removed
    reason: Mapped[str] = mapped_column(Text)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    effective_from: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
