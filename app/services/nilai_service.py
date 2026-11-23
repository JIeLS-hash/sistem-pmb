from __future__ import annotations

from collections import defaultdict
from typing import Any

from sqlalchemy.orm import Session

from app.models.calon_mahasiswa import CalonMahasiswa
from app.models.matakuliah import MataKuliah
from app.models.nilai import GRADE_SCALE, PASSING_GRADES, Grade, GradeHistory
from app.models.riwayat_nilai import RiwayatNilai
from app.models.skala_nilai import SkalaNilai

MIN_PRESENSI_PERSEN = 75.0


class NilaiBusinessError(ValueError):
    """Exception untuk pelanggaran aturan bisnis penilaian."""


def konversi_huruf_ke_angka(nilai_huruf: str) -> float:
    huruf = nilai_huruf.strip().upper()
    if huruf not in GRADE_SCALE:
        raise NilaiBusinessError(f"Nilai huruf tidak valid: {nilai_huruf}")
    return GRADE_SCALE[huruf]


def is_lulus_mk(nilai_huruf: str) -> bool:
    return nilai_huruf.strip().upper() in PASSING_GRADES


def tentukan_predikat(ipk: float, total_sks_lulus: int) -> str:
    if total_sks_lulus <= 0 or ipk <= 0.0:
        return "Belum Ada Nilai"
    if ipk >= 3.50:
        return "Cum Laude (Dengan Pujian)"
    if ipk >= 3.00:
        return "Sangat Memuaskan"
    if ipk >= 2.75:
        return "Memuaskan"
    if ipk >= 2.00:
        return "Cukup"
    return "Kurang"


def _sync_riwayat_nilai(
    db: Session, nim: str, kode_mk: str, semester: str, nilai_huruf: str
) -> None:
    """Menyinkronkan ke tabel riwayat_nilai untuk pengecekan prasyarat KRS jika skala tersedia."""
    if not db.query(SkalaNilai).filter_by(huruf=nilai_huruf).first():
        return
    existing = (
        db.query(RiwayatNilai)
        .filter_by(nim=nim, kode_mk=kode_mk, semester=semester)
        .first()
    )
    if existing:
        existing.nilai_huruf = nilai_huruf
    else:
        db.add(
            RiwayatNilai(
                nim=nim,
                kode_mk=kode_mk,
                semester=semester,
                nilai_huruf=nilai_huruf,
            )
        )


def input_nilai(
    db: Session,
    *,
    nim: str,
    kode_mk: str,
    semester: str,
    presensi: float,
    nilai_huruf: str,
    changed_by: str = "Dosen Pengampu",
    reason: str = "Input nilai akhir semester",
) -> Grade:
    if presensi < MIN_PRESENSI_PERSEN:
        raise NilaiBusinessError(
            f"Nilai tidak dapat diinput karena presensi ({presensi:.1f}%) kurang dari {MIN_PRESENSI_PERSEN:.0f}%."
        )

    mhs = db.query(CalonMahasiswa).filter_by(nim=nim).first()
    if not mhs:
        raise LookupError(f"Mahasiswa dengan NIM '{nim}' tidak ditemukan.")

    mk = db.query(MataKuliah).filter_by(kode_mk=kode_mk).first()
    if not mk:
        raise LookupError(f"Mata kuliah dengan kode '{kode_mk}' tidak ditemukan.")

    existing = (
        db.query(Grade)
        .filter_by(nim=nim, kode_mk=kode_mk, semester=semester)
        .first()
    )
    if existing:
        raise NilaiBusinessError(
            f"Nilai untuk NIM {nim} pada MK {kode_mk} semester {semester} sudah ada (ID={existing.id}). Gunakan fitur edit nilai."
        )

    huruf = nilai_huruf.strip().upper()
    angka = konversi_huruf_ke_angka(huruf)

    grade = Grade(
        nim=nim,
        kode_mk=kode_mk,
        semester=semester,
        presensi=presensi,
        nilai_huruf=huruf,
        nilai_angka=angka,
        updated_by=changed_by,
        update_reason=reason,
    )
    db.add(grade)
    _sync_riwayat_nilai(db, nim, kode_mk, semester, huruf)
    db.commit()
    db.refresh(grade)
    return grade


