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
from app.db.models.claim import Claim, ClaimStatus
from app.db.models.user import User

from app.services.assessment_service import (
    run_assessment,
)

from app.services.claim_package_service import (
    IMAGE_EXTENSIONS,
    generate_claim_package,
)


router = APIRouter()


# ============================================================
# AUTHORIZATION HELPERS
# ============================================================

def get_normalized_role(user: User) -> str:
    """
    Safely extract and normalize the current user's role.

    Handles:
        Enum values
        Strings
        None
        Whitespace
        Different capitalization
    """

    role = getattr(user, "role", None)

    if role is None:
        return ""

    # Enum -> value
    role_value = getattr(role, "value", role)

    return str(role_value).strip().upper()


def is_authorized_for_claim(
    claim: Claim,
    current_user: User,
) -> bool:
    """
    Check whether the current user can access/run assessment
    for the given claim.

    Claim owner is always allowed.

    Service-center, technician, adjuster and admin roles
    are also allowed.

    The role normalization supports common variations such as:

        SERVICE_CENTER
        SERVICE_CENTER_USER
        SERVICE_CENTER_ADMIN
        TECHNICIAN
        TECHNICIAN_USER
        ADMIN
        ADJUSTER
    """

    # --------------------------------------------------------
    # Claim owner
    # --------------------------------------------------------

    if claim.user_id == current_user.id:
        return True

    role = get_normalized_role(current_user)

    # --------------------------------------------------------
    # Exact supported roles
    # --------------------------------------------------------

    allowed_roles = {
        "SERVICE_CENTER",
        "SERVICE_CENTER_USER",
        "SERVICE_CENTER_ADMIN",
        "TECHNICIAN",
        "TECHNICIAN_USER",
        "ADMIN",
        "ADJUSTER",
        # NOTE: plain "USER" (a customer) is intentionally NOT listed - customers may
        # only access their own claims, which the owner check above already allows.
    }

    if role in allowed_roles:
        return True

    # --------------------------------------------------------
    # Handle role naming variations
    # --------------------------------------------------------
    #
    # Examples:
    #
    # SERVICE-CENTER
    # service_center
    # Service Center
    # SERVICECENTER
    # SERVICE_CENTER_MANAGER
    #
    # Normalize separators first.
    # --------------------------------------------------------

    normalized = (
        role
        .replace("-", "_")
        .replace(" ", "_")
    )

    # Service-center related roles
    if (
        "SERVICE_CENTER" in normalized
        or "SERVICECENTER" in normalized
    ):
        return True

    # Technician-related roles
    if "TECHNICIAN" in normalized:
        return True

    # Admin-related roles
    if "ADMIN" in normalized:
        return True

    # Adjuster-related roles
    if "ADJUSTER" in normalized:
        return True

    return False


def require_claim_access(
    claim: Claim,
    current_user: User,
) -> None:
    """
    Raise a 403 error when the current user cannot access
    the requested claim.

    The actual role is included in the error message to make
    debugging authentication/role problems easier.
    """

    if is_authorized_for_claim(claim, current_user):
        return

    role = get_normalized_role(current_user)

    raise HTTPException(
        status_code=403,
        detail=(
            "Not authorized to access this claim. "
            f"Current user role: {role or 'UNKNOWN'}"
        ),
    )


# ============================================================
# HEALTH
# ============================================================

