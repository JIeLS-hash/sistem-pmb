from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import String, ForeignKey, UniqueConstraint, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.matakuliah import MataKuliah


class Prerequisite(Base):
    __tablename__ = "prerequisite"

    __table_args__ = (
        UniqueConstraint("kode_mk", "kode_mk_prasyarat", name="uq_prerequisite_pair"),
        CheckConstraint("kode_mk <> kode_mk_prasyarat", name="ck_prerequisite_not_self"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    kode_mk: Mapped[str] = mapped_column(
        ForeignKey("matakuliah.kode_mk", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    kode_mk_prasyarat: Mapped[str] = mapped_column(
        ForeignKey("matakuliah.kode_mk", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    min_nilai_huruf: Mapped[str] = mapped_column(
        ForeignKey("skala_nilai.huruf"),
        default="C",
        nullable=False
    )

    matakuliah: Mapped["MataKuliah"] = relationship(
        "MataKuliah",
        foreign_keys=[kode_mk],
        back_populates="prerequisites"
    )
    prasyarat_mk: Mapped["MataKuliah"] = relationship(
        "MataKuliah",
        foreign_keys=[kode_mk_prasyarat]
    )