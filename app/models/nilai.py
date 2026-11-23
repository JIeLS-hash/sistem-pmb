from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    DDL,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    event,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.calon_mahasiswa import CalonMahasiswa
    from app.models.matakuliah import MataKuliah


GRADE_SCALE: dict[str, float] = {
    "A": 4.0,
    "B": 3.0,
    "C": 2.0,
    "D": 1.0,
    "E": 0.0,
}

PASSING_GRADES: set[str] = {"A", "B", "C", "D"}


class Grade(Base):
    __tablename__ = "grades"

    __table_args__ = (
        UniqueConstraint("nim", "kode_mk", "semester", name="uq_grades_nim_mk_semester"),
        CheckConstraint(
            "nilai_huruf IN ('A', 'B', 'C', 'D', 'E')",
            name="ck_grades_nilai_huruf",
        ),
        CheckConstraint(
            "nilai_angka BETWEEN 0.0 AND 4.0",
            name="ck_grades_nilai_angka",
        ),
        CheckConstraint(
            "presensi BETWEEN 0.0 AND 100.0",
            name="ck_grades_presensi",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    nim: Mapped[str] = mapped_column(
        ForeignKey("calon_mahasiswa.nim"),
        nullable=False,
        index=True,
    )
    kode_mk: Mapped[str] = mapped_column(
        ForeignKey("matakuliah.kode_mk"),
        nullable=False,
        index=True,
    )
    semester: Mapped[str] = mapped_column(String(20), nullable=False)
    presensi: Mapped[float] = mapped_column(Float, default=100.0, nullable=False)
    nilai_huruf: Mapped[str] = mapped_column(String(2), nullable=False)
    nilai_angka: Mapped[float] = mapped_column(Float, nullable=False)
    updated_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    update_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    mahasiswa: Mapped["CalonMahasiswa"] = relationship("CalonMahasiswa")
    matakuliah: Mapped["MataKuliah"] = relationship("MataKuliah")
    histories: Mapped[list["GradeHistory"]] = relationship(
        "GradeHistory",
        back_populates="grade",
        cascade="all, delete-orphan",
        order_by="GradeHistory.id.asc()",
    )


class GradeHistory(Base):
    __tablename__ = "grade_history"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    grade_id: Mapped[int] = mapped_column(
        ForeignKey("grades.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    old_value: Mapped[str] = mapped_column(String(2), nullable=False)
    new_value: Mapped[str] = mapped_column(String(2), nullable=False)
    changed_by: Mapped[str] = mapped_column(String(100), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)

    grade: Mapped["Grade"] = relationship("Grade", back_populates="histories")


AUDIT_TRIGGER_SQL = """
CREATE TRIGGER IF NOT EXISTS trg_grades_after_update
AFTER UPDATE OF nilai_huruf ON grades
FOR EACH ROW
WHEN OLD.nilai_huruf <> NEW.nilai_huruf
BEGIN
    INSERT INTO grade_history (grade_id, old_value, new_value, changed_by, changed_at, reason)
    VALUES (
        NEW.id,
        OLD.nilai_huruf,
        NEW.nilai_huruf,
        COALESCE(NEW.updated_by, 'system'),
        CURRENT_TIMESTAMP,
        COALESCE(NEW.update_reason, 'Pembaruan nilai')
    );
END;
"""

event.listen(
    Grade.__table__,
    "after_create",
    DDL(AUDIT_TRIGGER_SQL).execute_if(dialect="sqlite"),
)