from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func
from app.db.session import Base
from app.db.types import EncryptedString  # US-11.2 Encrypted Type


class User(Base):
    __tablename__ = "users"
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    
    # Sensitive PII Fields Encrypted At Rest (US-11.2)
    full_name = Column(EncryptedString(255), nullable=True)
    phone_number = Column(EncryptedString(100), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)