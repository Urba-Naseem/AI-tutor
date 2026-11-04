import os
from cryptography.fernet import Fernet
from fastapi import HTTPException, status

# Load encryption key from environment variable
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")

if not ENCRYPTION_KEY:
    # Dev fallback key (MUST be configured in production .env)
    dev_key = Fernet.generate_key()
    ENCRYPTION_KEY = dev_key.decode()

fernet_suite = Fernet(ENCRYPTION_KEY.encode() if isinstance(ENCRYPTION_KEY, str) else ENCRYPTION_KEY)


class EncryptionService:
    """Symmetric encryption engine for PII and sensitive student/exam data (US-11.2)."""

    @staticmethod
    def encrypt(plain_text: str) -> str:
        if plain_text is None:
            return None
        return fernet_suite.encrypt(plain_text.encode("utf-8")).decode("utf-8")

    @staticmethod
    def decrypt(cipher_text: str) -> str:
        if cipher_text is None:
            return None
        try:
            return fernet_suite.decrypt(cipher_text.encode("utf-8")).decode("utf-8")
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Decryption failed: corrupted payload or invalid key."
            )