@router.get("/health")
def assessment_health():

    from app.ai.model_loader import model_status

    status = model_status()
    ready = status["damage_model_loaded"] and status["parts_model_loaded"]

    return {
        "module": "AI assessment",
        "status": "ready" if ready else "models_missing",
        **status,
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

    # --------------------------------------------------------
    # 1. Find claim
    # --------------------------------------------------------

    claim = (
        db.query(Claim)
        .filter(
            Claim.claim_id == claim_id
        )
        .first()
    )

    if not claim:
        raise HTTPException(
            status_code=404,
            detail="Claim not found",
        )

    # --------------------------------------------------------
    # 2. Authorization
    # --------------------------------------------------------

    require_claim_access(
        claim,
        current_user,
    )

    # --------------------------------------------------------
    # 3. Run AI assessment
    # --------------------------------------------------------

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

        if isinstance(exc, ValueError):
            raise HTTPException(
                status_code=400,
                detail=str(exc),
            )

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

    # --------------------------------------------------------
    # 2. Authorization
    # --------------------------------------------------------

    require_claim_access(
        claim,
        current_user,
    )

    # --------------------------------------------------------
    # 3. Find assessment
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
            detail="Assessment not found",
        )

    # --------------------------------------------------------
    # 4. Return assessment
    # --------------------------------------------------------

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

    # ========================================================
    # 1. FIND CLAIM
    # ========================================================

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

    # Keep the claim lifecycle in sync with the successfully generated
    # package so the customer timeline, service-center queue, and dashboard
    # all reflect the same persisted state.
    claim.status = ClaimStatus.PACKAGE_GENERATED
    db.commit()

    # ========================================================
    # 2. AUTHORIZATION
    # ========================================================

    require_claim_access(
        claim,
        current_user,
    )

    # ========================================================
    # 3. FIND ASSESSMENT
    # ========================================================

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

    # ========================================================
    # 4. CHECK ASSESSMENT STATUS
    # ========================================================

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

    # ========================================================
    # 5. LOCATE EVIDENCE
    # ========================================================

    evidence_dir = (
        Path("storage")
        / "claims"
        / claim_id
        / "evidence"
    )

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

    # ========================================================
    # 6. CREATE DIRECTORIES
    # ========================================================

    evidence_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    supporting_documents_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    # ========================================================
    # 7. VALIDATE / RESTORE EVIDENCE
    # ========================================================

    import shutil

    # IMPORTANT:
    #
    # The package must be built only from ClaimEvidence records.
    # Never fall back to whatever image files happen to exist in
    # storage/claims/<claim_id>/evidence because those files may be
    # stale artifacts from an earlier package generation.
    #
    # The database record (file_name + file_path) is authoritative.
    # The same ordered list is passed to claim_package_service below.
    # ========================================================

    evidence_order = []
    resolved_sources = []
    supporting_document_sources = []
    seen_image_names = set()
    seen_document_names = set()

    for ev in claim.evidence:

        if not getattr(ev, "file_path", None):
            continue

        stored_name = (
            getattr(ev, "file_name", None)
            or Path(ev.file_path).name
        )
        stored_name = Path(str(stored_name)).name

        if not stored_name:
            continue

        source_path = Path(ev.file_path)

        if not source_path.exists() or not source_path.is_file():
            source_path = Path.cwd() / source_path

        if not source_path.exists() or not source_path.is_file():
            continue

        key = stored_name.lower()
        if source_path.suffix.lower() in IMAGE_EXTENSIONS:
            # Keep image order aligned with the persisted assessment.
            if key in seen_image_names:
                continue
            seen_image_names.add(key)
            evidence_order.append(stored_name)
            resolved_sources.append((stored_name, source_path))
        else:
            # PDFs and other non-image uploads belong in the supporting
            # documents folder, never in the computer-vision image list.
            if key in seen_document_names:
                continue
            seen_document_names.add(key)
            supporting_document_sources.append((stored_name, source_path))

    if not evidence_order:
        raise HTTPException(
            status_code=400,
            detail=(
                "No valid uploaded evidence photographs were found "
                f"for claim {claim_id}. Please upload at least 1 "
                "vehicle damage photo in the photo intake tab."
            ),
        )

    # Keep package folders in sync with the files referenced by this claim.
    authoritative_names = {name.lower() for name in evidence_order}

    for existing_file in evidence_dir.iterdir():
        if not existing_file.is_file():
            continue
        if existing_file.name.lower() not in authoritative_names:
            try:
                existing_file.unlink()
            except OSError:
                pass

    authoritative_document_names = {
        name.lower() for name, _ in supporting_document_sources
    }
    for existing_file in supporting_documents_dir.iterdir():
        if not existing_file.is_file():
            continue
        if existing_file.name.lower() not in authoritative_document_names:
            try:
                existing_file.unlink()
            except OSError:
                pass

    copied_evidence = 0

    for stored_name, source_path in resolved_sources:
        destination = evidence_dir / stored_name

        try:
            if source_path.resolve() != destination.resolve():
                shutil.copy2(source_path, destination)

            if destination.exists() and destination.is_file():
                copied_evidence += 1

        except Exception:
            continue

    if copied_evidence != len(evidence_order):
        missing = [
            name
            for name in evidence_order
            if not (evidence_dir / name).is_file()
        ]

        raise HTTPException(
            status_code=400,
            detail=(
                "Evidence mapping failed for claim "
                f"{claim_id}. Missing files: "
                + ", ".join(missing)
            ),
        )

    for stored_name, source_path in supporting_document_sources:
        destination = supporting_documents_dir / stored_name
        try:
            if source_path.resolve() != destination.resolve():
                shutil.copy2(source_path, destination)
        except OSError as exc:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Could not map supporting document {stored_name}: {exc}"
                ),
            ) from exc

    # ========================================================
    # 8. BUILD CLAIM INFORMATION
    # ========================================================

    customer_obj = claim.user
    vehicle_obj = claim.vehicle

    claim_info: dict[str, Any] = {

        # ----------------------------------------------------
        # CUSTOMER
        # ----------------------------------------------------

        "customer_name": (
            getattr(
                customer_obj,
                "full_name",
                None,
            )
            or getattr(
                claim,
                "customer_name",
                None,
            )
            or (
                f"{getattr(customer_obj, 'first_name', '')} "
                f"{getattr(customer_obj, 'last_name', '')}"
            ).strip()
            or "Policyholder"
        ),

        "contact_number": (
            getattr(
                customer_obj,
                "phone",
                None,
            )
            or getattr(
                claim,
                "contact_number",
                None,
            )
            or ""
        ),

        "email": (
            getattr(
                customer_obj,
                "email",
                None,
            )
            or getattr(
                claim,
                "email",
                None,
            )
            or ""
        ),

        "customer_address": ", ".join(
            str(value).strip()
            for value in (
                getattr(customer_obj, "address_line", None),
                getattr(customer_obj, "city", None),
                getattr(customer_obj, "state", None),
                getattr(customer_obj, "pincode", None),
                getattr(customer_obj, "country", None),
            )
            if value
        ),

        # ----------------------------------------------------
        # VEHICLE
        # ----------------------------------------------------

        "vehicle_registration": (
            getattr(
                vehicle_obj,
                "registration_number",
                None,
            )
            or getattr(
                claim,
                "registration_number",
                None,
            )
            or getattr(
                claim,
                "vehicle_registration",
                None,
            )
            or ""
        ),

        "make": (
            getattr(
                vehicle_obj,
                "make",
                None,
            )
            or getattr(
                claim,
                "vehicle_make",
                None,
            )
            or ""
        ),

        "model": (
            getattr(
                vehicle_obj,
                "model",
                None,
            )
            or getattr(
                claim,
                "vehicle_model",
                None,
            )
            or ""
        ),

        "variant": (
            getattr(
                vehicle_obj,
                "variant",
                None,
            )
            or getattr(
                claim,
                "vehicle_variant",
                None,
            )
            or ""
        ),

        "vin": (
            getattr(
                vehicle_obj,
                "vin",
                None,
            )
            or getattr(
                claim,
                "vin",
                None,
            )
            or ""
        ),

        "year": getattr(vehicle_obj, "year", None),
        "vehicle_type": getattr(vehicle_obj, "vehicle_type", None) or "",
        "fuel_type": getattr(vehicle_obj, "fuel_type", None) or "",
        "engine_number": getattr(vehicle_obj, "engine_number", None) or "",
        "transmission": getattr(vehicle_obj, "transmission", None) or "",
        "color": getattr(vehicle_obj, "color", None) or "",

        "policy_number": (
            getattr(
                claim,
                "policy_number",
                None,
            )
            or getattr(
                vehicle_obj,
                "policy_number",
                None,
            )
            or ""
        ),

        "insurance_company": (
            getattr(
                claim,
                "insurance_company",
                None,
            )
            or getattr(
                vehicle_obj,
                "insurance_provider",
                None,
            )
            or ""
        ),

        # ----------------------------------------------------
        # ACCIDENT
        # ----------------------------------------------------

        "accident_date": (
            getattr(
                claim,
                "accident_date",
                None,
            )
            or ""
        ),

        "accident_time": (
            getattr(
                claim,
                "accident_time",
                None,
            )
            or ""
        ),

        "accident_location": (
            getattr(
                claim,
                "accident_location",
                None,
            )
            or ""
        ),

        "accident_description": (
            getattr(
                claim,
                "accident_description",
                None,
            )
            or ""
        ),

        "accident_type": getattr(claim, "accident_type", None) or "",
        "policy_type": getattr(claim, "policy_type", None) or "",
        "policy_expiry": getattr(claim, "policy_expiry", None) or "",

        # ----------------------------------------------------
        # WORKSHOP / SERVICE CENTER
        # ----------------------------------------------------

        "workshop_name": (
            getattr(
                claim,
                "service_center_name",
                None,
            )
            or getattr(
                claim,
                "workshop_name",
                None,
            )
            or ""
        ),

        "technician_name": (
            getattr(
                claim,
                "assigned_technician",
                None,
            )
            or getattr(
                claim,
                "technician_name",
                None,
            )
            or (
                (assessment.fusion_results or {}).get("technician_name")
                if isinstance(assessment.fusion_results, dict)
                else None
            )
            or ""
        ),
    }

    # ========================================================
    # 9. EXISTING ASSESSMENT RESULTS
    # ========================================================

    # --------------------------------------------------------
    # IMPORTANT:
    #
    # We DO NOT run the AI model again here.
    #
    # We use the assessment already stored against this claim.
    # --------------------------------------------------------

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

    # ========================================================
    # 10. MODEL METADATA
    # ========================================================

    stored_fusion = (
        assessment.fusion_results
        if isinstance(assessment.fusion_results, dict)
        else {}
    )
    stored_versions = stored_fusion.get("model_versions") or {}

    model_metadata = {

        "damage_model_version":
            stored_versions.get("damage") or "unknown",

        "parts_model_version":
            stored_versions.get("parts") or "unknown",

        "severity_version":
            stored_versions.get("severity") or "unknown",

        # short hashes of the weight files that produced this assessment
        "model_weights":
            stored_fusion.get("model_weights") or {},

        "vehicle_segment":
            (stored_fusion.get("summary") or {}).get("vehicle_segment"),

        "config": {
            "source":
                "backend",
        },
    }

    # ========================================================
    # 11. GENERATE PACKAGE
    # ========================================================

    try:

        # ----------------------------------------------------
        # Technician overrides
        # ----------------------------------------------------

        tech_overrides = {}

        if (
            assessment.fusion_results
            and isinstance(
                assessment.fusion_results,
                dict,
            )
        ):

            tech_overrides = (
                assessment
                .fusion_results
                .get(
                    "technician_overrides",
                    {},
                )
            )

        # ----------------------------------------------------
        # Repair estimate
        # ----------------------------------------------------

        workshop_items = []

        if (
            assessment.repair_results
            and isinstance(
                assessment.repair_results,
                dict,
            )
        ):

            workshop_items = (
                assessment
                .repair_results
                .get(
                    "items",
                    [],
                )
            )

        # ----------------------------------------------------
        # Generate package


        # evidence_order was built once above from the authoritative
        # ClaimEvidence records. Do not rebuild it from the filesystem.
        result = generate_claim_package(

            claim_id=claim_id,

            claim_info=claim_info,

            existing_assessment=(
                existing_assessment
            ),

            evidence_dir=evidence_dir,

            supporting_documents_dir=(
                supporting_documents_dir
            ),

            output_dir=output_dir,

            technician_overrides=(
                tech_overrides
            ),

            workshop_items=(
                workshop_items
            ),

            model_metadata=(
                model_metadata
            ),
            evidence_order=evidence_order
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

    # ========================================================
    # 12. RETURN RESULT
    # ========================================================

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
