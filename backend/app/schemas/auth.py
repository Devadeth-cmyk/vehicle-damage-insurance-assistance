from typing import Literal

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=150)
    email: EmailStr
    password: str = Field(min_length=4)
    phone: str | None = None
    portal: Literal["customer", "service_center"] = "customer"
    service_center_id: int | None = None
    service_center_code: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    portal: Literal["customer", "service_center", "admin"] | None = None


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