def update_nilai(
    db: Session,
    *,
    grade_id: int,
    nilai_huruf: str,
    changed_by: str,
    reason: str,
    presensi: float | None = None,
) -> Grade:
    grade = db.query(Grade).filter_by(id=grade_id).first()
    if not grade:
        raise LookupError(f"Data nilai dengan ID {grade_id} tidak ditemukan.")

    effective_presensi = presensi if presensi is not None else grade.presensi
    if effective_presensi < MIN_PRESENSI_PERSEN:
        raise NilaiBusinessError(
            f"Nilai tidak dapat diperbarui karena presensi ({effective_presensi:.1f}%) kurang dari {MIN_PRESENSI_PERSEN:.0f}%."
        )

    huruf = nilai_huruf.strip().upper()
    angka = konversi_huruf_ke_angka(huruf)

    grade.presensi = effective_presensi
    grade.nilai_huruf = huruf
    grade.nilai_angka = angka
    grade.updated_by = changed_by
    grade.update_reason = reason

    _sync_riwayat_nilai(db, grade.nim, grade.kode_mk, grade.semester, huruf)
    db.commit()
    db.refresh(grade)
    return grade


def upsert_nilai(
    db: Session,
    *,
    nim: str,
    kode_mk: str,
    semester: str,
    presensi: float,
    nilai_huruf: str,
    changed_by: str,
    reason: str,
) -> tuple[Grade, bool]:
    """Menyimpan nilai baru atau memperbarui jika sudah ada (mengembalikan tuple (Grade, is_updated))."""
    existing = (
        db.query(Grade)
        .filter_by(nim=nim, kode_mk=kode_mk, semester=semester)
        .first()
    )
    if existing:
        updated = update_nilai(
            db,
            grade_id=existing.id,
            nilai_huruf=nilai_huruf,
            changed_by=changed_by,
            reason=reason,
            presensi=presensi,
        )
        return updated, True

    created = input_nilai(
        db,
        nim=nim,
        kode_mk=kode_mk,
        semester=semester,
        presensi=presensi,
        nilai_huruf=nilai_huruf,
        changed_by=changed_by,
        reason=reason,
    )
    return created, False


def get_grade_history_by_nim(db: Session, nim: str) -> list[dict[str, Any]]:
    rows = (
        db.query(GradeHistory, Grade)
        .join(Grade, GradeHistory.grade_id == Grade.id)
        .filter(Grade.nim == nim)
        .order_by(GradeHistory.id.desc())
        .all()
    )
    return [
        {
            "id": hist.id,
            "grade_id": hist.grade_id,
            "kode_mk": grade.kode_mk,
            "semester": grade.semester,
            "old_value": hist.old_value,
            "new_value": hist.new_value,
            "changed_by": hist.changed_by,
            "changed_at": hist.changed_at,
            "reason": hist.reason,
        }
        for hist, grade in rows
    ]


def calculate_ips(db: Session, nim: str, semester: str) -> float:
    """Menghitung Indeks Prestasi Semester (IPS)."""
    rows = (
        db.query(Grade, MataKuliah)
        .join(MataKuliah, Grade.kode_mk == MataKuliah.kode_mk)
        .filter(Grade.nim == nim, Grade.semester == semester)
        .all()
    )
    if not rows:
        return 0.0

    total_sks = sum(mk.sks for _, mk in rows)
    if total_sks <= 0:
        return 0.0

    total_mutu = sum(mk.sks * grade.nilai_angka for grade, mk in rows)
    return round(total_mutu / total_sks, 2)


def calculate_ipk(db: Session, nim: str) -> float:
    """
    Menghitung Indeks Prestasi Kumulatif (IPK):
    - IPK = Sigma(SKS x Nilai Angka) / Sigma(SKS)
    - Hanya menghitung MK yang lulus (nilai >= D)
    - Jika MK diulang, mengambil nilai tertinggi
    - Jika mahasiswa belum memiliki nilai lulus, mengembalikan 0.0
    """
    rows = (
        db.query(Grade, MataKuliah)
        .join(MataKuliah, Grade.kode_mk == MataKuliah.kode_mk)
        .filter(Grade.nim == nim)
        .all()
    )
    if not rows:
        return 0.0

    best_by_mk: dict[str, tuple[Grade, MataKuliah]] = {}
    for grade, mk in rows:
        current_best = best_by_mk.get(mk.kode_mk)
        if current_best is None or grade.nilai_angka > current_best[0].nilai_angka:
            best_by_mk[mk.kode_mk] = (grade, mk)

    passed_items = [
        (grade, mk)
        for grade, mk in best_by_mk.values()
        if is_lulus_mk(grade.nilai_huruf)
    ]
    if not passed_items:
        return 0.0

    total_sks = sum(mk.sks for _, mk in passed_items)
    if total_sks <= 0:
        return 0.0

    total_mutu = sum(mk.sks * grade.nilai_angka for grade, mk in passed_items)
    return round(total_mutu / total_sks, 2)


