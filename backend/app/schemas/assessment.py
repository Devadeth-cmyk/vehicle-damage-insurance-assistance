from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict


class AssessmentResponse(BaseModel):
    id: int
    claim_id: int
    status: str
    damage_results: dict[str, Any] | None = None
    parts_results: dict[str, Any] | None = None
    severity_results: dict[str, Any] | None = None
    fusion_results: dict[str, Any] | None = None
    repair_results: dict[str, Any] | None = None
    total_estimated_cost: float | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
