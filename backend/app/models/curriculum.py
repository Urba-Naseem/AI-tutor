from sqlalchemy import Column, Integer, String, DateTime, BigInteger, Text, JSON, func
from app.db.session import Base

class CurriculumDocument(Base):
    __tablename__ = "curriculum_documents"

    id = Column(Integer, primary_key=True, index=True)

    # Metadata linkage (Acceptance Criteria 3)
    program = Column(String(100), nullable=False)
    department = Column(String(100), nullable=False)
    cohort = Column(String(50), nullable=False)
    term = Column(String(50), nullable=False)

    # Versioning control field (US-1.1)
    version = Column(Integer, nullable=False, default=1)

    # File & Storage properties (Acceptance Criteria 4)
    original_filename = Column(String(255), nullable=False)
    stored_filename = Column(String(255), nullable=False)
    file_path = Column(String(512), nullable=False)
    mime_type = Column(String(100), nullable=False)
    file_size_bytes = Column(BigInteger, nullable=False)
    sha256_checksum = Column(String(64), nullable=False, index=True)

    # Audit & User tracking
    uploaded_by = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)