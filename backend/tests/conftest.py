"""Shared test fixtures. Every test runs against a fresh in-memory database,
a throwaway key ring and the offline AI mode (no network calls)."""
import os
import tempfile

_tmp = tempfile.mkdtemp(prefix="aitutor-test-")
os.environ.update(
    APP_ENV="test",
    # fast in-memory SQLite by default; set TEST_DATABASE_URL to run the suite against PostgreSQL
    # (use an EMPTY throwaway database - every test drops and recreates all tables)
    DATABASE_URL=os.environ.get("TEST_DATABASE_URL", "sqlite://"),
    KEYRING_PATH=os.path.join(_tmp, "keyring.json"),
    JWT_SECRET="test-secret-" + "x" * 40,
    AI_MODE=os.environ.get("TEST_AI_MODE", "offline"),
    AUTOMATION="false",  # the step-by-step review workflow; tests/test_automation.py switches it on
    UPLOAD_DIR=os.path.join(_tmp, "uploads"),
    OUTBOX_DIR=os.path.join(_tmp, "outbox"),
    BACKUP_DIR=os.path.join(_tmp, "backups"),
    ALLOWED_EMAIL_DOMAIN="university.edu",
)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import db as dbmod  # noqa: E402
from app.main import app  # noqa: E402


_pg_ready = False


def _reset_database():
    """SQLite: rebuild the in-memory tables. PostgreSQL: build the tables once per run, then just empty them
    (rebuilding ~60 tables before every test takes seconds there)."""
    global _pg_ready
    from sqlalchemy import text

    eng = dbmod.engine
    if eng.dialect.name != "postgresql":
        dbmod.Base.metadata.drop_all(bind=eng)
        dbmod.init_db()
        return
    if not _pg_ready:
        dbmod.Base.metadata.drop_all(bind=eng)
        dbmod.init_db()
        _pg_ready = True
        return
    # DELETE is several times faster than TRUNCATE on small tables; triggers off so the audit guard and
    # foreign keys don't block the wipe; ids restart at 1 like a fresh database
    with eng.begin() as conn:
        conn.execute(text("SET LOCAL session_replication_role = replica"))
        for t in reversed(dbmod.Base.metadata.sorted_tables):
            conn.execute(text(f'DELETE FROM "{t.name}"'))
        conn.execute(text(
            "SELECT setval(c.oid, 1, false) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE c.relkind = 'S' AND n.nspname = current_schema()"))


@pytest.fixture()
def client():
    from app import models  # noqa: F401

    _reset_database()
    with TestClient(app, base_url="https://testserver") as c:
        yield c


@pytest.fixture()
def db(client):
    s = dbmod.SessionLocal()
    yield s
    s.close()
