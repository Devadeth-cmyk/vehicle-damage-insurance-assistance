from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.database import get_db
from app.db.models.user import User
from app.services.claim_service import get_user_claim_by_id
from app.services.document_service import save_claim_evidence

router = APIRouter()


@router.post("/claims/{claim_id}/evidence")
def upload_evidence(
    claim_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    claim = get_user_claim_by_id(db, current_user.id, claim_id)
    evidence = save_claim_evidence(db, claim, file)

    return {
        "message": "Evidence uploaded successfully",
        "claim_id": claim.claim_id,
        "file_name": evidence.file_name,
        "file_path": evidence.file_path,
    }