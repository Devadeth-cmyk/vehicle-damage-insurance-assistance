from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ClaimCreate(BaseModel):
    vehicle_id: int
    customer_address: str | None = None
    accident_date: str | None = None
    accident_location: str | None = None
    accident_description: str | None = None
    accident_time: str | None = None
    accident_type: str | None = None
    policy_number: str | None = None
    insurance_company: str | None = None
    policy_type: str | None = None
    policy_expiry: str | None = None


class ClaimAssessmentSummary(BaseModel):
    status: str
    damage_results: dict[str, Any] | None = None
    parts_results: dict[str, Any] | None = None
    severity_results: dict[str, Any] | None = None
    fusion_results: dict[str, Any] | None = None
    repair_results: dict[str, Any] | None = None
    total_estimated_cost: float | None = None
    error_message: str | None = None

    model_config = ConfigDict(from_attributes=True)
class ClaimVehicleSummary(BaseModel):
    make: str
    model: str
    year: int | None = None
    registration_number: str
    vin: str | None = None
    engine_number: str | None = None

    model_config = ConfigDict(from_attributes=True)


class ClaimEvidenceSummary(BaseModel):
    file_name: str
    file_type: str
    uploaded_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class ClaimResponse(BaseModel):
    id: int
    claim_id: str
    vehicle_id: int
    service_center_id: int | None = None
    service_center_name: str | None = None
    status: str
    customer_address: str | None = None
    accident_date: str | None = None
    accident_location: str | None = None
    accident_description: str | None = None
    accident_time: str | None = None
    accident_type: str | None = None
    policy_number: str | None = None
    insurance_company: str | None = None
    policy_type: str | None = None
    policy_expiry: str | None = None
    created_at: datetime | None = None
    vehicle: ClaimVehicleSummary | None = None
    evidence: list[ClaimEvidenceSummary] = Field(default_factory=list)
    assessment: ClaimAssessmentSummary | None = None

    model_config = ConfigDict(from_attributes=True)
