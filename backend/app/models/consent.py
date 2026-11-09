"""US-2.1 - Consent records (kept as history: acceptance and withdrawal)."""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base, utcnow


class ConsentRecord(Base):
    __tablename__ = "consent_records"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    version: Mapped[str] = mapped_column(String(20))
    text_sha256: Mapped[str] = mapped_column(String(64))
    accepted_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
