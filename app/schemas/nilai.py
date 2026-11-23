from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field, field_validator

from app.models.nilai import GRADE_SCALE


class NilaiInputRequest(BaseModel):
    nim: str = Field(..., min_length=4, max_length=20)
    kode_mk: str = Field(..., min_length=2, max_length=10)
    semester: str = Field(..., min_length=4, max_length=20, examples=["2026/2027-1"])
    presensi: float = Field(..., ge=0.0, le=100.0, examples=[90.0])
    nilai_huruf: str = Field(..., min_length=1, max_length=2, examples=["A"])
    changed_by: str = Field(default="Dosen Pengampu", min_length=1, max_length=100)
    reason: str = Field(default="Input nilai akhir semester", min_length=1)

    @field_validator("nilai_huruf")
    @classmethod
    def validate_huruf(cls, v: str) -> str:
        cleaned = v.strip().upper()
        if cleaned not in GRADE_SCALE:
            raise ValueError(f"Nilai huruf harus salah satu dari {list(GRADE_SCALE.keys())}")
        return cleaned


class NilaiUpdateRequest(BaseModel):
    nilai_huruf: str = Field(..., min_length=1, max_length=2, examples=["A"])
    presensi: float | None = Field(default=None, ge=0.0, le=100.0)
    changed_by: str = Field(..., min_length=1, max_length=100, examples=["Dr. Budi Santoso"])
    reason: str = Field(..., min_length=3, examples=["Perbaikan nilai komponen UAS"])

    @field_validator("nilai_huruf")
    @classmethod
    def validate_huruf(cls, v: str) -> str:
        cleaned = v.strip().upper()
        if cleaned not in GRADE_SCALE:
            raise ValueError(f"Nilai huruf harus salah satu dari {list(GRADE_SCALE.keys())}")
        return cleaned


class GradeHistoryOut(BaseModel):
    id: int
    grade_id: int
    kode_mk: str | None = None
    semester: str | None = None
    old_value: str
    new_value: str
    changed_by: str
    changed_at: datetime
    reason: str

    model_config = {"from_attributes": True}


class GradeOut(BaseModel):
    id: int
    nim: str
    kode_mk: str
    semester: str
    presensi: float
    nilai_huruf: str
    nilai_angka: float
    status_lulus: str
    updated_by: str | None = None
    update_reason: str | None = None
    created_at: datetime
    updated_at: datetime
    ipk_terbaru: float | None = None

    model_config = {"from_attributes": True}