from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


def import_models():
    from app.db.models.user import User
    from app.db.models.vehicle import Vehicle
    from app.db.models.claim import Claim, ClaimEvidence
    from app.db.models.assessment import Assessment

    return (
        User,
        Vehicle,
        Claim,
        ClaimEvidence,
        Assessment,
    )