"""Database engine, session factory and declarative base."""
from datetime import datetime, timezone

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import StaticPool

from .config import get_settings


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


def make_engine(url: str):
    kwargs = {}
    in_memory = url in ("sqlite://", "sqlite:///:memory:")
    if url.startswith("sqlite"):
        # timeout: a writer waits up to 30 s for another writer instead of failing at once with "database is locked"
        kwargs["connect_args"] = {"check_same_thread": False, "timeout": 30}
        if in_memory:
            kwargs["poolclass"] = StaticPool
        else:
            path = url.replace("sqlite:///", "")
            from pathlib import Path

            Path(path).parent.mkdir(parents=True, exist_ok=True)
    if url.startswith("postgresql"):
        # drop dead connections (server restart, laptop sleep) instead of failing the next request
        kwargs.update(pool_pre_ping=True, pool_size=10, max_overflow=20)
    eng = create_engine(url, **kwargs)
    if url.startswith("sqlite"):

        @event.listens_for(eng, "connect")
        def _pragmas(dbapi_conn, _):
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.execute("PRAGMA busy_timeout=30000")
            if not in_memory:
                # WAL: readers never block the writer (web requests keep working while background jobs write)
                cur.execute("PRAGMA journal_mode=WAL")
                cur.execute("PRAGMA synchronous=NORMAL")
            cur.close()

    return eng


engine = make_engine(get_settings().db_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def configure(url: str):
    """Re-point the app at another database (used by tests)."""
    global engine
    engine = make_engine(url)
    SessionLocal.configure(bind=engine)
    return engine


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from . import models  # noqa: F401  (registers all tables)

    Base.metadata.create_all(bind=engine)
    add_missing_columns()
    models.install_db_guards(engine)


def add_missing_columns():
    """Bring an existing database up to date with new OPTIONAL columns (create_all only creates missing tables).
    Only nullable columns without a server default are added; existing rows and data are never changed."""
    from sqlalchemy import inspect, text

    insp = inspect(engine)
    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            if not insp.has_table(table.name):
                continue
            have = {c["name"] for c in insp.get_columns(table.name)}
            for col in table.columns:
                if col.name not in have and col.nullable and col.server_default is None and not col.primary_key:
                    ddl = col.type.compile(dialect=engine.dialect)
                    conn.execute(text(f'ALTER TABLE "{table.name}" ADD COLUMN "{col.name}" {ddl}'))
