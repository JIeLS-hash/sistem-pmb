
from __future__ import annotations

from sqlalchemy import String, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app.models.calon_mahasiswa import CalonMahasiswa

class ProgramStudi(Base):
    __tablename__ = "program_studi"

    __table_args__ = (
        CheckConstraint(
            "length(kode) = 3",
            name="ck_program_studi_kode_length"
        ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True
    )

    kode: Mapped[str] = mapped_column(
        String(3),
        unique=True,
        nullable=False
    )

    nama: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    fakultas: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    calon_mahasiswa: Mapped[list["CalonMahasiswa"]] = relationship(
    "CalonMahasiswa",
    back_populates="program_studi"
)
