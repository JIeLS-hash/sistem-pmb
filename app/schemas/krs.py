from __future__ import annotations

from datetime import datetime, time
from pydantic import BaseModel, ConfigDict, Field

from app.services.krs_manager import DEFAULT_SEMESTER


class CourseActionRequest(BaseModel):
    nim: str = Field(..., examples=["2026001001"])
    kode_mk: str = Field(..., examples=["IF201"])
    semester: str = Field(default=DEFAULT_SEMESTER, examples=[DEFAULT_SEMESTER])


class SubmitKRSRequest(BaseModel):
    nim: str = Field(..., examples=["2026001001"])
    semester: str = Field(default=DEFAULT_SEMESTER, examples=[DEFAULT_SEMESTER])


class ApproveKRSRequest(BaseModel):
    nim: str = Field(..., examples=["2026001001"])
    dosen_pa_id: int = Field(..., gt=0, examples=[101])
    semester: str = Field(default=DEFAULT_SEMESTER, examples=[DEFAULT_SEMESTER])


class RejectKRSRequest(BaseModel):
    nim: str = Field(..., examples=["2026001001"])
    dosen_pa_id: int = Field(..., gt=0, examples=[101])
    catatan_revisi: str | None = Field(
        default=None, examples=["Silakan ganti mata kuliah pilihan dengan MK wajib"]
    )
    semester: str = Field(default=DEFAULT_SEMESTER, examples=[DEFAULT_SEMESTER])


class MataKuliahResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kode_mk: str
    nama: str
    sks: int
    semester_paket: int
    is_wajib: bool
    hari: str
    jam_mulai: time
    jam_selesai: time


class KRSDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kode_mk: str
    matakuliah: MataKuliahResponse


class KRSResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nim: str
    semester: str
    status: str
    total_sks: int
    dosen_pa_id: int | None
    catatan_revisi: str | None
    updated_at: datetime
    details: list[KRSDetailResponse]


class ValidationResponse(BaseModel):
    is_valid: bool
    message: str