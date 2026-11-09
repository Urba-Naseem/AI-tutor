"""US-11.2 - Encrypted backups (database + encrypted upload store).

The backup archive is encrypted with the key ring's *backup key*, so a stolen
backup file is useless without the separately-held key ring.
"""
from __future__ import annotations

import io
import shutil
import sqlite3
import subprocess
import zipfile
from datetime import datetime
from pathlib import Path

from ..config import get_settings
from .crypto import get_keyring


def _sqlite_path() -> Path:
    url = get_settings().db_url
    return Path(url.replace("sqlite:///", "")).resolve()


def _is_pg() -> bool:
    return get_settings().db_url.startswith("postgresql")


def _pg_tool(name: str) -> str:
    """pg_dump / pg_restore from PATH, else from a standard Windows install."""
    found = shutil.which(name)
    if found:
        return found
    for d in sorted(Path("C:/Program Files/PostgreSQL").glob("*/bin"), reverse=True):
        if (d / f"{name}.exe").exists():
            return str(d / f"{name}.exe")
    raise RuntimeError(f"{name} not found - add PostgreSQL's bin folder to PATH")


def _pg_args():
    """Connection details for the PostgreSQL tools; the password goes through the environment, not the command line."""
    import os

    from sqlalchemy.engine import make_url

    u = make_url(get_settings().db_url)
    env = {**os.environ, "PGPASSWORD": u.password or ""}
    return ["-h", u.host or "localhost", "-p", str(u.port or 5432), "-U", u.username or "postgres", "-d", u.database], env


def create_backup(out_dir: Path | None = None) -> Path:
    s = get_settings()
    out_dir = out_dir or s.path(s.backup_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        if _is_pg():
            args, env = _pg_args()
            out = subprocess.run([_pg_tool("pg_dump"), "-Fc", *args], env=env, capture_output=True, check=True)
            z.writestr("aitutor.pgdump", out.stdout)
        else:
            # consistent snapshot through SQLite's online backup API
            src = sqlite3.connect(_sqlite_path())
            snap = sqlite3.connect(":memory:")
            src.backup(snap)
            src.close()
            z.writestr("aitutor.db", snap.serialize())
            snap.close()
        uploads = s.path(s.upload_dir)
        if uploads.exists():
            for f in uploads.glob("*.bin"):
                z.write(f, f"uploads/{f.name}")
    target = out_dir / f"aitutor-{datetime.now():%Y%m%d-%H%M%S}.bak.enc"
    target.write_bytes(get_keyring().encrypt_backup(buf.getvalue()))
    return target


def restore_backup(path: Path) -> None:
    s = get_settings()
    data = get_keyring().decrypt_backup(path.read_bytes())
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        if "aitutor.pgdump" in z.namelist():
            if not _is_pg():
                raise RuntimeError("This backup is from PostgreSQL; set DATABASE_URL to a PostgreSQL database")
            args, env = _pg_args()
            subprocess.run([_pg_tool("pg_restore"), "--clean", "--if-exists", "--no-owner", *args],
                           input=z.read("aitutor.pgdump"), env=env, capture_output=True, check=True)
        else:
            if _is_pg():
                raise RuntimeError("This backup is from SQLite; use copy-from-sqlite to move it into PostgreSQL")
            db_bytes = z.read("aitutor.db")
            dest = _sqlite_path()
            dest.parent.mkdir(parents=True, exist_ok=True)
            snap = sqlite3.connect(":memory:")
            snap.deserialize(db_bytes)
            out = sqlite3.connect(dest)
            snap.backup(out)
            out.close()
            snap.close()
        uploads = s.path(s.upload_dir)
        uploads.mkdir(parents=True, exist_ok=True)
        for name in z.namelist():
            if name.startswith("uploads/"):
                (uploads / Path(name).name).write_bytes(z.read(name))
