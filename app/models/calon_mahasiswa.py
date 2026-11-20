
from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    String,
    Text,
    Date,
    DateTime,
    ForeignKey,
    CheckConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.program_studi import ProgramStudi
    from app.models.jalur_masuk import JalurMasuk
    from app.models.krs import KRS
    from app.models.riwayat_nilai import RiwayatNilai


class CalonMahasiswa(Base):
    __tablename__ = "calon_mahasiswa"

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'approved', 'rejected')",
            name="ck_calon_mahasiswa_status"
        ),
        CheckConstraint(
            "length(phone) BETWEEN 10 AND 13 "
            "AND substr(phone, 1, 2) = '08' "
            "AND phone NOT GLOB '*[^0-9]*'",
            name="ck_calon_mahasiswa_phone"
        ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True
    )

    nama_lengkap: Mapped[str] = mapped_column(
        String(150),
        nullable=False
    )

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False
    )

    phone: Mapped[str] = mapped_column(
        String(15),
        nullable=False
    )

    tanggal_lahir: Mapped[date] = mapped_column(
        Date,
        nullable=False
    )

    alamat: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )

    program_studi_id: Mapped[int] = mapped_column(
        ForeignKey("program_studi.id"),
        nullable=False
    )

    jalur_masuk_id: Mapped[int] = mapped_column(
        ForeignKey("jalur_masuk.id"),
        nullable=False
    )

    status: Mapped[str] = mapped_column(
        String(20),
        default="pending",
        nullable=False
    )

    nim: Mapped[str | None] = mapped_column(
        String(20),
        unique=True,
        nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False
    )

    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True
    )

    program_studi: Mapped["ProgramStudi"] = relationship(
        "ProgramStudi",
        back_populates="calon_mahasiswa"
    )

    jalur_masuk: Mapped["JalurMasuk"] = relationship(
        "JalurMasuk",
        back_populates="calon_mahasiswa"
    )

    krs_list: Mapped[list["KRS"]] = relationship(
        "KRS",
        back_populates="mahasiswa"
    )

    riwayat_nilai: Mapped[list["RiwayatNilai"]] = relationship(
        "RiwayatNilai",
        back_populates="mahasiswa"
    )