import logging
import os
import re
from pathlib import Path
from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.api.deps import require_service_center
from app.db.database import get_db
from app.db.models.claim import Claim, ClaimEvidence, ClaimStatus
from app.db.models.assessment import Assessment, AssessmentStatus
from app.db.models.user import User
from app.services.assessment_service import run_assessment
from app.services.claim_package_service import generate_claim_package

router = APIRouter()
logger = logging.getLogger(__name__)


def _safe_unique_filename(directory: str, original: Optional[str]) -> str:
    """
    Sanitised file name that never overwrites an existing upload. Two photos
    called "image.jpg" used to land on the same path, so both evidence rows
    pointed at whichever was written last.
    """
    base = re.split(r"[\\/]", original or "")[-1]
    base = re.sub(r'[:*?"<>|\x00-\x1f]', "_", base).strip(". ") or "upload.jpg"
    stem, ext = os.path.splitext(base)
    ext = ext or ".jpg"
    candidate = f"{stem}{ext}"
    counter = 1
    while os.path.exists(os.path.join(directory, candidate)):
        candidate = f"{stem}_{counter}{ext}"
        counter += 1
    return candidate


def _money(value: Any, field: str, line_no: int) -> float:
    if value in (None, ""):
        return 0.0
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail=f"Line {line_no}: {field} must be a number.")
    if number != number or number < 0:
        raise HTTPException(status_code=422, detail=f"Line {line_no}: {field} cannot be negative.")
    return int(number) if number.is_integer() else round(number, 2)


class StatusUpdateSchema(BaseModel):
    status: str


class TechnicianAssignSchema(BaseModel):
    technician_name: str


class TechnicianReviewSchema(BaseModel):
    technician_overrides: dict[str, Any]
    review_notes: Optional[str] = None
    technician_name: Optional[str] = None


class RepairEstimateUpdateSchema(BaseModel):
    items: List[dict[str, Any]]
    total_estimated_cost: Optional[float] = None


@router.get("/health")
def service_center_health():
    return {
        "module": "service center",
        "status": "ready",
    }


@router.get("/dashboard")
def get_dashboard_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_service_center),
):
    claims = db.query(Claim).order_by(Claim.created_at.desc()).all()
    
    total_claims = len(claims)
    new_claims = len([c for c in claims if c.status.value in ["submitted", "draft"]])
    assessment_in_progress = len([c for c in claims if c.status.value == "assessment_in_progress"])
    awaiting_technician = len([c for c in claims if c.status.value == "human_review" or c.status.value == "assessment_completed"])
    repair_estimates_pending = len([c for c in claims if c.status.value == "under_review"])
    packages_generated = len([c for c in claims if c.status.value in ["package_generated", "ready_for_insurer", "approved"]])

    return {
        "summary": {
            "total_claims": total_claims,
            "new_claims": new_claims,
            "claims_under_assessment": assessment_in_progress,
            "awaiting_technician_review": awaiting_technician,
            "repair_estimates_pending": repair_estimates_pending,
            "packages_generated": packages_generated,
        },
        "recent_claims": [serialize_claim_detail(c) for c in claims[:10]]
    }


def serialize_claim_detail(claim: Claim) -> dict[str, Any]:
    return {
        "id": claim.id,
        "claim_id": claim.claim_id,
        "status": claim.status.value,
        "user_id": claim.user_id,
        "customer_name": claim.user.full_name if claim.user else "Policyholder",
        "customer_email": claim.user.email if claim.user else "N/A",
        "customer_phone": getattr(claim.user, "phone", "N/A"),
        "customer_address": claim.customer_address or ", ".join(
            value for value in (
                getattr(claim.user, "address_line", None),
                getattr(claim.user, "city", None),
                getattr(claim.user, "state", None),
                getattr(claim.user, "pincode", None),
                getattr(claim.user, "country", None),
            ) if value
        ) or "Not provided",
        "vehicle_id": claim.vehicle_id,
        "vehicle_make": claim.vehicle.make if claim.vehicle else "N/A",
        "vehicle_model": claim.vehicle.model if claim.vehicle else "N/A",
        "vehicle_year": claim.vehicle.year if claim.vehicle else None,
        "registration_number": claim.vehicle.registration_number if claim.vehicle else "Not provided",
        "vin": getattr(claim.vehicle, "vin", None) or "Not provided",
        "engine_number": getattr(claim.vehicle, "engine_number", None) or "Not provided",
        "insurance_company": claim.insurance_company or "Not provided",
        "policy_number": claim.policy_number or "Not provided",
        "policy_type": claim.policy_type or "Not provided",
        "policy_start": getattr(claim, "policy_start", None) or "Not provided",
        "policy_expiry": claim.policy_expiry or "Not provided",
        "accident_date": claim.accident_date or "Not provided",
        "accident_time": claim.accident_time or "Not provided",
        "accident_location": claim.accident_location or "Not provided",
        "accident_type": claim.accident_type or "Not provided",
        "accident_description": claim.accident_description,
        "assigned_technician": getattr(claim, "assigned_technician", None) or "Not assigned",
        "created_at": claim.created_at.isoformat() if claim.created_at else None,
        "updated_at": claim.updated_at.isoformat() if claim.updated_at else None,
        "evidence": [
            {
                "id": ev.id,
                "file_name": ev.file_name,
                "file_path": ev.file_path,
                "file_type": ev.file_type,
                "uploaded_at": ev.uploaded_at.isoformat() if ev.uploaded_at else None,
            }
            for ev in claim.evidence
        ],
        "assessment": {
            "id": claim.assessment.id,
            "status": claim.assessment.status.value,
            "error_message": getattr(claim.assessment, "error_message", None),
            "damage_results": claim.assessment.damage_results,
            "parts_results": claim.assessment.parts_results,
            "severity_results": claim.assessment.severity_results,
            "fusion_results": claim.assessment.fusion_results,
            "repair_results": claim.assessment.repair_results,
            "total_estimated_cost": claim.assessment.total_estimated_cost,
        } if claim.assessment else None
    }


