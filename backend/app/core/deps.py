"""Request dependencies: the authenticated user."""
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..db import get_db
from ..models.user import AuthSession, User
from .security import decode_access_token


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        raise HTTPException(401, "Not authenticated")
    data = decode_access_token(auth.split(" ", 1)[1])
    sess = db.get(AuthSession, data.get("sid"))
    if sess is None or sess.revoked_at is not None:
        raise HTTPException(401, "Session revoked")
    user = db.get(User, int(data["sub"]))
    if user is None or not user.is_active:
        raise HTTPException(401, "Account disabled")
    request.state.user = user
    return user
