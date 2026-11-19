
from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app.models.calon_mahasiswa import CalonMahasiswa

class JalurMasuk(Base):
    __tablename__ = "jalur_masuk"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True
    )

    nama: Mapped[str] = mapped_column(
        String(30),
        unique=True,
        nullable=False
    )

    calon_mahasiswa: Mapped[list["CalonMahasiswa"]] = relationship(
    "CalonMahasiswa",
    back_populates="jalur_masuk"
)
