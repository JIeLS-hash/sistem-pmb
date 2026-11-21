from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Response, status
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.jadwal import (
    ConflictReportResponse,
    JadwalCreate,
    JadwalResponse,
    JadwalUpdate,
    RescheduleSuggestRequest,
    RescheduleSuggestResponse,
)
from app.services.ai_rescheduler import AIRescheduler
from app.services.ics_exporter import export_schedules_to_ics
from app.services.observer import notification_manager
from app.services.scheduling_service import (
    SchedulingConflictError,
    SchedulingNotFoundError,
    SchedulingService,
    SchedulingValidationError,
)

router = APIRouter(prefix="/api/jadwal", tags=["Jadwal & Ruangan"])

router = APIRouter(prefix="/api/jadwal", tags=["Jadwal & Ruangan"])

DASHBOARD_TEMPLATE_PATH = (
    Path(__file__).resolve().parent.parent / "templates" / "conflict_resolver.html"
)


@router.get("/dashboard", response_class=HTMLResponse)
def conflict_resolver_dashboard() -> HTMLResponse:
    """Menampilkan halaman web Conflict Resolver UI untuk Admin Akademik."""
    html = DASHBOARD_TEMPLATE_PATH.read_text(encoding="utf-8")
    return HTMLResponse(content=html)


@router.get("/conflicts", response_model=ConflictReportResponse)

def get_schedule_conflicts(db: Session = Depends(get_db)) -> dict:
    """Melaporkan seluruh jadwal bentrok (ruangan & dosen) menggunakan algoritma sweep-line."""
    return SchedulingService.get_all_conflicts(db)


@router.get("/export/ics")
def export_jadwal_ics(
    hari: int | None = Query(default=None, ge=1, le=6),
    ruangan_kode: str | None = Query(default=None),
    dosen_id: int | None = Query(default=None, gt=0),
    kelas_id: int | None = Query(default=None, gt=0),
    db: Session = Depends(get_db),
) -> Response:
    """Mengekspor jadwal kuliah dalam format iCalendar (.ics) yang dapat diimpor ke Google/Outlook Calendar."""
    schedules = SchedulingService.list_jadwal(
        db,
        hari=hari,
        ruangan_kode=ruangan_kode,
        dosen_id=dosen_id,
        kelas_id=kelas_id,
    )
    ics_content = export_schedules_to_ics(db, schedules=schedules)
    return Response(
        content=ics_content,
        media_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="jadwal_kuliah.ics"'},
    )


@router.get("/notifications")
def get_notification_logs() -> dict[str, Any]:
    """Menampilkan log notifikasi lintas kanal (EMAIL, SMS, PUSH) dari Observer Pattern."""
    return {
        "total_logs": len(notification_manager.logs),
        "errors": notification_manager.subject.errors,
        "logs": list(reversed(notification_manager.logs)),
    }


@router.post(
    "/{jadwal_id}/suggest-reschedule",
    response_model=RescheduleSuggestResponse,
)
def suggest_reschedule_with_ai(
    jadwal_id: int,
    payload: RescheduleSuggestRequest | None = Body(default=None),
    db: Session = Depends(get_db),
):
    """Menghasilkan alternatif jadwal bebas bentrok menggunakan Prompt Step 3 + saringan validator."""
    req = payload or RescheduleSuggestRequest()
    try:
        return AIRescheduler.suggest_reschedule_options(
            db,
            jadwal_id=jadwal_id,
            raw_candidates=req.raw_candidates,
            limit=req.limit,
        )
    except SchedulingNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


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