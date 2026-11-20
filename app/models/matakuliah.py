from __future__ import annotations

from datetime import time
from typing import TYPE_CHECKING

from sqlalchemy import String, Integer, Time, Boolean, CheckConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.krs import KRSDetail
    from app.models.prerequisite import Prerequisite


class MataKuliah(Base):
    __tablename__ = "matakuliah"

    __table_args__ = (
        CheckConstraint("sks BETWEEN 1 AND 6", name="ck_matakuliah_sks"),
        CheckConstraint("jam_selesai > jam_mulai", name="ck_matakuliah_jam"),
        Index("ix_matakuliah_jadwal", "hari", "jam_mulai", "jam_selesai"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    kode_mk: Mapped[str] = mapped_column(String(10), unique=True, nullable=False, index=True)
    nama: Mapped[str] = mapped_column(String(100), nullable=False)
    sks: Mapped[int] = mapped_column(Integer, nullable=False)
    semester_paket: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_wajib: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    hari: Mapped[str] = mapped_column(String(10), nullable=False)
    jam_mulai: Mapped[time] = mapped_column(Time, nullable=False)
    jam_selesai: Mapped[time] = mapped_column(Time, nullable=False)

    krs_details: Mapped[list["KRSDetail"]] = relationship(
        "KRSDetail",
        back_populates="matakuliah"
    )

    prerequisites: Mapped[list["Prerequisite"]] = relationship(
        "Prerequisite",
        foreign_keys="Prerequisite.kode_mk",
        back_populates="matakuliah",
        cascade="all, delete-orphan"
    )