def get_transcript(db: Session, nim: str) -> dict[str, Any]:
    """Mengambil rekam akademik lengkap mahasiswa untuk tampilan web dan generator PDF."""
    mhs = db.query(CalonMahasiswa).filter_by(nim=nim).first()
    if not mhs:
        raise LookupError(f"Mahasiswa dengan NIM '{nim}' tidak ditemukan.")

    prodi_nama = mhs.program_studi.nama if mhs.program_studi else "-"
    fakultas_nama = mhs.program_studi.fakultas if mhs.program_studi else "Fakultas Ilmu Komputer"
    angkatan = (
        mhs.nim[:4]
        if mhs.nim and len(mhs.nim) >= 4 and mhs.nim[:4].isdigit()
        else str(mhs.created_at.year)
    )

    rows = (
        db.query(Grade, MataKuliah)
        .join(MataKuliah, Grade.kode_mk == MataKuliah.kode_mk)
        .filter(Grade.nim == nim)
        .order_by(Grade.semester.asc(), MataKuliah.kode_mk.asc())
        .all()
    )

    grouped: dict[str, list[tuple[Grade, MataKuliah]]] = defaultdict(list)
    best_by_mk: dict[str, tuple[Grade, MataKuliah]] = {}

    for grade, mk in rows:
        grouped[grade.semester].append((grade, mk))
        prev = best_by_mk.get(mk.kode_mk)
        if prev is None or grade.nilai_angka > prev[0].nilai_angka:
            best_by_mk[mk.kode_mk] = (grade, mk)

    semester_records: list[dict[str, Any]] = []
    for smt in sorted(grouped.keys()):
        items = grouped[smt]
        courses_list = []
        sks_smt = 0
        mutu_smt = 0.0
        for grade, mk in items:
            mutu = round(mk.sks * grade.nilai_angka, 2)
            sks_smt += mk.sks
            mutu_smt += mutu
            courses_list.append(
                {
                    "grade_id": grade.id,
                    "kode_mk": mk.kode_mk,
                    "nama_mk": mk.nama,
                    "sks": mk.sks,
                    "presensi": grade.presensi,
                    "nilai_huruf": grade.nilai_huruf,
                    "nilai_angka": grade.nilai_angka,
                    "mutu": mutu,
                    "status_lulus": "LULUS" if is_lulus_mk(grade.nilai_huruf) else "TIDAK LULUS",
                }
            )
        ips = round(mutu_smt / sks_smt, 2) if sks_smt > 0 else 0.0
        semester_records.append(
            {
                "semester": smt,
                "courses": courses_list,
                "total_sks": sks_smt,
                "total_mutu": round(mutu_smt, 2),
                "ips": ips,
            }
        )

    passed_best = [
        (grade, mk)
        for grade, mk in best_by_mk.values()
        if is_lulus_mk(grade.nilai_huruf)
    ]
    total_sks_lulus = sum(mk.sks for _, mk in passed_best)
    total_mutu_kumulatif = round(
        sum(mk.sks * grade.nilai_angka for grade, mk in passed_best), 2
    )
    ipk = calculate_ipk(db, nim)
    predikat = tentukan_predikat(ipk, total_sks_lulus)

    return {
        "biodata": {
            "nim": mhs.nim,
            "nama": mhs.nama_lengkap,
            "program_studi": prodi_nama,
            "fakultas": fakultas_nama,
            "angkatan": angkatan,
        },
        "semesters": semester_records,
        "summary": {
            "total_sks": total_sks_lulus,
            "total_mutu": total_mutu_kumulatif,
            "ipk": ipk,
            "predikat": predikat,
        },
    }