from fastapi import APIRouter, Depends, HTTPException
import hashlib
import secrets
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.vehicle_catalog import (
    SUPPORTED_VEHICLE_MAKES,
    canonical_vehicle_make,
    infer_vehicle_make_from_center_name,
)
from app.db.database import get_db
from app.db.models.service_center import ServiceCenter
from app.db.models.claim import Claim
from app.db.models.user import User, UserRole
from app.services.claim_service import resolve_service_center

router = APIRouter()


class ServiceCenterCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    city: str | None = None
    state: str | None = None
    address: str | None = None


class ServiceCenterUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    supported_makes: list[str] | None = None
    city: str | None = None
    state: str | None = None
    address: str | None = None
    is_active: bool | None = None

    @field_validator("supported_makes")
    @classmethod
    def validate_makes(cls, makes: list[str] | None) -> list[str] | None:
        if makes is None:
            return None
        normalized = [canonical_vehicle_make(make) for make in makes]
        if not normalized or any(make not in SUPPORTED_VEHICLE_MAKES for make in normalized):
            raise ValueError("Provide at least one published vehicle make")
        return list(dict.fromkeys(normalized))


class MemberAssignment(BaseModel):
    email: EmailStr


def _serialize(center: ServiceCenter) -> dict:
    return {
        "id": center.id,
        "name": center.name,
        "supported_makes": center.supported_makes or [],
        "city": center.city,
        "state": center.state,
        "address": center.address,
        "is_active": center.is_active,
    }


def _require_admin(user: User) -> None:
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Platform administrator access required")


def _route_unassigned_claims(db: Session) -> int:
    routed = 0
    claims = db.query(Claim).filter(Claim.service_center_id.is_(None)).all()
    for claim in claims:
        center = resolve_service_center(db, claim.vehicle, claim.accident_location)
        if center:
            claim.service_center_id = center.id
            routed += 1
    if routed:
        db.commit()
    return routed


@router.get("/options")
def list_active_service_centers(db: Session = Depends(get_db)):
    centers = db.query(ServiceCenter).filter(ServiceCenter.is_active.is_(True)).order_by(ServiceCenter.name).all()
    return [_serialize(center) for center in centers]


@router.get("")
def list_managed_service_centers(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    return [_serialize(c) for c in db.query(ServiceCenter).order_by(ServiceCenter.name).all()]


@router.post("", status_code=201)
def create_service_center(
    payload: ServiceCenterCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    make = infer_vehicle_make_from_center_name(payload.name)
    if make is None:
        raise HTTPException(
            status_code=422,
            detail=(
                "Include one supported vehicle make in the service-center name "
                "(for example, 'Toyota Kochi Service Center')."
            ),
        )
    join_code = secrets.token_urlsafe(18)
    center = ServiceCenter(
        **payload.model_dump(),
        supported_makes=[make],
        join_code_hash=hashlib.sha256(join_code.encode("utf-8")).hexdigest(),
    )
    db.add(center)
    db.commit()
    db.refresh(center)
    routed_count = _route_unassigned_claims(db)
    return {**_serialize(center), "join_code": join_code, "routed_existing_claims": routed_count}


@router.patch("/{center_id}")
def update_service_center(
    center_id: int,
    payload: ServiceCenterUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    center = db.get(ServiceCenter, center_id)
    if center is None:
        raise HTTPException(status_code=404, detail="Service center not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(center, key, value)
    db.commit()
    db.refresh(center)
    return {**_serialize(center), "routed_existing_claims": _route_unassigned_claims(db)}


@router.post("/{center_id}/members")
def assign_service_center_member(
    center_id: int,
    payload: MemberAssignment,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    center = db.get(ServiceCenter, center_id)
    member = db.query(User).filter(User.email == payload.email.strip().lower()).first()
    if center is None:
        raise HTTPException(status_code=404, detail="Service center not found")
    if member is None or member.role != UserRole.SERVICE_CENTER:
        raise HTTPException(status_code=404, detail="Service-center staff account not found")
    member.service_center_id = center.id
    db.commit()
    return {"message": "Staff member assigned", "user_id": member.id, "service_center_id": center.id}


@router.post("/{center_id}/invite-code")
def rotate_center_invite_code(
    center_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    center = db.get(ServiceCenter, center_id)
    if center is None or not center.is_active:
        raise HTTPException(status_code=404, detail="Active service center not found")
    join_code = secrets.token_urlsafe(18)
    center.join_code_hash = hashlib.sha256(join_code.encode("utf-8")).hexdigest()
    db.commit()
    return {"service_center_id": center.id, "join_code": join_code}
