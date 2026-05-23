import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr

from app.auth.models import UserRole


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    role: UserRole = UserRole.pharmacist
    phone: str | None = None
    license_number: str | None = None


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    role: UserRole
    phone: str | None
    license_number: str | None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str
