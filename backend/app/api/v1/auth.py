from typing import Optional
from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException, status
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr

from app.db.session import get_db
from app.models.user import User
from app.services.audit_service import AuditService

router = APIRouter()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class AuthRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: Optional[str] = None
    phone_number: Optional[str] = None

@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(
    data: AuthRequest, 
    background_tasks: BackgroundTasks, 
    db: Session = Depends(get_db)
):
    existing_user = db.query(User).filter(User.email == data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Email already registered"
        )

    hashed_pwd = pwd_context.hash(data.password)

    new_user = User(
        email=data.email,
        hashed_password=hashed_pwd,
        full_name=data.full_name,
        phone_number=data.phone_number
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    AuditService.emit_event_async(
        background_tasks,
        event_type="USER_REGISTERED",
        user_id=str(new_user.id),
        details={"email": new_user.email}
    )

    return {
        "message": "User registered successfully",
        "id": new_user.id,
        "email": new_user.email,
        "full_name": new_user.full_name,
        "phone_number": new_user.phone_number
    }