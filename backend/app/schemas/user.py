from pydantic import BaseModel, EmailStr, ConfigDict


class UserBase(BaseModel):
    full_name: str
    email: EmailStr
    phone: str | None = None
    role: str = "user"


class UserCreate(UserBase):
    password: str


class UserUpdate(BaseModel):
    full_name: str | None = None
    phone: str | None = None
    address_line: str | None = None
    city: str | None = None
    state: str | None = None
    pincode: str | None = None
    country: str | None = None


class UserResponse(UserBase):
    id: int
    is_active: bool
    address_line: str | None = None
    city: str | None = None
    state: str | None = None
    pincode: str | None = None
    country: str | None = None

    model_config = ConfigDict(from_attributes=True)