@router.get("/claims")
def get_service_center_claims(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_service_center),
):
    claims = db.query(Claim).order_by(Claim.created_at.desc()).all()
    return [serialize_claim_detail(c) for c in claims]


@router.get("/claims/{claim_id}")
def get_service_center_claim_by_id(
    claim_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_service_center),
):
    claim = db.query(Claim).filter(Claim.claim_id == claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
    return serialize_claim_detail(claim)


@router.patch("/claims/{claim_id}/status")
def update_claim_status(
    claim_id: str,
    payload: StatusUpdateSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_service_center),
):
    claim = db.query(Claim).filter(Claim.claim_id == claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
    
    try:
        new_enum = ClaimStatus(payload.status.strip().lower())
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Unknown claim status '{payload.status}'.")

    claim.status = new_enum
    db.commit()
    db.refresh(claim)

    return {"message": "Status updated", "status": claim.status.value}


@router.post("/claims/{claim_id}/assign")
def assign_technician(
    claim_id: str,
    payload: TechnicianAssignSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_service_center),
):
    claim = db.query(Claim).filter(Claim.claim_id == claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
    
    setattr(claim, "assigned_technician", payload.technician_name)
    db.commit()
    return {"message": "Technician assigned", "assigned_technician": payload.technician_name}


@router.post("/claims/{claim_id}/evidence")
def upload_service_center_evidence(
    claim_id: str,
    files: List[UploadFile] = File(...),
    category: str = Form("General Evidence"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_service_center),
):
    claim = db.query(Claim).filter(Claim.claim_id == claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    upload_dir = os.path.join("storage", "claims", claim_id, "evidence")
    os.makedirs(upload_dir, exist_ok=True)

    saved_evidence = []
    for file in files:
        safe_name = _safe_unique_filename(upload_dir, file.filename)
        file_path = os.path.join(upload_dir, safe_name)
        with open(file_path, "wb") as f:
            f.write(file.file.read())

        ev = ClaimEvidence(
            claim_id=claim.id,
            file_name=safe_name,
            file_path=file_path,
            file_type=f"{category} ({file.content_type})"
        )
        db.add(ev)
        saved_evidence.append(ev)

    db.commit()
    return {"message": f"{len(saved_evidence)} files uploaded successfully", "evidence": [
        {"id": ev.id, "file_name": ev.file_name, "file_type": ev.file_type} for ev in saved_evidence
    ]}


@router.post("/claims/{claim_id}/technician-review")
def submit_technician_review(
    claim_id: str,
    payload: TechnicianReviewSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_service_center),
):
    claim = db.query(Claim).filter(Claim.claim_id == claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    assessment = db.query(Assessment).filter(Assessment.claim_id == claim.id).first()
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment must be run before technician review")

    # Update assessment with technician overrides.
    # Work on a COPY and flag the column: mutating the loaded JSON dict in place and
    # re-assigning the same object is not detected as a change by SQLAlchemy, so the
    # review could silently fail to persist.
    fusion = dict(assessment.fusion_results or {})
    fusion["technician_overrides"] = {str(k): str(v) for k, v in payload.technician_overrides.items()}
    fusion["review_notes"] = payload.review_notes
    fusion["technician_name"] = (
        payload.technician_name
        or getattr(current_user, "full_name", None)
        or getattr(current_user, "email", None)
    )
    assessment.fusion_results = fusion
    flag_modified(assessment, "fusion_results")
    
    assessment.status = AssessmentStatus.COMPLETED
    claim.status = ClaimStatus.HUMAN_REVIEW
    db.commit()

    return {"message": "Technician review saved successfully", "status": claim.status.value}


@router.post("/claims/{claim_id}/repair-estimate")
def save_repair_estimate(
    claim_id: str,
    payload: RepairEstimateUpdateSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_service_center),
):
    claim = db.query(Claim).filter(Claim.claim_id == claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    assessment = db.query(Assessment).filter(Assessment.claim_id == claim.id).first()
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    # Normalise the lines and compute the total here - the server is the single
    # source of truth for the figure that goes into the claim package, not
    # whatever number the browser happened to send.
    items: List[dict[str, Any]] = []
    total = 0
    for line_no, raw in enumerate(payload.items, start=1):
        item = dict(raw)
        item["partsCost"] = _money(item.get("partsCost"), "partsCost", line_no)
        item["laborCost"] = _money(item.get("laborCost"), "laborCost", line_no)
        total += item["partsCost"] + item["laborCost"]
        items.append(item)

    if payload.total_estimated_cost is not None and abs(payload.total_estimated_cost - total) > 0.5:
        logger.warning(
            "Client total %s differs from computed total %s for claim %s; using computed.",
            payload.total_estimated_cost, total, claim_id,
        )

    repair_data = dict(assessment.repair_results or {})   # copy, see note in submit_technician_review
    repair_data["items"] = items
    repair_data["total_estimated_cost"] = total
    assessment.total_estimated_cost = total

    assessment.repair_results = repair_data
    flag_modified(assessment, "repair_results")
    claim.status = ClaimStatus.UNDER_REVIEW
    db.commit()

    return {"message": "Repair estimate saved & approved", "status": claim.status.value}
