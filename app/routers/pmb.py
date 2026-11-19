
from fastapi import APIRouter, Depends, HTTPException
from fastapi import status

from sqlalchemy.orm import Session
from sqlalchemy import func, text
from datetime import datetime

from app.services.nim_generator import generate_nim
from sqlalchemy.exc import IntegrityError

from app.database import get_db

from app.models.calon_mahasiswa import CalonMahasiswa
from app.models.program_studi import ProgramStudi
from app.models.jalur_masuk import JalurMasuk

from app.schemas.pmb import (
    CalonMahasiswaCreate,
    CalonMahasiswaResponse,
    PMBStatsResponse
)


router = APIRouter(
    prefix="/api/pmb",
    tags=["PMB"]
)


@router.post(
    "/register",
    response_model=CalonMahasiswaResponse,
    status_code=status.HTTP_201_CREATED
)
def register_mahasiswa(
    data: CalonMahasiswaCreate,
    db: Session = Depends(get_db)
):
    # 1. Normalisasi email
    email = str(data.email).lower()

    # 2. Memeriksa email yang sudah terdaftar
    existing_email = db.query(CalonMahasiswa).filter(
        func.lower(CalonMahasiswa.email) == email
    ).first()

    if existing_email:
        raise HTTPException(
            status_code=409,
            detail="Email sudah terdaftar"
        )

    # 3. Memeriksa program studi
    program = db.get(
        ProgramStudi,
        data.program_studi_id
    )

    if program is None:
        raise HTTPException(
            status_code=404,
            detail="Program studi tidak ditemukan"
        )

    # 4. Memeriksa jalur masuk
    jalur = db.get(
        JalurMasuk,
        data.jalur_masuk_id
    )

    if jalur is None:
        raise HTTPException(
            status_code=404,
            detail="Jalur masuk tidak ditemukan"
        )

    # 5. Membuat objek calon mahasiswa
    mahasiswa = CalonMahasiswa(
        nama_lengkap=data.nama_lengkap,
        email=email,
        phone=data.phone,
        tanggal_lahir=data.tanggal_lahir,
        alamat=data.alamat,
        program_studi_id=data.program_studi_id,
        jalur_masuk_id=data.jalur_masuk_id,
        status="pending"
    )

    # 6. Menyimpan ke database
    try:
        db.add(mahasiswa)
        db.commit()
        db.refresh(mahasiswa)

    except IntegrityError as exc:
        db.rollback()

        raise HTTPException(
            status_code=409,
            detail="Email sudah terdaftar atau data melanggar constraint database"
        ) from exc

    # 7. Mengembalikan data mahasiswa
    return mahasiswa


@router.get(
    "/status/{id}",
    response_model=CalonMahasiswaResponse
)
def cek_status_pendaftaran(
    id: int,
    db: Session = Depends(get_db)
):
    # Mencari calon mahasiswa berdasarkan ID
    mahasiswa = db.get(CalonMahasiswa, id)

    # Jika data tidak ditemukan
    if mahasiswa is None:
        raise HTTPException(
            status_code=404,
            detail="Data pendaftaran tidak ditemukan"
        )

    # Mengembalikan data mahasiswa
    return mahasiswa


@router.put(
    "/approve/{id}",
    response_model=CalonMahasiswaResponse
)
def approve_mahasiswa(
    id: int,
    db: Session = Depends(get_db)
):
    try:
        # Mengunci transaksi penulisan SQLite
        # agar dua persetujuan tidak membuat NIM yang sama
        db.execute(text("BEGIN IMMEDIATE"))

        # 1. Mencari calon mahasiswa
        mahasiswa = db.get(CalonMahasiswa, id)

        if mahasiswa is None:
            raise HTTPException(
                status_code=404,
                detail="Data pendaftaran tidak ditemukan"
            )

        # 2. Memeriksa apakah sudah disetujui
        # Jika sudah, kembalikan data tanpa membuat NIM baru
        if mahasiswa.status == "approved" and mahasiswa.nim:
            db.commit()
            return mahasiswa

        # 3. Mahasiswa yang ditolak tidak boleh disetujui
        if mahasiswa.status == "rejected":
            raise HTTPException(
                status_code=400,
                detail="Pendaftaran yang ditolak tidak dapat disetujui"
            )

        # 4. Mengambil data program studi
        program = db.get(
            ProgramStudi,
            mahasiswa.program_studi_id
        )

        if program is None:
            raise HTTPException(
                status_code=404,
                detail="Program studi tidak ditemukan"
            )

        # 5. Menentukan tahun saat persetujuan
        tahun = datetime.now().year

        # 6. Membuat NIM otomatis
        mahasiswa.nim = generate_nim(
            tahun=tahun,
            kode_prodi=program.kode,
            db=db
        )

        # 7. Mengubah status pendaftaran
        mahasiswa.status = "approved"
        mahasiswa.approved_at = datetime.now()

        # 8. Menyimpan perubahan
        db.commit()
        db.refresh(mahasiswa)

        return mahasiswa

    except HTTPException:
        db.rollback()
        raise

    except IntegrityError as exc:
        db.rollback()

        raise HTTPException(
            status_code=409,
            detail="Terjadi konflik saat membuat NIM"
        ) from exc

    except ValueError as exc:
        db.rollback()

        raise HTTPException(
            status_code=409,
            detail=str(exc)
        ) from exc


@router.get(
    "/stats",
    response_model=PMBStatsResponse
)
def get_pmb_stats(
    db: Session = Depends(get_db)
):
    # Menghitung seluruh pendaftar
    total = db.query(
        func.count(CalonMahasiswa.id)
    ).scalar() or 0

    # Menghitung pendaftar berdasarkan status
    pending = db.query(
        func.count(CalonMahasiswa.id)
    ).filter(
        CalonMahasiswa.status == "pending"
    ).scalar() or 0

    approved = db.query(
        func.count(CalonMahasiswa.id)
    ).filter(
        CalonMahasiswa.status == "approved"
    ).scalar() or 0

    rejected = db.query(
        func.count(CalonMahasiswa.id)
    ).filter(
        CalonMahasiswa.status == "rejected"
    ).scalar() or 0

    return {
        "total_pendaftar": total,
        "pending": pending,
        "approved": approved,
        "rejected": rejected
    }
