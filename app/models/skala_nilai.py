from __future__ import annotations

from sqlalchemy import String, Float, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SkalaNilai(Base):
    __tablename__ = "skala_nilai"

    __table_args__ = (
        CheckConstraint("bobot BETWEEN 0.0 AND 4.0", name="ck_skala_nilai_bobot"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    huruf: Mapped[str] = mapped_column(String(2), unique=True, nullable=False)
    bobot: Mapped[float] = mapped_column(Float, nullable=False)