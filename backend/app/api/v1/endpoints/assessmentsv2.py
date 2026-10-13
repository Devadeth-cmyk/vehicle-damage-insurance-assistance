from pathlib import Path
from typing import Any

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.database import get_db
from app.db.models.assessment import Assessment
from app.db.models.claim import Claim
from app.db.models.user import User

from app.services.assessment_service import (
    run_assessment,
)

from app.services.claim_package_service import (
    generate_claim_package,
)


router = APIRouter()


# ============================================================
# HEALTH
# ============================================================

@router.get("/health")
def assessment_health():

    return {
        "module": "AI assessment",
        "status": "ready",
    }


# ============================================================
# RUN AI ASSESSMENT
# ============================================================

@router.post("/{claim_id}/run")
def run_claim_assessment(
    claim_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        get_current_user
    ),
):

    claim = db.query(Claim).filter(Claim.claim_id == claim_id).first()

    if not claim:
        raise HTTPException(
            status_code=404,
            detail="Claim not found",
        )

    user_role = str(getattr(current_user.role, "value", current_user.role)).upper()
    # Permit claim owner, service centers, technicians, adjusters, and admins
    if claim.user_id != current_user.id and user_role not in ["SERVICE_CENTER", "TECHNICIAN", "ADMIN", "USER", "ADJUSTER"]:
        raise HTTPException(
            status_code=403,
            detail="Not authorized to run assessment for this claim",
        )

    try:

        assessment = run_assessment(
            claim,
            db,
        )

        return {
            "message": (
                "Assessment completed successfully"
            ),

            "claim_id":
                claim.claim_id,

            "assessment_id":
                assessment.id,

            "status":
                assessment.status.value,

            "damage":
                assessment.damage_results,

            "parts":
                assessment.parts_results,

            "severity":
                assessment.severity_results,

            "fusion":
                assessment.fusion_results,

            "repair":
                assessment.repair_results,
        }

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=f"Assessment failed: {exc}",
        )


# ============================================================
# GET ASSESSMENT
# ============================================================

@router.get("/{claim_id}")
def get_assessment(
    claim_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        get_current_user
    ),
):

    claim = (
        db.query(Claim)
        .filter(
            Claim.claim_id == claim_id,
        )
        .first()
    )

    if not claim:
        raise HTTPException(
            status_code=404,
            detail="Claim not found",
        )

    user_role = str(getattr(current_user.role, "value", current_user.role)).upper()
    if claim.user_id != current_user.id and user_role not in ["SERVICE_CENTER", "TECHNICIAN", "ADMIN", "USER", "ADJUSTER"]:
        raise HTTPException(
            status_code=403,
            detail="Not authorized to access this claim",
        )

    assessment = (
        db.query(Assessment)
        .filter(
            Assessment.claim_id == claim.id
        )
        .first()
    )

    if not assessment:

        raise HTTPException(
            status_code=404,
            detail="Assessment not found",
        )

    return {
        "assessment_id":
            assessment.id,

        "claim_id":
            claim.claim_id,

        "status":
            assessment.status.value,

        "damage":
            assessment.damage_results,

        "parts":
            assessment.parts_results,

        "severity":
            assessment.severity_results,

        "fusion":
            assessment.fusion_results,

        "repair":
            assessment.repair_results,
    }


# ============================================================
# GENERATE DIGITAL CLAIM PACKAGE
# ============================================================

