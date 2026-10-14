from pydantic import BaseModel, field_validator


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

    @field_validator("make")
    @classmethod
    def validate_make(cls, value: str) -> str:
        from app.core.vehicle_catalog import canonical_vehicle_make

        make = canonical_vehicle_make(value)
        if make is None:
            raise ValueError("Select one of the supported vehicle manufacturers.")
        return make


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

    @field_validator("make")
    @classmethod
    def validate_make(cls, value: str | None) -> str | None:
        if value is None:
            return value
        from app.core.vehicle_catalog import canonical_vehicle_make

        make = canonical_vehicle_make(value)
        if make is None:
            raise ValueError("Select one of the supported vehicle manufacturers.")
        return make


class VehicleResponse(VehicleCreate):
    id: int

    model_config = {
        "from_attributes": True
    }
