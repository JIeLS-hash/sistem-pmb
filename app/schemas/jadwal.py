from __future__ import annotations

from datetime import time
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class JadwalBase(BaseModel):
    kelas_id: int = Field(..., gt=0)
    hari: int = Field(..., ge=1, le=6, description="1 = Senin .. 6 = Sabtu")
    jam_mulai: time
    jam_selesai: time
    ruangan_kode: str = Field(..., min_length=1, max_length=10)
    dosen_id: int = Field(..., gt=0)

    @model_validator(mode="after")
    def validate_time_range(self) -> JadwalBase:
        if self.jam_mulai >= self.jam_selesai:
            raise ValueError("jam_mulai harus lebih awal dari jam_selesai")
        return self


class JadwalCreate(JadwalBase):
    pass


class JadwalUpdate(BaseModel):
    kelas_id: int | None = Field(default=None, gt=0)
    hari: int | None = Field(default=None, ge=1, le=6)
    jam_mulai: time | None = None
    jam_selesai: time | None = None
    ruangan_kode: str | None = Field(default=None, min_length=1, max_length=10)
    dosen_id: int | None = Field(default=None, gt=0)


class JadwalResponse(BaseModel):
    id: int
    kelas_id: int
    hari: int
    jam_mulai: time
    jam_selesai: time
    ruangan_kode: str
    dosen_id: int

    model_config = ConfigDict(from_attributes=True)


class ConflictReportResponse(BaseModel):
    total_schedules: int
    total_conflicts: int
    conflicts: list[dict[str, Any]]