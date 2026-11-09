"""US-6.2 - Hints given during quizzes."""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base, utcnow


class HintRequest(Base):
    __tablename__ = "hint_requests"
    id: Mapped[int] = mapped_column(primary_key=True)
    attempt_id: Mapped[int] = mapped_column(ForeignKey("quiz_attempts.id", ondelete="CASCADE"), index=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    level: Mapped[int] = mapped_column(Integer)  # 1..3, progressively more specific
    mode: Mapped[str] = mapped_column(String(20))  # socratic (Gemini) | static (fallback) | protected (AI blocked -> static)
    text: Mapped[str] = mapped_column(Text)
    ai_call_id: Mapped[int | None] = mapped_column(ForeignKey("ai_calls.id"), nullable=True)
    at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
