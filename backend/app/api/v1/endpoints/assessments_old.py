from pathlib import Path
from typing import Any

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)
from fastapi.responses import FileResponse
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
    if claim.user_id != current_user.id and user_role not in ["SERVICE_CENTER", "TECHNICIAN", "ADMIN"]:
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
    if claim.user_id != current_user.id and user_role not in ["SERVICE_CENTER", "TECHNICIAN", "ADMIN"]:
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
    if claim.user_id != current_user.id and user_role not in ["SERVICE_CENTER", "TECHNICIAN", "ADMIN"]:
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
    for ev in claim.evidence:
        if ev.file_path and Path(ev.file_path).exists():
            dest = evidence_dir / Path(ev.file_path).name
            if not dest.exists():
                shutil.copy(ev.file_path, dest)

    # --------------------------------------------------------
    # 6. Build claim information
    # --------------------------------------------------------

    #
    # We intentionally use getattr() here because your current
    # Claim model may not contain every optional field yet.
    #

    claim_info: dict[str, Any] = {

        # Customer
        "customer_name":
            getattr(
                claim,
                "customer_name",
                "",
            ),

        "contact_number":
            getattr(
                claim,
                "contact_number",
                "",
            ),

        "email":
            getattr(
                claim,
                "email",
                "",
            ),

        # Vehicle
        "vehicle_registration":
            getattr(
                claim,
                "vehicle_registration",
                "",
            ),

        "make":
            getattr(
                claim,
                "vehicle_make",
                "",
            ),

        "model":
            getattr(
                claim,
                "vehicle_model",
                "",
            ),

        "variant":
            getattr(
                claim,
                "vehicle_variant",
                "",
            ),

        "vin":
            getattr(
                claim,
                "vin",
                "",
            ),

        "policy_number":
            getattr(
                claim,
                "policy_number",
                "",
            ),

        "insurance_company":
            getattr(
                claim,
                "insurance_company",
                "",
            ),

        # Accident
        "accident_date":
            getattr(
                claim,
                "accident_date",
                "",
            ),

        "accident_time":
            getattr(
                claim,
                "accident_time",
                "",
            ),

        "accident_location":
            getattr(
                claim,
                "accident_location",
                "",
            ),

        "accident_description":
            getattr(
                claim,
                "accident_description",
                "",
            ),

        # Workshop
        "workshop_name":
            getattr(
                claim,
                "workshop_name",
                "",
            ),

        "technician_name":
            getattr(
                claim,
                "technician_name",
                "",
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


# ============================================================
# CLAIM PACKAGE DOWNLOAD
# ============================================================

def _get_authorized_claim(
    claim_id: str,
    db: Session,
    current_user: User,
):
    """
    Get the claim and verify that the current user is allowed
    to access its generated package.
    """
    claim = (
        db.query(Claim)
        .filter(Claim.claim_id == claim_id)
        .first()
    )

    if not claim:
        raise HTTPException(
            status_code=404,
            detail="Claim not found",
        )

    user_role = str(
        getattr(current_user.role, "value", current_user.role)
    ).upper()

    if (
        claim.user_id != current_user.id
        and user_role not in [
            "SERVICE_CENTER",
            "TECHNICIAN",
            "ADMIN",
        ]
    ):
        raise HTTPException(
            status_code=403,
            detail="Not authorized to access this claim package",
        )

    return claim


def _package_paths(claim_id: str):
    """
    Return the paths produced by claim_package_service.py.

    generate_claim_package() receives:
        storage/claims/<claim_id>/package

    and creates:
        storage/claims/<claim_id>/package/<claim_id>/claim_report.pdf
        storage/claims/<claim_id>/package/<claim_id>_digital_claim_package.zip
    """
    output_dir = (
        Path("storage")
        / "claims"
        / claim_id
        / "package"
    )

    package_dir = output_dir / claim_id

    pdf_path = package_dir / "claim_report.pdf"

    zip_path = (
        output_dir
        / f"{claim_id}_digital_claim_package.zip"
    )

    json_path = package_dir / "claim_package.json"

    return {
        "output_dir": output_dir,
        "package_dir": package_dir,
        "pdf_path": pdf_path,
        "zip_path": zip_path,
        "json_path": json_path,
    }


@router.get("/{claim_id}/package")
def get_claim_package(
    claim_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Check whether the digital claim package exists and return
    API download URLs.
    """
    _get_authorized_claim(
        claim_id,
        db,
        current_user,
    )

    paths = _package_paths(claim_id)

    pdf_exists = paths["pdf_path"].is_file()
    zip_exists = paths["zip_path"].is_file()
    json_exists = paths["json_path"].is_file()

    return {
        "claim_id": claim_id,
        "ready": pdf_exists and zip_exists,
        "files": {
            "claim_json": json_exists,
            "claim_pdf": pdf_exists,
            "claim_zip": zip_exists,
        },
        "download_urls": {
            "pdf": (
                f"/api/v1/assessments/"
                f"{claim_id}/package/pdf"
            ),
            "zip": (
                f"/api/v1/assessments/"
                f"{claim_id}/package/zip"
            ),
        },
    }


@router.get("/{claim_id}/package/pdf")
def download_claim_pdf(
    claim_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Download the generated claim PDF.
    """
    _get_authorized_claim(
        claim_id,
        db,
        current_user,
    )

    paths = _package_paths(claim_id)
    pdf_path = paths["pdf_path"]

    if not pdf_path.is_file():
        raise HTTPException(
            status_code=404,
            detail=(
                "Claim PDF not found. "
                "Generate the digital claim package first."
            ),
        )

    return FileResponse(
        path=str(pdf_path.resolve()),
        media_type="application/pdf",
        filename=f"{claim_id}_claim_report.pdf",
    )


@router.get("/{claim_id}/package/zip")
def download_claim_zip(
    claim_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Download the complete digital claim package as a ZIP archive.
    """
    _get_authorized_claim(
        claim_id,
        db,
        current_user,
    )

    paths = _package_paths(claim_id)
    zip_path = paths["zip_path"]

    if not zip_path.is_file():
        raise HTTPException(
            status_code=404,
            detail=(
                "Claim ZIP package not found. "
                "Generate the digital claim package first."
            ),
        )

    return FileResponse(
        path=str(zip_path.resolve()),
        media_type="application/zip",
        filename=f"{claim_id}_digital_claim_package.zip",
    )

