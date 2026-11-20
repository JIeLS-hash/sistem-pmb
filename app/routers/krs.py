from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.matakuliah import MataKuliah
from app.schemas.krs import (
    ApproveKRSRequest,
    CourseActionRequest,
    KRSResponse,
    MataKuliahResponse,
    RejectKRSRequest,
    SubmitKRSRequest,
    ValidationResponse,
)
from app.services.krs_manager import (
    DEFAULT_SEMESTER,
    InvalidStateTransitionError,
    KRSBusinessError,
    KRSManager,
    KRSNotFoundError,
)

router = APIRouter(prefix="/api/krs", tags=["KRS"])


def _handle_krs_error(exc: Exception) -> HTTPException:
    if isinstance(exc, KRSNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, InvalidStateTransitionError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    if isinstance(exc, KRSBusinessError):
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)
    )


@router.get("/matakuliah", response_model=list[MataKuliahResponse])
def list_matakuliah(db: Session = Depends(get_db)):
    return db.scalars(select(MataKuliah).order_by(MataKuliah.kode_mk)).all()


@router.get("/{nim}", response_model=KRSResponse)
def get_krs_mahasiswa(
    nim: str,
    semester: str = Query(default=DEFAULT_SEMESTER),
    db: Session = Depends(get_db),
):
    manager = KRSManager(db, semester=semester)
    try:
        return manager.get_krs(nim)
    except KRSBusinessError as exc:
        raise _handle_krs_error(exc)


@router.post("/add-course", response_model=KRSResponse, status_code=status.HTTP_201_CREATED)
def add_course_to_krs(payload: CourseActionRequest, db: Session = Depends(get_db)):
    manager = KRSManager(db, semester=payload.semester)
    try:
        return manager.add_course(payload.nim, payload.kode_mk)
    except KRSBusinessError as exc:
        raise _handle_krs_error(exc)


@router.delete("/remove-course", response_model=KRSResponse)
def remove_course_from_krs(payload: CourseActionRequest, db: Session = Depends(get_db)):
    manager = KRSManager(db, semester=payload.semester)
    try:
        return manager.remove_course(payload.nim, payload.kode_mk)
    except KRSBusinessError as exc:
        raise _handle_krs_error(exc)


@router.get("/{nim}/validate", response_model=ValidationResponse)
def validate_krs_mahasiswa(
    nim: str,
    semester: str = Query(default=DEFAULT_SEMESTER),
    db: Session = Depends(get_db),
):
    manager = KRSManager(db, semester=semester)
    try:
        result = manager.validate_krs(nim)
        return ValidationResponse(is_valid=result.is_valid, message=result.message)
    except KRSBusinessError as exc:
        raise _handle_krs_error(exc)


@router.put("/submit", response_model=KRSResponse)
def submit_krs_mahasiswa(payload: SubmitKRSRequest, db: Session = Depends(get_db)):
    manager = KRSManager(db, semester=payload.semester)
    try:
        return manager.submit_krs(payload.nim)
    except KRSBusinessError as exc:
        raise _handle_krs_error(exc)


@router.put("/approve", response_model=KRSResponse)
def approve_krs_dosen_pa(payload: ApproveKRSRequest, db: Session = Depends(get_db)):
    manager = KRSManager(db, semester=payload.semester)
    try:
        return manager.approve_krs(payload.nim, payload.dosen_pa_id)
    except KRSBusinessError as exc:
        raise _handle_krs_error(exc)


@router.put("/reject", response_model=KRSResponse)
def reject_krs_dosen_pa(payload: RejectKRSRequest, db: Session = Depends(get_db)):
    manager = KRSManager(db, semester=payload.semester)
    try:
        return manager.reject_krs(
            payload.nim, payload.dosen_pa_id, payload.catatan_revisi
        )
    except KRSBusinessError as exc:
        raise _handle_krs_error(exc)