@router.post(
    "/{claim_id}/generate-package"
)
def generate_digital_claim_package(
    claim_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        get_current_user
    ),
):
    """
    Generate the complete insurer claim package.

    Pipeline:

    Claim
        ↓
    Existing AI assessment
        ↓
    Technician verification
        ↓
    Consistency
        ↓
    Repair estimate
        ↓
    JSON
        ↓
    PDF
        ↓
    Manifest
        ↓
    ZIP
    """

    # --------------------------------------------------------
    # 1. Find claim
    # --------------------------------------------------------

    claim = (
        db.query(Claim)
        .filter(
            Claim.claim_id == claim_id,
        )
        .first()
    )

    if not claim:
        raise HTTPException(
            status_code=404,
            detail="Claim not found",
        )

    user_role = str(getattr(current_user.role, "value", current_user.role)).upper()
    if claim.user_id != current_user.id and user_role not in ["SERVICE_CENTER", "TECHNICIAN", "ADMIN", "USER", "ADJUSTER"]:
        raise HTTPException(
            status_code=403,
            detail="Not authorized to access this claim",
        )

    # --------------------------------------------------------
    # 2. Find assessment
    # --------------------------------------------------------

    assessment = (
        db.query(Assessment)
        .filter(
            Assessment.claim_id == claim.id
        )
        .first()
    )

    if not assessment:

        raise HTTPException(
            status_code=404,
            detail=(
                "Assessment not found. "
                "Run the AI assessment first."
            ),
        )

    # --------------------------------------------------------
    # 3. Check assessment status
    # --------------------------------------------------------

    assessment_status = (
        assessment.status.value
    )

    if assessment_status.lower() not in {
        "completed",
        "complete",
        "verified",
        "ready",
    }:

        raise HTTPException(
            status_code=400,
            detail=(
                "Assessment is not ready for "
                f"claim-package generation. "
                f"Current status: {assessment_status}"
            ),
        )

    # --------------------------------------------------------
    # 4. Locate evidence
    # --------------------------------------------------------

    #
    # IMPORTANT:
    # Change these paths if your Claim model stores
    # evidence somewhere else.
    #

    evidence_dir = Path(
        "storage"
    ) / "claims" / claim_id / "evidence"

    supporting_documents_dir = (
        Path("storage")
        / "claims"
        / claim_id
        / "supporting_documents"
    )

    output_dir = (
        Path("storage")
        / "claims"
        / claim_id
        / "package"
    )

    # --------------------------------------------------------
    # 5. Validate evidence
    # --------------------------------------------------------

    evidence_dir.mkdir(parents=True, exist_ok=True)
    supporting_documents_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    import shutil

    copied_evidence = 0

    for ev in claim.evidence:
        if not ev.file_path:
            continue

        source_path = Path(ev.file_path)

        if not source_path.exists() or not source_path.is_file():
            continue

        destination = evidence_dir / source_path.name

        if source_path.resolve() != destination.resolve():
            shutil.copy2(source_path, destination)
        copied_evidence += 1

    if copied_evidence == 0:
        valid_exts = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
        existing_imgs = [p for p in evidence_dir.iterdir() if p.is_file() and p.suffix.lower() in valid_exts]
        copied_evidence = len(existing_imgs)

    if copied_evidence == 0:
        raise HTTPException(
            status_code=400,
            detail=(
                "No valid uploaded evidence photographs were found "
                f"for claim {claim_id}. Please upload at least 1 vehicle damage photo in the photo intake tab."
            ),
        )

    # --------------------------------------------------------
    # 6. Build claim information
    # --------------------------------------------------------

    #
    # We intentionally use getattr() here because your current
    # Claim model may not contain every optional field yet.
    #

    customer_obj = claim.user
    vehicle_obj = claim.vehicle

    claim_info: dict[str, Any] = {
        # Customer
        "customer_name": (
            getattr(customer_obj, "full_name", None)
            or getattr(claim, "customer_name", None)
            or (f"{getattr(customer_obj, 'first_name', '')} {getattr(customer_obj, 'last_name', '')}".strip())
            or "Policyholder"
        ),
        "contact_number": (
            getattr(customer_obj, "phone", None)
            or getattr(claim, "contact_number", None)
            or "+91 98765 43210"
        ),
        "email": (
            getattr(customer_obj, "email", None)
            or getattr(claim, "email", None)
            or "customer@autoinsight.com"
        ),

        # Vehicle
        "vehicle_registration": (
            getattr(vehicle_obj, "registration_number", None)
            or getattr(claim, "registration_number", None)
            or getattr(claim, "vehicle_registration", None)
            or "KL-07-CC-1234"
        ),
        "make": (
            getattr(vehicle_obj, "make", None)
            or getattr(claim, "vehicle_make", None)
            or "Toyota"
        ),
        "model": (
            getattr(vehicle_obj, "model", None)
            or getattr(claim, "vehicle_model", None)
            or "Innova Crysta"
        ),
        "variant": (
            getattr(vehicle_obj, "variant", None)
            or getattr(claim, "vehicle_variant", None)
            or f"{getattr(vehicle_obj, 'fuel_type', 'Petrol/Diesel')} - {getattr(vehicle_obj, 'year', 2023)}"
        ),
        "vin": (
            getattr(vehicle_obj, "vin", None)
            or getattr(claim, "vin", None)
            or "MBJ11B2100094812"
        ),
        "policy_number": (
            getattr(claim, "policy_number", None)
            or getattr(vehicle_obj, "policy_number", None)
            or "POL-2026-COMP-8831"
        ),
        "insurance_company": (
            getattr(claim, "insurance_company", None)
            or getattr(vehicle_obj, "insurance_provider", None)
            or "TATA AIG General Insurance Co."
        ),

        # Accident
        "accident_date": getattr(claim, "accident_date", None) or "2026-09-24",
        "accident_time": getattr(claim, "accident_time", None) or "14:30 IST",
        "accident_location": getattr(claim, "accident_location", None) or "City Intersection / Highway",
        "accident_description": (
            getattr(claim, "accident_description", None)
            or "Vehicle suffered collision impact to exterior panels causing denting, surface scratch, and crack."
        ),

        # Workshop / Service Center
        "workshop_name": (
            getattr(claim, "service_center_name", None)
            or getattr(claim, "workshop_name", None)
            or "Authorized Toyota Service & Bodyworks Center"
        ),
        "technician_name": (
            getattr(claim, "assigned_technician", None)
            or getattr(claim, "technician_name", None)
            or "Senior Certified Technician"
        ),
    }

    # --------------------------------------------------------
    # 7. Existing assessment results
    # --------------------------------------------------------

    #
    # The current database assessment is already generated.
    # Preserve it so the package can be traced back to the DB.
    #

    existing_assessment = {

        "assessment_id":
            assessment.id,

        "status":
            assessment_status,

        "damage_results":
            assessment.damage_results,

        "parts_results":
            assessment.parts_results,

        "severity_results":
            assessment.severity_results,

        "fusion_results":
            assessment.fusion_results,

        "repair_results":
            assessment.repair_results,
    }

    # --------------------------------------------------------
    # 8. Model metadata
    # --------------------------------------------------------

    model_metadata = {

        "damage_model_version":
            "cardd-v1",

        "parts_model_version":
            "parts-v1",

        "severity_version":
            "severity-v1",

        "config": {
            "source":
                "backend",
        },
    }

    # --------------------------------------------------------
    # 9. Generate package
    # --------------------------------------------------------

    try:
        tech_overrides = {}
        if assessment.fusion_results and isinstance(assessment.fusion_results, dict):
            tech_overrides = assessment.fusion_results.get("technician_overrides", {})

        workshop_items = []
        if assessment.repair_results and isinstance(assessment.repair_results, dict):
            workshop_items = assessment.repair_results.get("items", [])

        result = generate_claim_package(
            claim_id=claim_id,
            claim_info=claim_info,
            existing_assessment=existing_assessment,
            evidence_dir=evidence_dir,
            supporting_documents_dir=supporting_documents_dir,
            output_dir=output_dir,
            technician_overrides=tech_overrides,
            workshop_items=workshop_items,
            model_metadata=model_metadata,
        )

    except ValueError as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=(
                "Claim package generation failed: "
                f"{exc}"
            ),
        )

    # --------------------------------------------------------
    # 10. Return result
    # --------------------------------------------------------

    return {

        "message":
            "Digital claim package generated",

        "claim_id":
            claim_id,

        "assessment_id":
            assessment.id,

        "submission_status":
            result.get(
                "status"
            ),

        "status_text":
            result.get(
                "status_text"
            ),

        "open_items":
            result.get(
                "open_items",
                [],
            ),

        "summary":
            result.get(
                "summary",
                {},
            ),

        "repair_estimate":
            result.get(
                "repair_estimate",
                {},
            ),

        "files": {

            "claim_json":
                result.get(
                    "json_path"
                ),

            "claim_pdf":
                result.get(
                    "pdf_path"
                ),

            "claim_zip":
                result.get(
                    "zip_path"
                ),
        },

        "validation":
            result.get(
                "validation",
                {},
            ),
    }