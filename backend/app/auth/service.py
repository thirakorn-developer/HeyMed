from datetime import datetime, timedelta, timezone

import bcrypt
from jose import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.auth.schemas import UserCreate
from app.config import settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_token(data: dict, token_type: str, expires_delta: timedelta) -> str:
    to_encode = data.copy()
    to_encode.update({"type": token_type, "exp": datetime.now(timezone.utc) + expires_delta})
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)


def create_access_token(user_id: str) -> str:
    return create_token(
        {"sub": user_id},
        "access",
        timedelta(minutes=settings.access_token_expire_minutes),
    )


def create_refresh_token(user_id: str) -> str:
    return create_token(
        {"sub": user_id},
        "refresh",
        timedelta(days=settings.refresh_token_expire_days),
    )


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def create_user(db: AsyncSession, data: UserCreate) -> User:
    user = User(
        email=data.email,
        full_name=data.full_name,
        hashed_password=hash_password(data.password),
        role=data.role,
        phone=data.phone,
        license_number=data.license_number,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def authenticate_user(db: AsyncSession, email: str, password: str) -> User | None:
    user = await get_user_by_email(db, email)
    if user is None or not verify_password(password, user.hashed_password):
        return None
    return user
