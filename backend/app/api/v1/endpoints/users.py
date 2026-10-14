from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.database import get_db
from app.db.models.user import User
from app.schemas.user import UserUpdate


router = APIRouter()


@router.get("/me")
def get_profile(
    current_user: User = Depends(get_current_user),
):

    return {
        "id": current_user.id,
        "full_name": current_user.full_name,
        "email": current_user.email,
        "phone": current_user.phone,
        "address_line": current_user.address_line,
        "city": current_user.city,
        "state": current_user.state,
        "pincode": current_user.pincode,
        "country": current_user.country,
        "role": current_user.role.value,
        "service_center_id": current_user.service_center_id,
        "service_center_name": current_user.service_center.name if current_user.service_center else None,
        "is_active": current_user.is_active,
    }


@router.patch("/me")
def update_profile(
    payload: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(current_user, field, value.strip() if isinstance(value, str) else value)
    db.commit()
    db.refresh(current_user)
    return get_profile(current_user)
