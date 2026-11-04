from sqlalchemy.types import TypeDecorator, String
from app.core.security import EncryptionService


class EncryptedString(TypeDecorator):
    """SQLAlchemy Custom Type that transparently encrypts strings at rest (US-11.2)."""

    impl = String
    cache_ok = True

    def __init__(self, length=255, *args, **kwargs):
        # Fernet base64 output requires larger column storage space
        super().__init__(length=max(length, 500), *args, **kwargs)

    def process_bind_param(self, value, dialect):
        """Encrypts plain text before writing to database."""
        if value is not None:
            return EncryptionService.encrypt(str(value))
        return value

    def process_result_value(self, value, dialect):
        """Decrypts cipher text after retrieving from database."""
        if value is not None:
            return EncryptionService.decrypt(value)
        return value