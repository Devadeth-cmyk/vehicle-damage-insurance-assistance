from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.db.models.claim import Claim, ClaimStatus
from app.db.models.vehicle import Vehicle
from app.schemas.claim import ClaimCreate


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

    claim = Claim(
        user_id=user_id,
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
