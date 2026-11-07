"""Start the API server. Uses HTTPS automatically when backend/certs exists
(create it with: python -m app.cli gen-cert)."""
import logging
from pathlib import Path

import uvicorn

HERE = Path(__file__).parent
key, cert = HERE / "certs" / "localhost-key.pem", HERE / "certs" / "localhost.pem"


class _IgnoreClientResets(logging.Filter):
    """On Windows, asyncio logs a traceback whenever a browser drops a TLS connection
    (ConnectionResetError / WinError 10054). It is harmless noise, so it is filtered out."""

    def filter(self, record: logging.LogRecord) -> bool:
        exc = record.exc_info[1] if record.exc_info else None
        return not isinstance(exc, (ConnectionResetError, ConnectionAbortedError))


if __name__ == "__main__":
    logging.getLogger("asyncio").addFilter(_IgnoreClientResets())
    ssl = {"ssl_keyfile": str(key), "ssl_certfile": str(cert)} if key.exists() and cert.exists() else {}
    print(f"AI Tutor API on {'https' if ssl else 'http'}://localhost:8000  (docs at /docs)")
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, **ssl)
