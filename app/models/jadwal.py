from __future__ import annotations

from datetime import time
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Time,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.matakuliah import MataKuliah


class Ruangan(Base):
    __tablename__ = "ruangan"
    __table_args__ = (
        CheckConstraint("kapasitas > 0", name="ck_ruangan_kapasitas"),
    )

    kode: Mapped[str] = mapped_column(String(10), primary_key=True)  # contoh: "A101"
    kapasitas: Mapped[int] = mapped_column(Integer, nullable=False)

    jadwals: Mapped[list[Jadwal]] = relationship(back_populates="ruangan")


class Dosen(Base):
    __tablename__ = "dosen"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    nidn: Mapped[str] = mapped_column(String(10), unique=True, nullable=False, index=True)
    nama: Mapped[str] = mapped_column(String(100), nullable=False)

    jadwals: Mapped[list[Jadwal]] = relationship(back_populates="dosen")


class Kelas(Base):
    __tablename__ = "kelas"
    __table_args__ = (
        CheckConstraint("kuota > 0", name="ck_kelas_kuota"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    kode_mk: Mapped[str] = mapped_column(
        String(20), ForeignKey("matakuliah.kode_mk"), nullable=False, index=True
    )
    nama: Mapped[str] = mapped_column(String(10), nullable=False)  # contoh: "A", "B"
    kuota: Mapped[int] = mapped_column(Integer, nullable=False)
    semester: Mapped[str] = mapped_column(String(20), nullable=False)  # contoh: "2026/2027-1"

    matakuliah: Mapped[MataKuliah] = relationship()
    jadwals: Mapped[list[Jadwal]] = relationship(
        back_populates="kelas", cascade="all, delete-orphan"
    )


class Jadwal(Base):
    __tablename__ = "jadwal"
    __table_args__ = (
        CheckConstraint("jam_mulai < jam_selesai", name="ck_jadwal_waktu"),
        CheckConstraint("hari BETWEEN 1 AND 6", name="ck_jadwal_hari"),
        Index("ix_jadwal_ruang", "hari", "ruangan_kode"),
        Index("ix_jadwal_dosen", "hari", "dosen_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    kelas_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("kelas.id"), nullable=False, index=True
    )
    hari: Mapped[int] = mapped_column(Integer, nullable=False)  # 1 = Senin .. 6 = Sabtu
    jam_mulai: Mapped[time] = mapped_column(Time, nullable=False)
    jam_selesai: Mapped[time] = mapped_column(Time, nullable=False)
    ruangan_kode: Mapped[str] = mapped_column(
        String(10), ForeignKey("ruangan.kode"), nullable=False
    )
    dosen_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("dosen.id"), nullable=False
    )

    kelas: Mapped[Kelas] = relationship(back_populates="jadwals")
    ruangan: Mapped[Ruangan] = relationship(back_populates="jadwals")
    dosen: Mapped[Dosen] = relationship(back_populates="jadwals")