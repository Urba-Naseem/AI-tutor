"""Command-line tools.

    python -m app.cli init-keys      create key ring + JWT secret (first run)
    python -m app.cli gen-cert       self-signed HTTPS certificate for localhost
    python -m app.cli rotate-keys    add a new data key and re-encrypt all data
    python -m app.cli backup         write an encrypted backup to ./backups
    python -m app.cli restore FILE   restore an encrypted backup
    python -m app.cli copy-from-sqlite data/aitutor.db   one-time copy of a SQLite database into PostgreSQL
    python -m app.cli create-user --role admin --email a@university.edu --name "Ada Admin" --password ...
"""
import argparse
import secrets
import sys

from .config import BACKEND_DIR, get_settings


def _ensure_env_secret():
    env = BACKEND_DIR / ".env"
    text = env.read_text() if env.exists() else ""
    lines = [ln for ln in text.splitlines() if not ln.startswith("JWT_SECRET=")]
    current = [ln for ln in text.splitlines() if ln.startswith("JWT_SECRET=")]
    if current and len(current[0].split("=", 1)[1]) >= 32 and "change-me" not in current[0]:
        return False
    lines.append(f"JWT_SECRET={secrets.token_urlsafe(48)}")
    env.write_text("\n".join(lines) + "\n")
    return True


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m app.cli")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init-keys")
    sub.add_parser("gen-cert")
    sub.add_parser("rotate-keys")
    sub.add_parser("backup")
    r = sub.add_parser("restore")
    r.add_argument("file")
    sub.add_parser("seed")
    cp = sub.add_parser("copy-from-sqlite")
    cp.add_argument("file")
    cu = sub.add_parser("create-user")
    cu.add_argument("--role", required=True, choices=["student", "instructor", "admin", "exam_staff"])
    cu.add_argument("--email", required=True)
    cu.add_argument("--name", required=True)
    cu.add_argument("--password", required=True)
    args = p.parse_args(argv)
    s = get_settings()

    if args.cmd == "init-keys":
        from .core.crypto import get_keyring

        ring = get_keyring()
        print(f"Key ring ready at {ring.path} (active key {ring.active_id})")
        print("JWT secret generated in .env" if _ensure_env_secret() else "JWT secret already present")
    elif args.cmd == "gen-cert":
        from .core.tls import generate_dev_cert

        k, c = generate_dev_cert(BACKEND_DIR / "certs")
        print(f"Wrote {c} and {k}")
    elif args.cmd == "rotate-keys":
        from .core.crypto import get_keyring, rotate_all
        from .db import engine, init_db

        init_db()
        kid = get_keyring().rotate()
        print(f"New active key {kid}; re-encrypted: {rotate_all(engine)}")
    elif args.cmd == "backup":
        from .core.backup import create_backup

        print(f"Encrypted backup written to {create_backup()}")
    elif args.cmd == "restore":
        from pathlib import Path

        from .core.backup import restore_backup

        restore_backup(Path(args.file))
        print("Backup restored")
    elif args.cmd == "copy-from-sqlite":
        from pathlib import Path

        from .core.sqlite_copy import copy_from_sqlite

        res = copy_from_sqlite(Path(args.file))
        orphans = res.pop("_orphans")
        print(f"Copied {sum(res.values())} rows in {sum(1 for v in res.values() if v)} tables:")
        for name, n in res.items():
            if n:
                print(f"  {name}: {n}")
        if orphans:
            print("Rows pointing at a missing parent (copied unchanged, as they were in SQLite):")
            for o in orphans:
                print(f"  {o}")
    elif args.cmd == "create-user":
        from .core.crypto import get_keyring
        from .core.security import check_password_policy, hash_password
        from .db import SessionLocal, init_db
        from .models.user import User

        init_db()
        check_password_policy(args.password)
        db = SessionLocal()
        db.add(User(role=args.role, email=args.email, email_hash=get_keyring().blind_index(args.email),
                    full_name=args.name, password_hash=hash_password(args.password), email_verified=True))
        db.commit()
        print(f"Created {args.role} {args.email}")
    elif args.cmd == "seed":
        from .seed import run

        run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
