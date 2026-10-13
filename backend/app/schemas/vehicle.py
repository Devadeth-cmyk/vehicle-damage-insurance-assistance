from pydantic import BaseModel


class VehicleCreate(BaseModel):
    registration_number: str
    make: str
    model: str
    year: int | None = None
    fuel_type: str | None = None
    vin: str | None = None
    engine_number: str | None = None


class VehicleUpdate(BaseModel):
    vin: str | None = None
    engine_number: str | None = None


class VehicleResponse(VehicleCreate):
    id: int

    model_config = {
        "from_attributes": True
    }
