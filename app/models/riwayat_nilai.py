from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import String, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.calon_mahasiswa import CalonMahasiswa
    from app.models.matakuliah import MataKuliah
    from app.models.skala_nilai import SkalaNilai


class RiwayatNilai(Base):
    __tablename__ = "riwayat_nilai"

    __table_args__ = (
        UniqueConstraint("nim", "kode_mk", "semester", name="uq_riwayat_nilai_mhs_mk_smt"),
        Index("ix_riwayat_nilai_lookup", "nim", "kode_mk", "nilai_huruf"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    nim: Mapped[str] = mapped_column(
        ForeignKey("calon_mahasiswa.nim"),
        nullable=False,
        index=True
    )
    kode_mk: Mapped[str] = mapped_column(
        ForeignKey("matakuliah.kode_mk"),
        nullable=False,
        index=True
    )
    semester: Mapped[str] = mapped_column(String(20), nullable=False)
    nilai_huruf: Mapped[str] = mapped_column(
        ForeignKey("skala_nilai.huruf"),
        nullable=False
    )

    mahasiswa: Mapped["CalonMahasiswa"] = relationship(
        "CalonMahasiswa",
        back_populates="riwayat_nilai"
    )
    matakuliah: Mapped["MataKuliah"] = relationship("MataKuliah")
    skala_nilai: Mapped["SkalaNilai"] = relationship("SkalaNilai")