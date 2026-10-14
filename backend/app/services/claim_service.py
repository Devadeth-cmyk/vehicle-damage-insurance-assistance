from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.db.models.claim import Claim, ClaimStatus
from app.db.models.vehicle import Vehicle
from app.db.models.service_center import ServiceCenter
from app.schemas.claim import ClaimCreate
from app.core.vehicle_catalog import canonical_vehicle_make


def resolve_service_center(db: Session, vehicle: Vehicle, location: str | None = None) -> ServiceCenter | None:
    make = canonical_vehicle_make(vehicle.make)
    if make is None:
        return None
    centers = [
        center
        for center in db.query(ServiceCenter).filter(ServiceCenter.is_active.is_(True)).all()
        if make in (center.supported_makes or [])
    ]
    if not centers:
        return None
    vehicle_state = (vehicle.registration_state or "").strip().casefold()
    state_matches = [
        center for center in centers
        if center.state and center.state.strip().casefold() == vehicle_state
    ]
    if vehicle_state and any(center.state for center in centers):
        if not state_matches:
            return None
        candidates = state_matches
    else:
        candidates = centers
    incident_location = (location or "").strip().casefold()
    city_matches = [
        center for center in candidates
        if center.city and center.city.strip().casefold() in incident_location
    ]
    if len(city_matches) == 1:
        return city_matches[0]
    if len(candidates) == 1:
        return candidates[0]
    return None


def create_user_claim(db: Session, user_id: int, request: ClaimCreate) -> Claim:
    vehicle = (
        db.query(Vehicle)
        .filter(Vehicle.id == request.vehicle_id, Vehicle.owner_id == user_id)
        .first()
    )
    if not vehicle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vehicle not found",
        )

    make = canonical_vehicle_make(vehicle.make)
    centers = [center for center in db.query(ServiceCenter).filter(ServiceCenter.is_active.is_(True)).all()
               if make in (center.supported_makes or [])]
    if not centers:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"No active service center currently accepts {make or vehicle.make}. Contact support to add a matching center.",
        )
    assigned_center = resolve_service_center(db, vehicle, request.accident_location)
    if assigned_center is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"No unique active service center matches {make or vehicle.make} for the vehicle's registration state and accident location. Ask an administrator to configure coverage.",
        )

    claim = Claim(
        user_id=user_id,
        service_center_id=assigned_center.id,
        status=ClaimStatus.SUBMITTED,
        **request.model_dump(),
    )
    db.add(claim)
    db.commit()
    db.refresh(claim)
    return claim


def get_user_claims(db: Session, user_id: int) -> list[Claim]:
    return (
        db.query(Claim)
        .filter(Claim.user_id == user_id)
        .order_by(Claim.created_at.desc())
        .all()
    )


def get_user_claim_by_id(db: Session, user_id: int, claim_id: str) -> Claim:
    claim = (
        db.query(Claim)
        .filter(Claim.claim_id == claim_id, Claim.user_id == user_id)
        .first()
    )
    if not claim:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Claim not found",
        )
    return claim
