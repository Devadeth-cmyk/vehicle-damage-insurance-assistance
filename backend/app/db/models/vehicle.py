from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Vehicle(Base):
    __tablename__ = "vehicles"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    registration_number: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    make: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    model: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    year: Mapped[int | None] = mapped_column(
        nullable=True,
    )

    vin: Mapped[str | None] = mapped_column(String(100), nullable=True)
    engine_number: Mapped[str | None] = mapped_column(String(100), nullable=True)

    fuel_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    owner = relationship(
        "User",
        back_populates="vehicles",
    )

    claims = relationship(
        "Claim",
        back_populates="vehicle",
    )
