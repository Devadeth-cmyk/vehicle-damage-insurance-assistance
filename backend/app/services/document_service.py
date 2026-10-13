from pathlib import Path
import shutil
from fastapi import HTTPException, status, UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models.claim import Claim, ClaimEvidence

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".pdf"}


def save_claim_evidence(
    db: Session, claim: Claim, file: UploadFile
) -> ClaimEvidence:
    extension = Path(file.filename or "").suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file type. Use PDF, JPG, JPEG, PNG or WEBP.",
        )

    claim_dir = Path(settings.UPLOAD_DIR) / claim.claim_id
    claim_dir.mkdir(parents=True, exist_ok=True)

    destination = claim_dir / Path(file.filename or "evidence.jpg").name

    with destination.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    evidence = ClaimEvidence(
        claim_id=claim.id,
        file_name=destination.name,
        file_path=str(destination),
        file_type=file.content_type or "application/octet-stream",
    )
    db.add(evidence)
    db.commit()
    db.refresh(evidence)
    return evidence
