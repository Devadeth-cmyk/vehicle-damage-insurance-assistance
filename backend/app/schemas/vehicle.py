from pydantic import BaseModel


class VehicleCreate(BaseModel):
    registration_number: str
    make: str
    model: str
    year: int | None = None
    fuel_type: str | None = None
    vin: str | None = None
    engine_number: str | None = None
    vehicle_type: str | None = None
    variant: str | None = None
    transmission: str | None = None
    color: str | None = None
    registration_date: str | None = None
    registration_state: str | None = None
    rto: str | None = None


class VehicleUpdate(BaseModel):
    registration_number: str | None = None
    make: str | None = None
    model: str | None = None
    year: int | None = None
    fuel_type: str | None = None
    vehicle_type: str | None = None
    variant: str | None = None
    transmission: str | None = None
    color: str | None = None
    registration_date: str | None = None
    registration_state: str | None = None
    rto: str | None = None
    vin: str | None = None
    engine_number: str | None = None


class VehicleResponse(VehicleCreate):
    id: int

    model_config = {
        "from_attributes": True
    }
