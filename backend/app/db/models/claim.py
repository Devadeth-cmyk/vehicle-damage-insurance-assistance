import enum
import uuid

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base import Base


class ClaimStatus(str, enum.Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    ASSESSMENT_IN_PROGRESS = "assessment_in_progress"
    ASSESSMENT_COMPLETED = "assessment_completed"
    HUMAN_REVIEW = "human_review"
    PACKAGE_GENERATED = "package_generated"
    READY_FOR_INSURER = "ready_for_insurer"
    APPROVED = "approved"
    REJECTED = "rejected"
    NEEDS_INFORMATION = "needs_information"


class Claim(Base):
    __tablename__ = "claims"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    claim_id: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        index=True,
        default=lambda: (
            f"CLM-{uuid.uuid4().hex[:8].upper()}"
        ),
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    vehicle_id: Mapped[int] = mapped_column(
        ForeignKey("vehicles.id"),
        nullable=False,
        index=True,
    )

    service_center_id: Mapped[int | None] = mapped_column(
        ForeignKey("service_centers.id"), nullable=True, index=True
    )

    accident_date: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
    )

    accident_location: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    accident_description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    customer_address: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    policy_number: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    insurance_company: Mapped[str | None] = mapped_column(String(255), nullable=True)
    policy_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    policy_expiry: Mapped[str | None] = mapped_column(String(30), nullable=True)
    accident_time: Mapped[str | None] = mapped_column(String(20), nullable=True)
    accident_type: Mapped[str | None] = mapped_column(String(100), nullable=True)

    status: Mapped[ClaimStatus] = mapped_column(
        Enum(ClaimStatus),
        default=ClaimStatus.DRAFT,
        nullable=False,
        index=True,
    )

    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    user = relationship(
        "User",
        back_populates="claims",
    )

    service_center = relationship("ServiceCenter", back_populates="claims")

    vehicle = relationship(
        "Vehicle",
        back_populates="claims",
    )

    evidence = relationship(
        "ClaimEvidence",
        back_populates="claim",
        cascade="all, delete-orphan",
    )

    assessment = relationship(
        "Assessment",
        back_populates="claim",
        uselist=False,
        cascade="all, delete-orphan",
    )

    @property
    def service_center_name(self) -> str | None:
        return self.service_center.name if self.service_center else None


class ClaimEvidence(Base):
    __tablename__ = "claim_evidence"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    claim_id: Mapped[int] = mapped_column(
        ForeignKey("claims.id"),
        nullable=False,
        index=True,
    )

    file_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    file_path: Mapped[str] = mapped_column(
        String(1000),
        nullable=False,
    )

    file_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    uploaded_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    claim = relationship(
        "Claim",
        back_populates="evidence",
    )
