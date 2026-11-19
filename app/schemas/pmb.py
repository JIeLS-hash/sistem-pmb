
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# Data yang diterima saat calon mahasiswa mendaftar
class CalonMahasiswaCreate(BaseModel):
    nama_lengkap: str = Field(min_length=3, max_length=150)
    email: EmailStr
    phone: str = Field(pattern=r"^08[0-9]{8,11}$")
    tanggal_lahir: date
    alamat: str = Field(min_length=5)
    program_studi_id: int = Field(gt=0)
    jalur_masuk_id: int = Field(gt=0)


# Data yang dikirim kembali oleh API
class CalonMahasiswaResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nama_lengkap: str
    email: EmailStr
    phone: str
    tanggal_lahir: date
    alamat: str
    program_studi_id: int
    jalur_masuk_id: int
    status: Literal["pending", "approved", "rejected"]
    nim: str | None
    created_at: datetime
    approved_at: datetime | None


# Data statistik pendaftaran
class PMBStatsResponse(BaseModel):
    total_pendaftar: int
    pending: int
    approved: int
    rejected: int
