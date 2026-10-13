import enum

from sqlalchemy import (
    DateTime,
    Enum,
    Float,
    ForeignKey,
    JSON,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base import Base


class AssessmentStatus(str, enum.Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Assessment(Base):
    __tablename__ = "assessments"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    claim_id: Mapped[int] = mapped_column(
        ForeignKey("claims.id"),
        nullable=False,
        unique=True,
    )

    status: Mapped[AssessmentStatus] = mapped_column(
        Enum(AssessmentStatus),
        default=AssessmentStatus.QUEUED,
        nullable=False,
    )

    damage_results: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )

    parts_results: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )

    severity_results: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )

    fusion_results: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )

    repair_results: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )

    total_estimated_cost: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    started_at: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    completed_at: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    claim = relationship(
        "Claim",
        back_populates="assessment",
    )