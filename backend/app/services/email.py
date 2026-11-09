"""Outgoing e-mail. Without SMTP configured, messages are written to the outbox
folder (backend/outbox) so verification / reset links can be demonstrated."""
import json
import re
from datetime import datetime

from ..config import get_settings


def send_email(to: str, subject: str, body: str) -> None:
    folder = get_settings().path(get_settings().outbox_dir)
    folder.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    safe = re.sub(r"[^a-zA-Z0-9]+", "_", to)[:40]
    (folder / f"{stamp}-{safe}.json").write_text(
        json.dumps({"to": to, "subject": subject, "body": body, "sent_at": datetime.now().isoformat()}, indent=2)
    )


def list_outbox(limit: int = 30) -> list[dict]:
    folder = get_settings().path(get_settings().outbox_dir)
    if not folder.exists():
        return []
    files = sorted(folder.glob("*.json"), reverse=True)[:limit]
    return [json.loads(f.read_text()) for f in files]
