from sqlalchemy.orm import Session
from app.db.models.claim import Claim
from app.services.assessment_service import run_assessment


def process_assessment_job(claim_id: str, db: Session):
    claim = db.query(Claim).filter(Claim.claim_id == claim_id).first()
    if claim:
        return run_assessment(claim, db)
    return None
