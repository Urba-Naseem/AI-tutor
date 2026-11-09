"""US-11.2 - Protect student and exam data.

Encryption at rest uses AES-256-GCM with keys held in a *key ring file* that is
stored separately from the database and from backups (KEYRING_PATH).

Key ring layout (JSON):
    {
      "active": "k2",                       # key used for new encryptions
      "data_keys": {"k1": "<b64>", "k2": "<b64>"},   # old keys kept for decryption
      "index_key": "<b64>",                 # HMAC key for blind indexes (lookups on encrypted columns)
      "backup_key": "<b64>"                 # separate key for encrypted backups
    }

Ciphertext format: "enc:<key-id>:<base64(nonce + ciphertext + tag)>".
Rotation adds a new active key; `rotate_all()` re-encrypts stored values.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
from pathlib import Path
from threading import Lock

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import Text
from sqlalchemy.types import TypeDecorator

from ..config import get_settings

PREFIX = "enc:"


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode()


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s.encode())


class KeyRing:
    def __init__(self, path: Path):
        self.path = path
        self._data: dict = {}
        self.load()

    # ---- persistence -------------------------------------------------
    def load(self):
        if not self.path.exists():
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._data = {
                "active": "k1",
                "data_keys": {"k1": _b64(AESGCM.generate_key(bit_length=256))},
                "index_key": _b64(secrets.token_bytes(32)),
                "backup_key": _b64(AESGCM.generate_key(bit_length=256)),
            }
            self.save()
        else:
            self._data = json.loads(self.path.read_text())

    def save(self):
        self.path.write_text(json.dumps(self._data, indent=2))
        try:
            os.chmod(self.path, 0o600)
        except OSError:
            pass

    @property
    def active_id(self) -> str:
        return self._data["active"]

    @property
    def key_ids(self) -> list[str]:
        return list(self._data["data_keys"].keys())

    def rotate(self) -> str:
        n = max(int(k[1:]) for k in self._data["data_keys"]) + 1
        kid = f"k{n}"
        self._data["data_keys"][kid] = _b64(AESGCM.generate_key(bit_length=256))
        self._data["active"] = kid
        self.save()
        return kid

    # ---- primitives --------------------------------------------------
    def _key(self, kid: str) -> bytes:
        return _unb64(self._data["data_keys"][kid])

    def encrypt_bytes(self, data: bytes, kid: str | None = None) -> bytes:
        kid = kid or self.active_id
        nonce = os.urandom(12)
        ct = AESGCM(self._key(kid)).encrypt(nonce, data, kid.encode())
        return kid.encode() + b"|" + nonce + ct

    def decrypt_bytes(self, blob: bytes) -> bytes:
        kid, rest = blob.split(b"|", 1)
        nonce, ct = rest[:12], rest[12:]
        return AESGCM(self._key(kid.decode())).decrypt(nonce, ct, kid)

    def encrypt(self, text: str) -> str:
        kid = self.active_id
        nonce = os.urandom(12)
        ct = AESGCM(self._key(kid)).encrypt(nonce, text.encode(), kid.encode())
        return f"{PREFIX}{kid}:{_b64(nonce + ct)}"

    def decrypt(self, token: str) -> str:
        if not token.startswith(PREFIX):
            return token  # legacy/plain value
        kid, payload = token[len(PREFIX):].split(":", 1)
        raw = _unb64(payload)
        return AESGCM(self._key(kid)).decrypt(raw[:12], raw[12:], kid.encode()).decode()

    def key_id_of(self, token: str) -> str | None:
        return token[len(PREFIX):].split(":", 1)[0] if token and token.startswith(PREFIX) else None

    def blind_index(self, value: str) -> str:
        """Deterministic keyed hash so encrypted columns can still be looked up / kept unique."""
        return hmac.new(_unb64(self._data["index_key"]), value.strip().lower().encode(), hashlib.sha256).hexdigest()

    # ---- backups use their own key -----------------------------------
    def encrypt_backup(self, data: bytes) -> bytes:
        nonce = os.urandom(12)
        return b"AITB1" + nonce + AESGCM(_unb64(self._data["backup_key"])).encrypt(nonce, data, b"backup")

    def decrypt_backup(self, blob: bytes) -> bytes:
        if not blob.startswith(b"AITB1"):
            raise ValueError("Not an AI Tutor encrypted backup")
        nonce, ct = blob[5:17], blob[17:]
        return AESGCM(_unb64(self._data["backup_key"])).decrypt(nonce, ct, b"backup")


_ring: KeyRing | None = None
_lock = Lock()


def get_keyring() -> KeyRing:
    global _ring
    with _lock:
        path = get_settings().path(get_settings().keyring_path)
        if _ring is None or _ring.path != path:
            _ring = KeyRing(path)
        return _ring


class EncryptedString(TypeDecorator):
    """Column type that transparently encrypts on write and decrypts on read."""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return get_keyring().encrypt(str(value))

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return get_keyring().decrypt(value)


class EncryptedJSON(TypeDecorator):
    """JSON document stored encrypted."""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return get_keyring().encrypt(json.dumps(value))

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return json.loads(get_keyring().decrypt(value))


# ---- encrypted file storage (uploads) ---------------------------------
def store_encrypted_file(data: bytes, name_hint: str) -> str:
    folder = get_settings().path(get_settings().upload_dir)
    folder.mkdir(parents=True, exist_ok=True)
    fname = f"{secrets.token_hex(12)}.bin"
    (folder / fname).write_bytes(get_keyring().encrypt_bytes(data))
    return fname


def read_encrypted_file(fname: str) -> bytes:
    folder = get_settings().path(get_settings().upload_dir)
    return get_keyring().decrypt_bytes((folder / fname).read_bytes())


def rotate_all(engine) -> dict:
    """Re-encrypt every encrypted column value with the active key."""
    from sqlalchemy import inspect, text

    from ..db import Base

    ring = get_keyring()
    counts: dict[str, int] = {}
    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            enc_cols = [c.name for c in table.columns if isinstance(c.type, (EncryptedString, EncryptedJSON))]
            if not enc_cols or not inspect(conn).has_table(table.name):
                continue
            pk = [c.name for c in table.primary_key.columns][0]
            for col in enc_cols:
                rows = conn.execute(text(f"SELECT {pk}, {col} FROM {table.name} WHERE {col} IS NOT NULL")).all()
                for rid, val in rows:
                    if ring.key_id_of(val) != ring.active_id:
                        conn.execute(
                            text(f"UPDATE {table.name} SET {col} = :v WHERE {pk} = :id"),
                            {"v": ring.encrypt(ring.decrypt(val)), "id": rid},
                        )
                        counts[f"{table.name}.{col}"] = counts.get(f"{table.name}.{col}", 0) + 1
    # uploaded files
    folder = get_settings().path(get_settings().upload_dir)
    if folder.exists():
        for f in folder.glob("*.bin"):
            blob = f.read_bytes()
            if blob.split(b"|", 1)[0].decode() != ring.active_id:
                f.write_bytes(ring.encrypt_bytes(ring.decrypt_bytes(blob)))
                counts["files"] = counts.get("files", 0) + 1
    return counts
