from __future__ import annotations

from datetime import date
from pathlib import Path
from urllib.parse import parse_qs, quote_plus

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.calon_mahasiswa import CalonMahasiswa
from app.models.matakuliah import MataKuliah
from app.schemas.nilai import (
    GradeHistoryOut,
    GradeOut,
    NilaiInputRequest,
    NilaiUpdateRequest,
)
from app.services.nilai_service import (
    NilaiBusinessError,
    calculate_ipk,
    calculate_ips,
    get_grade_history_by_nim,
    get_transcript,
    input_nilai,
    is_lulus_mk,
    tentukan_predikat,
    update_nilai,
    upsert_nilai,
)
from app.services.transcript_pdf import generate_transcript_pdf

router = APIRouter(prefix="/api/nilai", tags=["Nilai & Transkrip"])

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def _to_grade_out(db: Session, grade) -> GradeOut:
    return GradeOut(
        id=grade.id,
        nim=grade.nim,
        kode_mk=grade.kode_mk,
        semester=grade.semester,
        presensi=grade.presensi,
        nilai_huruf=grade.nilai_huruf,
        nilai_angka=grade.nilai_angka,
        status_lulus="LULUS" if is_lulus_mk(grade.nilai_huruf) else "TIDAK LULUS",
        updated_by=grade.updated_by,
        update_reason=grade.update_reason,
        created_at=grade.created_at,
        updated_at=grade.updated_at,
        ipk_terbaru=calculate_ipk(db, grade.nim),
    )


@router.get("/portal", response_class=HTMLResponse)
def portal_nilai(
    request: Request,
    nim: str | None = Query(default=None),
    success: str | None = Query(default=None),
    error: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    mahasiswa_list = (
        db.query(CalonMahasiswa)
        .filter(CalonMahasiswa.nim.is_not(None))
        .order_by(CalonMahasiswa.nim.asc())
        .all()
    )
    matakuliah_list = db.query(MataKuliah).order_by(MataKuliah.kode_mk.asc()).all()

    selected_nim = (nim or "").strip()
    if not selected_nim and mahasiswa_list:
        selected_nim = mahasiswa_list[0].nim or ""

    transcript = None
    histories = []
    local_error = error
    if selected_nim:
        try:
            transcript = get_transcript(db, selected_nim)
            histories = get_grade_history_by_nim(db, selected_nim)
        except LookupError as exc:
            local_error = str(exc)

    return templates.TemplateResponse(
        request,
        "nilai_portal.html",
        {
            "mahasiswa_list": mahasiswa_list,
            "matakuliah_list": matakuliah_list,
            "selected_nim": selected_nim,
            "transcript": transcript,
            "histories": histories,
            "success_msg": success,
            "error_msg": local_error,
        },
    )


@router.post("/portal/submit")
async def portal_submit_nilai(
    request: Request,
    db: Session = Depends(get_db),
):
    raw_body = (await request.body()).decode("utf-8")
    form = {k: v[0] for k, v in parse_qs(raw_body).items()}

    nim = form.get("nim", "").strip()
    kode_mk = form.get("kode_mk", "").strip().upper()
    semester = form.get("semester", "").strip()
    nilai_huruf = form.get("nilai_huruf", "").strip().upper()
    changed_by = form.get("changed_by", "Dosen Pengampu").strip()
    reason = form.get("reason", "Input nilai via portal web").strip()

    try:
        presensi = float(form.get("presensi", "0"))
    except ValueError:
        return RedirectResponse(
            url=f"/api/nilai/portal?nim={quote_plus(nim)}&error={quote_plus('Format angka presensi tidak valid.')}",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    try:
        grade, is_updated = upsert_nilai(
            db,
            nim=nim,
            kode_mk=kode_mk,
            semester=semester,
            presensi=presensi,
            nilai_huruf=nilai_huruf,
            changed_by=changed_by,
            reason=reason,
        )
        ipk_now = calculate_ipk(db, nim)
        aksi = "diperbarui (audit trail tercatat)" if is_updated else "disimpan"
        msg = f"Nilai {grade.kode_mk} ({grade.nilai_huruf}) untuk NIM {nim} berhasil {aksi}. IPK terbaru: {ipk_now:.2f}."
        return RedirectResponse(
            url=f"/api/nilai/portal?nim={quote_plus(nim)}&success={quote_plus(msg)}",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    except (NilaiBusinessError, LookupError, ValueError) as exc:
        return RedirectResponse(
            url=f"/api/nilai/portal?nim={quote_plus(nim)}&error={quote_plus(str(exc))}",
            status_code=status.HTTP_303_SEE_OTHER,
        )


@router.post("/", response_model=GradeOut, status_code=status.HTTP_201_CREATED)
def api_input_nilai(
    payload: NilaiInputRequest,
    db: Session = Depends(get_db),
):
    try:
        grade = input_nilai(
            db,
            nim=payload.nim,
            kode_mk=payload.kode_mk,
            semester=payload.semester,
            presensi=payload.presensi,
            nilai_huruf=payload.nilai_huruf,
            changed_by=payload.changed_by,
            reason=payload.reason,
        )
        return _to_grade_out(db, grade)
    except NilaiBusinessError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.put("/{grade_id}", response_model=GradeOut)
def api_update_nilai(
    grade_id: int,
    payload: NilaiUpdateRequest,
    db: Session = Depends(get_db),
):
    try:
        grade = update_nilai(
            db,
            grade_id=grade_id,
            nilai_huruf=payload.nilai_huruf,
            changed_by=payload.changed_by,
            reason=payload.reason,
            presensi=payload.presensi,
        )
        return _to_grade_out(db, grade)
    except NilaiBusinessError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get("/ips/{nim}")
def api_get_ips(
    nim: str,
    semester: str = Query(..., min_length=4),
    db: Session = Depends(get_db),
):
    ips = calculate_ips(db, nim, semester)
    return {"nim": nim, "semester": semester, "ips": ips}


@router.get("/ipk/{nim}")
def api_get_ipk(
    nim: str,
    db: Session = Depends(get_db),
):
    try:
        transcript = get_transcript(db, nim)
        return {
            "nim": nim,
            "ipk": transcript["summary"]["ipk"],
            "total_sks": transcript["summary"]["total_sks"],
            "predikat": transcript["summary"]["predikat"],
        }
    except LookupError:
        ipk = calculate_ipk(db, nim)
        return {
            "nim": nim,
            "ipk": ipk,
            "total_sks": 0,
            "predikat": tentukan_predikat(ipk, 0),
        }


@router.get("/history/{nim}", response_model=list[GradeHistoryOut])
def api_get_grade_history(
    nim: str,
    db: Session = Depends(get_db),
):
    return get_grade_history_by_nim(db, nim)


@router.get("/transcript/{nim}")
def api_get_transcript(
    nim: str,
    db: Session = Depends(get_db),
):
    try:
        return get_transcript(db, nim)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get("/transcript/{nim}/html", response_class=HTMLResponse)
def api_get_transcript_html(
    nim: str,
    request: Request,
    db: Session = Depends(get_db),
):
    try:
        transcript = get_transcript(db, nim)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    return templates.TemplateResponse(
        request,
        "transkrip.html",
        {
            "transcript": transcript,
            "tanggal_cetak": date.today().strftime("%d %B %Y"),
        },
    )


@router.get("/transcript/{nim}/pdf")
def api_download_transcript_pdf(
    nim: str,
    db: Session = Depends(get_db),
):
    try:
        transcript = get_transcript(db, nim)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    pdf_bytes = generate_transcript_pdf(transcript)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="transkrip_{nim}.pdf"'
        },
    )