from sqlalchemy.orm import Session
from app.db.models.vehicle import Vehicle
from app.schemas.vehicle import VehicleCreate


def create_user_vehicle(db: Session, user_id: int, request: VehicleCreate) -> Vehicle:
    vehicle = Vehicle(
        owner_id=user_id,
        **request.model_dump(),
    )
    db.add(vehicle)
    db.commit()
    db.refresh(vehicle)
    return vehicle


def get_user_vehicles(db: Session, user_id: int) -> list[Vehicle]:
    return db.query(Vehicle).filter(Vehicle.owner_id == user_id).all()
