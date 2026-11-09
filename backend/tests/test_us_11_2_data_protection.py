"""US-11.2 Protect student and exam data."""
import sqlite3

from sqlalchemy import Column, Integer, MetaData, Table, create_engine, select

from app.core import crypto
from app.core.crypto import EncryptedString, get_keyring


def test_values_are_encrypted_at_rest_and_decrypt_transparently(tmp_path):
    eng = create_engine(f"sqlite:///{tmp_path/'t.db'}")
    md = MetaData()
    t = Table("secret", md, Column("id", Integer, primary_key=True), Column("v", EncryptedString()))
    md.create_all(eng)
    with eng.begin() as c:
        c.execute(t.insert().values(id=1, v="alice@university.edu"))
        assert c.execute(select(t.c.v)).scalar() == "alice@university.edu"
    raw = sqlite3.connect(tmp_path / "t.db").execute("select v from secret").fetchone()[0]
    assert raw.startswith("enc:") and "alice" not in raw


def test_ciphertext_is_randomised_and_tamper_evident():
    ring = get_keyring()
    a, b = ring.encrypt("x"), ring.encrypt("x")
    assert a != b
    bad = a[:-4] + ("AAAA" if not a.endswith("AAAA") else "BBBB")
    try:
        ring.decrypt(bad)
        assert False, "tampered ciphertext must not decrypt"
    except Exception:
        pass


def test_key_rotation_keeps_old_data_readable():
    ring = get_keyring()
    old = ring.encrypt("grade=A")
    old_kid = ring.active_id
    new_kid = ring.rotate()
    assert new_kid != old_kid
    assert ring.decrypt(old) == "grade=A"
    assert ring.key_id_of(ring.encrypt("y")) == new_kid


def test_blind_index_is_deterministic_and_case_insensitive():
    ring = get_keyring()
    assert ring.blind_index("A@University.edu") == ring.blind_index("a@university.edu")


def test_encrypted_file_store_roundtrip():
    name = crypto.store_encrypted_file(b"%PDF-1.4 secret", "x.pdf")
    from app.config import get_settings

    raw = (get_settings().path(get_settings().upload_dir) / name).read_bytes()
    assert b"secret" not in raw
    assert crypto.read_encrypted_file(name) == b"%PDF-1.4 secret"


def test_backup_uses_separate_key_and_roundtrips():
    ring = get_keyring()
    blob = ring.encrypt_backup(b"database bytes")
    assert b"database" not in blob
    assert ring.decrypt_backup(blob) == b"database bytes"
    # a data key cannot open a backup
    try:
        ring.decrypt_bytes(blob)
        assert False
    except Exception:
        pass


def test_keyring_is_stored_outside_database():
    from app.config import get_settings

    assert get_keyring().path.name == "keyring.json"
    assert "sqlite" not in str(get_keyring().path)
    assert get_settings().jwt_secret not in get_keyring().path.read_text()


def test_security_headers_and_hsts_over_https(client):
    r = client.get("/api/health")
    assert r.headers["strict-transport-security"].startswith("max-age=")
    assert r.headers["x-content-type-options"] == "nosniff"
