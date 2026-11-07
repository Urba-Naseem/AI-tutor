"""One-time copy of an existing SQLite database into the configured (PostgreSQL) database.

Rows are copied table by table exactly as stored: encrypted columns stay encrypted with the same key ring, and
audit hashes keep chaining. The SQLite file is only read, never changed. The target must be empty.
"""
from __future__ import annotations

from pathlib import Path

from sqlalchemy import String, func, inspect, select, text


def copy_from_sqlite(sqlite_path: Path, batch: int = 1000) -> dict[str, int]:
    from .. import db as dbmod
    from .. import models  # noqa: F401  (registers all tables)

    dst = dbmod.engine
    if dst.dialect.name != "postgresql":
        raise RuntimeError("DATABASE_URL must point at PostgreSQL to copy into it")
    if not sqlite_path.exists():
        raise FileNotFoundError(sqlite_path)
    src = dbmod.make_engine("sqlite:///" + sqlite_path.resolve().as_posix())

    dbmod.init_db()  # tables, new columns and the audit triggers
    tables = dbmod.Base.metadata.sorted_tables
    with dst.connect() as conn:
        busy = [t.name for t in tables if conn.execute(select(func.count()).select_from(t)).scalar()]
    if busy:
        raise RuntimeError(f"The PostgreSQL database is not empty ({', '.join(busy[:5])}...). Use a new, empty database.")

    src_cols = {name: {c["name"] for c in inspect(src).get_columns(name)} for name in inspect(src).get_table_names()}

    # check text lengths first: SQLite ignores VARCHAR(n), PostgreSQL enforces it
    too_long = []
    with src.connect() as s:
        for t in tables:
            for c in t.columns:
                if isinstance(c.type, String) and c.type.length and c.name in src_cols.get(t.name, ()):
                    n = s.execute(text(f'SELECT MAX(LENGTH("{c.name}")) FROM "{t.name}"')).scalar() or 0
                    if n > c.type.length:
                        too_long.append(f"{t.name}.{c.name} ({n} > {c.type.length})")
    if too_long:
        raise RuntimeError("Values longer than their column allows: " + "; ".join(too_long))

    copied: dict[str, int] = {}
    with src.connect() as s, dst.begin() as d:
        # rows arrive in dependency order, but self-references / old orphans must not stop the copy;
        # foreign keys are checked again below
        d.execute(text("SET LOCAL session_replication_role = replica"))
        for t in tables:
            have = src_cols.get(t.name)
            if have is None:
                copied[t.name] = 0
                continue
            cols = [c for c in t.columns if c.name in have]
            rows = s.execute(select(*cols)).mappings()
            n = 0
            while chunk := rows.fetchmany(batch):
                d.execute(t.insert(), [dict(r) for r in chunk])
                n += len(chunk)
            copied[t.name] = n
        for t in tables:
            pk = list(t.primary_key.columns)
            if len(pk) == 1 and pk[0].autoincrement in (True, "auto") and pk[0].type.python_type is int:
                d.execute(text(
                    f"SELECT setval(pg_get_serial_sequence('\"{t.name}\"', '{pk[0].name}'), "
                    f"COALESCE(MAX(\"{pk[0].name}\"), 1), MAX(\"{pk[0].name}\") IS NOT NULL) FROM \"{t.name}\""))

    # verify: same row counts, and report rows whose parent row is missing (the copy keeps them as they were)
    orphans = []
    with src.connect() as s, dst.connect() as d:
        for t in tables:
            if t.name in src_cols:
                a = s.execute(select(func.count()).select_from(t)).scalar()
                b = d.execute(select(func.count()).select_from(t)).scalar()
                if a != b:
                    raise RuntimeError(f"Row count differs for {t.name}: SQLite {a}, PostgreSQL {b}")
            for fk in t.foreign_keys:
                col, ref = fk.parent, fk.column
                n = d.execute(text(
                    f'SELECT COUNT(*) FROM "{t.name}" c WHERE c."{col.name}" IS NOT NULL AND NOT EXISTS '
                    f'(SELECT 1 FROM "{ref.table.name}" p WHERE p."{ref.name}" = c."{col.name}")')).scalar()
                if n:
                    orphans.append(f"{t.name}.{col.name}: {n}")
    src.dispose()
    copied["_orphans"] = orphans  # type: ignore[assignment]
    return copied
