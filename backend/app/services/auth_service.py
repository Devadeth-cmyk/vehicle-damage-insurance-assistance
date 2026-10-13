from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password, verify_password
from app.db.models.user import User, UserRole
from app.schemas.auth import LoginResponse, RegisterRequest


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _find_user_by_email(db: Session, email: str) -> User | None:
    # Case-insensitive so "User@x.com" and "user@x.com" are the same account
    # (also matches older rows that were stored with mixed case).
    return (
        db.query(User)
        .filter(func.lower(User.email) == _normalize_email(email))
        .first()
    )


def register_user(db: Session, request: RegisterRequest) -> User:
    existing_user = _find_user_by_email(db, request.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email is already registered",
        )

    target_role = UserRole.USER
    if request.role and request.role.lower() in ["service_center", "technician"]:
        target_role = UserRole.SERVICE_CENTER
    elif request.role and request.role.lower() == "admin":
        target_role = UserRole.ADMIN

    user = User(
        full_name=request.full_name,
        email=_normalize_email(request.email),
        phone=request.phone,
        hashed_password=hash_password(request.password),
        role=target_role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, email: str, password: str) -> LoginResponse:
    user = _find_user_by_email(db, email)
    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    token = create_access_token(user.id, user.role.value)
    return LoginResponse(access_token=token)
