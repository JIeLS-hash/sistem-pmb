from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    String,
    Integer,
    Text,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    CheckConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.calon_mahasiswa import CalonMahasiswa
    from app.models.matakuliah import MataKuliah
    from app.models.jadwal import Kelas


class KRS(Base):
    __tablename__ = "krs"

    __table_args__ = (
        UniqueConstraint("nim", "semester", name="uq_krs_nim_semester"),
        CheckConstraint(
            "status IN ('DRAFT', 'SUBMITTED', 'APPROVED', 'REVISION')",
            name="ck_krs_status"
        ),
        CheckConstraint("total_sks BETWEEN 0 AND 24", name="ck_krs_total_sks"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    nim: Mapped[str] = mapped_column(
        ForeignKey("calon_mahasiswa.nim"),
        nullable=False,
        index=True
    )
    semester: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="DRAFT", nullable=False)
    total_sks: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    dosen_pa_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    catatan_revisi: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    mahasiswa: Mapped["CalonMahasiswa"] = relationship(
        "CalonMahasiswa",
        back_populates="krs_list"
    )
    details: Mapped[list["KRSDetail"]] = relationship(
        "KRSDetail",
        back_populates="krs",
        cascade="all, delete-orphan"
    )


class KRSDetail(Base):
    __tablename__ = "krs_detail"

    __table_args__ = (
        UniqueConstraint("krs_id", "kode_mk", name="uq_krs_detail_mk"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    krs_id: Mapped[int] = mapped_column(
        ForeignKey("krs.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    kode_mk: Mapped[str] = mapped_column(
        ForeignKey("matakuliah.kode_mk"),
        nullable=False,
        index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    kelas_id: Mapped[int | None] = mapped_column(
        ForeignKey("kelas.id", name="fk_krs_detail_kelas_id"), nullable=True, index=True
    )

    krs: Mapped["KRS"] = relationship("KRS", back_populates="details")
    matakuliah: Mapped["MataKuliah"] = relationship("MataKuliah", back_populates="krs_details")
    kelas: Mapped["Kelas | None"] = relationship("Kelas")
    