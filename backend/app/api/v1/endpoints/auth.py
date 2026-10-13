from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.auth import LoginRequest, LoginResponse, RegisterRequest
from app.services.auth_service import authenticate_user, register_user

router = APIRouter()


@router.post(
    "/register",
    response_model=LoginResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(
    request: RegisterRequest,
    db: Session = Depends(get_db),
):
    user = register_user(db, request)
    return authenticate_user(db, user.email, request.password)


@router.post(
    "/login",
    response_model=LoginResponse,
)
def login(
    request: Optional[LoginRequest] = None,
    email: Optional[str] = Query(None),
    password: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    user_email = request.email if request else email
    user_password = request.password if request else password

    if not user_email or not user_password:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Email and password are required",
        )

    return authenticate_user(db, user_email, user_password)

@router.post(
    "/token",
    response_model=LoginResponse,
    include_in_schema=True,
)
def login_for_swagger(
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """
    Standard OAuth2 form login (username = your email).
    Used by the Swagger UI "Authorize" button.
    """
    return authenticate_user(db, form.username, form.password)
