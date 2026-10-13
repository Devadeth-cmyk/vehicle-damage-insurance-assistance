from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pathlib import Path

from app.api.deps import get_current_user
from app.db.database import get_db
from app.db.models.user import User
from app.schemas.claim import ClaimCreate, ClaimResponse
from app.services.claim_service import (
    create_user_claim,
    get_user_claim_by_id,
    get_user_claims,
)

router = APIRouter()


@router.post("", response_model=ClaimResponse)
def create_claim(
    request: ClaimCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return create_user_claim(db, current_user.id, request)


@router.get("", response_model=list[ClaimResponse])
def get_my_claims(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_user_claims(db, current_user.id)


@router.get("/{claim_id}", response_model=ClaimResponse)
def get_claim(
    claim_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_user_claim_by_id(db, current_user.id, claim_id)


@router.get("/{claim_id}/package/pdf")
def get_claim_pdf(claim_id: str):
    candidates = [
        Path("storage") / "claims" / claim_id / "package" / claim_id / "claim_report.pdf",
        Path("storage") / "claims" / claim_id / "package" / "claim_report.pdf",
    ]
    pdf_path = next((p for p in candidates if p.exists()), None)
    if not pdf_path:
        raise HTTPException(status_code=404, detail="PDF Not Found. Please generate claim package first.")
    return FileResponse(pdf_path, media_type="application/pdf", filename=f"{claim_id}_claim_report.pdf")


@router.get("/{claim_id}/package/zip")
def get_claim_zip(claim_id: str):
    candidates = [
        Path("storage") / "claims" / claim_id / "package" / f"{claim_id}_digital_claim_package.zip",
        Path("storage") / "claims" / claim_id / "package" / "claim_package.zip",
        Path("storage") / "claims" / claim_id / "package" / claim_id / "claim_package.zip",
    ]
    zip_path = next((p for p in candidates if p.exists()), None)
    if not zip_path:
        raise HTTPException(status_code=404, detail="ZIP Not Found. Please generate claim package first.")
    return FileResponse(zip_path, media_type="application/zip", filename=f"{claim_id}_claim_package.zip")