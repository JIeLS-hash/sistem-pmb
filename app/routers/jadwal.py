from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.jadwal import (
    ConflictReportResponse,
    JadwalCreate,
    JadwalResponse,
    JadwalUpdate,
)
from app.services.scheduling_service import (
    SchedulingConflictError,
    SchedulingNotFoundError,
    SchedulingService,
    SchedulingValidationError,
)

router = APIRouter(prefix="/api/jadwal", tags=["Jadwal & Ruangan"])


@router.get("/conflicts", response_model=ConflictReportResponse)
def get_schedule_conflicts(db: Session = Depends(get_db)) -> dict:
    """Melaporkan seluruh jadwal bentrok (ruangan & dosen) menggunakan algoritma sweep-line."""
    return SchedulingService.get_all_conflicts(db)


@router.get("", response_model=list[JadwalResponse])
def list_schedules(
    hari: int | None = Query(default=None, ge=1, le=6),
    ruangan_kode: str | None = Query(default=None),
    dosen_id: int | None = Query(default=None, gt=0),
    kelas_id: int | None = Query(default=None, gt=0),
    db: Session = Depends(get_db),
):
    """Menampilkan daftar jadwal kuliah dengan filter opsional."""
    return SchedulingService.list_jadwal(
        db,
        hari=hari,
        ruangan_kode=ruangan_kode,
        dosen_id=dosen_id,
        kelas_id=kelas_id,
    )


@router.get("/{jadwal_id}", response_model=JadwalResponse)
def get_schedule_detail(jadwal_id: int, db: Session = Depends(get_db)):
    """Mengambil detail satu jadwal kuliah berdasarkan ID."""
    try:
        return SchedulingService.get_jadwal(db, jadwal_id)
    except SchedulingNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("", response_model=JadwalResponse, status_code=status.HTTP_201_CREATED)
def create_schedule(payload: JadwalCreate, db: Session = Depends(get_db)):
    """Membuat jadwal kuliah baru dengan pengecekan kapasitas dan bentrok 3 dimensi."""
    try:
        return SchedulingService.create_jadwal(db, payload)
    except SchedulingNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except SchedulingValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    except SchedulingConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=exc.to_detail()
        ) from exc


@router.put("/{jadwal_id}", response_model=JadwalResponse)
def update_schedule(
    jadwal_id: int, payload: JadwalUpdate, db: Session = Depends(get_db)
):
    """Memperbarui jadwal kuliah dengan pengecekan kapasitas dan bentrok 3 dimensi."""
    try:
        return SchedulingService.update_jadwal(db, jadwal_id, payload)
    except SchedulingNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except SchedulingValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    except SchedulingConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=exc.to_detail()
        ) from exc


@router.delete("/{jadwal_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_schedule(jadwal_id: int, db: Session = Depends(get_db)) -> Response:
    """Menghapus jadwal kuliah berdasarkan ID."""
    try:
        SchedulingService.delete_jadwal(db, jadwal_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except SchedulingNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc