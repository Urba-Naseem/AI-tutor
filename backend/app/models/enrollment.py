"""US-2.4 - Enrolments. Rows are never deleted: withdrawals and completions stay as history."""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base, utcnow


class Enrollment(Base):
    __tablename__ = "enrollments"
    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    section_id: Mapped[int] = mapped_column(ForeignKey("sections.id"), index=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="enrolled", index=True)  # enrolled | withdrawn | completed
    enrolled_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    enrolled_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    prerequisite_override: Mapped[bool] = mapped_column(Boolean, default=False)
    override_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    withdraw_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
