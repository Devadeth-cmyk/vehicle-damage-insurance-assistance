from fastapi import HTTPException, status
import hashlib
import hmac
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password, verify_password
from app.db.models.user import User, UserRole
from app.db.models.service_center import ServiceCenter
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

    center = None
    if request.portal == "service_center":
        if request.service_center_id is None:
            raise HTTPException(status_code=422, detail="Select the service-center organization for this account")
        center = db.get(ServiceCenter, request.service_center_id)
        if center is None or not center.is_active:
            raise HTTPException(status_code=404, detail="Active service-center organization not found")
        supplied_code = (request.service_center_code or "").strip()
        supplied_hash = hashlib.sha256(supplied_code.encode("utf-8")).hexdigest()
        if not center.join_code_hash or not hmac.compare_digest(center.join_code_hash, supplied_hash):
            raise HTTPException(status_code=403, detail="A valid organization invitation code is required")
    elif request.service_center_id is not None:
        raise HTTPException(status_code=422, detail="Customer accounts cannot be linked to a service center")

    user = User(
        full_name=request.full_name,
        email=_normalize_email(request.email),
        phone=request.phone,
        hashed_password=hash_password(request.password),
        # The portal is selected by the separate app host; public registration
        # can create customer or service-center accounts, never administrators.
        role=(
            UserRole.SERVICE_CENTER
            if request.portal == "service_center"
            else UserRole.USER
        ),
        service_center_id=center.id if center else None,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(
    db: Session,
    email: str,
    password: str,
    portal: str | None = None,
) -> LoginResponse:
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

    if portal == "customer" and user.role != UserRole.USER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account is not authorized for the customer portal",
        )
    if portal == "service_center" and user.role != UserRole.SERVICE_CENTER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account is not authorized for the service center portal",
        )
    if portal == "admin" and user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account is not authorized for the platform administration portal",
        )

    token = create_access_token(user.id, user.role.value)
    return LoginResponse(access_token=token)
