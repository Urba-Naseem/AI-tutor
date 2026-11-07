"""Development helpers - only mounted when APP_ENV is development/test."""
from fastapi import APIRouter

from ..services.email import list_outbox

router = APIRouter(prefix="/api/dev", tags=["dev"])


@router.get("/outbox")
def outbox():
    """Shows e-mails the app would have sent (verification / reset links) for demos."""
    return list_outbox()
