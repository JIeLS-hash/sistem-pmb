from __future__ import annotations

from datetime import date, time
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.calon_mahasiswa import CalonMahasiswa
from app.models.jalur_masuk import JalurMasuk
from app.models.matakuliah import MataKuliah
from app.models.nilai import Grade, GradeHistory
from app.models.program_studi import ProgramStudi
from app.services.nilai_service import (
    NilaiBusinessError,
    calculate_ipk,
    calculate_ips,
    get_grade_history_by_nim,
    get_transcript,
    input_nilai,
    tentukan_predikat,
    update_nilai,
)


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()

    # Seed master data minimal
    prodi = ProgramStudi(kode="TIF", nama="Teknik Informatika", fakultas="Fakultas Ilmu Komputer")
    jalur = JalurMasuk(nama="SNBP")
    db.add_all([prodi, jalur])
    db.flush()

    mhs1 = CalonMahasiswa(
        nama_lengkap="Ahmad Fauzi",
        email="ahmad.fauzi@example.com",
        phone="081234567890",
        tanggal_lahir=date(2005, 5, 10),
        alamat="Jl. Margonda Raya No. 1, Depok",
        program_studi_id=prodi.id,
        jalur_masuk_id=jalur.id,
        status="approved",
        nim="2026TIF0001",
    )
    mhs2 = CalonMahasiswa(
        nama_lengkap="Siti Aminah",
        email="siti.aminah@example.com",
        phone="081298765432",
        tanggal_lahir=date(2006, 2, 15),
        alamat="Jl. Kukusan Teknik No. 2, Depok",
        program_studi_id=prodi.id,
        jalur_masuk_id=jalur.id,
        status="approved",
        nim="2026TIF0002",
    )
    db.add_all([mhs1, mhs2])

    mk_list = [
        MataKuliah(kode_mk="IF101", nama="Algoritma & Pemrograman", sks=4, semester_paket=1, is_wajib=True, hari="Senin", jam_mulai=time(8, 0), jam_selesai=time(10, 0)),
        MataKuliah(kode_mk="IF102", nama="Struktur Data", sks=3, semester_paket=2, is_wajib=True, hari="Selasa", jam_mulai=time(8, 0), jam_selesai=time(10, 0)),
        MataKuliah(kode_mk="IF103", nama="Basis Data", sks=3, semester_paket=2, is_wajib=True, hari="Rabu", jam_mulai=time(10, 0), jam_selesai=time(12, 0)),
        MataKuliah(kode_mk="IF104", nama="Jaringan Komputer", sks=2, semester_paket=3, is_wajib=True, hari="Kamis", jam_mulai=time(13, 0), jam_selesai=time(15, 0)),
    ]
    db.add_all(mk_list)
    db.commit()

    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ==============================================================================
# 13+ KASUS PENGUJIAN PERHITUNGAN IPK & PREDIKAT
# ==============================================================================

@pytest.mark.parametrize(
    "case_name, records, expected_ipk",
    [
        (
            "1_mahasiswa_semester_awal_belum_ada_nilai",
            [],
            0.0,
        ),
        (
            "2_nilai_sempurna_semua_A",
            [
                ("IF101", "2026/2027-1", "A"),
                ("IF102", "2026/2027-1", "A"),
                ("IF103", "2026/2027-2", "A"),
            ],
            4.0,
        ),
        (
            "3_kombinasi_A_B_C_bobot_berbeda",
            # (4*4.0 + 3*3.0 + 3*2.0) / (4+3+3) = (16+9+6)/10 = 3.10
            [
                ("IF101", "2026/2027-1", "A"),
                ("IF102", "2026/2027-1", "B"),
                ("IF103", "2026/2027-2", "C"),
            ],
            3.10,
        ),
        (
            "4_mk_tidak_lulus_E_dikecualikan_dari_ipk",
            # IF101 (4 sks, A=4.0), IF102 (3 sks, E=0.0 -> tidak lulus) => IPK = 16 / 4 = 4.0
            [
                ("IF101", "2026/2027-1", "A"),
                ("IF102", "2026/2027-1", "E"),
            ],
            4.0,
        ),
        (
            "5_semua_mk_tidak_lulus_E",
            [
                ("IF101", "2026/2027-1", "E"),
                ("IF102", "2026/2027-1", "E"),
            ],
            0.0,
        ),
        (
            "6_nilai_batas_lulus_minimum_D",
            # IF101 (4 sks, D=1.0), IF102 (3 sks, B=3.0) => (4 + 9)/7 = 1.86
            [
                ("IF101", "2026/2027-1", "D"),
                ("IF102", "2026/2027-1", "B"),
            ],
            1.86,
        ),
        (
            "7_mk_diulang_dari_D_menjadi_B_ambil_tertinggi",
            # IF101 diambil 2x (D=1.0 lalu B=3.0 -> ambil B=3.0) => 12/4 = 3.0
            [
                ("IF101", "2026/2027-1", "D"),
                ("IF101", "2026/2027-2", "B"),
            ],
            3.0,
        ),
        (
            "8_mk_diulang_dari_E_menjadi_A_sks_dihitung_sekali",
            # IF101 (E -> A), IF102 (B) => (4*4.0 + 3*3.0) / 7 = 25/7 = 3.57
            [
                ("IF101", "2026/2027-1", "E"),
                ("IF101", "2026/2027-2", "A"),
                ("IF102", "2026/2027-2", "B"),
            ],
            3.57,
        ),
        (
            "9_mk_diulang_nilai_kedua_lebih_rendah_tetap_ambil_tertinggi",
            # IF102 diambil B lalu C -> tetap ambil B (3.0)
            [
                ("IF102", "2026/2027-1", "B"),
                ("IF102", "2026/2027-2", "C"),
            ],
            3.0,
        ),
        (
            "10_mk_diulang_tiga_kali_E_D_A",
            [
                ("IF103", "2026/2027-1", "E"),
                ("IF103", "2026/2027-2", "D"),
                ("IF103", "2027/2028-1", "A"),
            ],
            4.0,
        ),
        (
            "11_kombinasi_4_mk_beragam",
            # (4*4 + 3*3 + 3*3 + 2*2) / 12 = (16+9+9+4)/12 = 38/12 = 3.17
            [
                ("IF101", "2026/2027-1", "A"),
                ("IF102", "2026/2027-1", "B"),
                ("IF103", "2026/2027-2", "B"),
                ("IF104", "2026/2027-2", "C"),
            ],
            3.17,
        ),
        (
            "12_batas_cum_laude_3_50",
            # IF101 (4 sks, A=4.0), IF104 (2 sks, B=3.0) => (16+6)/6 = 3.67
            [
                ("IF101", "2026/2027-1", "A"),
                ("IF104", "2026/2027-1", "B"),
            ],
            3.67,
        ),
    ],
)
def test_calculate_ipk_scenarios(db_session, case_name, records, expected_ipk):
    nim = "2026TIF0001"
    for kode_mk, smt, huruf in records:
        input_nilai(
            db_session,
            nim=nim,
            kode_mk=kode_mk,
            semester=smt,
            presensi=95.0,
            nilai_huruf=huruf,
        )
    assert calculate_ipk(db_session, nim) == expected_ipk


def test_predikat_kelulusan():
    assert tentukan_predikat(0.0, 0) == "Belum Ada Nilai"
    assert tentukan_predikat(3.75, 20) == "Cum Laude (Dengan Pujian)"
    assert tentukan_predikat(3.50, 20) == "Cum Laude (Dengan Pujian)"
    assert tentukan_predikat(3.25, 20) == "Sangat Memuaskan"
    assert tentukan_predikat(2.85, 20) == "Memuaskan"
    assert tentukan_predikat(2.20, 20) == "Cukup"


def test_calculate_ips_per_semester(db_session):
    nim = "2026TIF0001"
    input_nilai(db_session, nim=nim, kode_mk="IF101", semester="2026/2027-1", presensi=90.0, nilai_huruf="A")
    input_nilai(db_session, nim=nim, kode_mk="IF102", semester="2026/2027-1", presensi=85.0, nilai_huruf="C")
    # Semester 1: (4*4.0 + 3*2.0) / 7 = 22/7 = 3.14
    assert calculate_ips(db_session, nim, "2026/2027-1") == 3.14
    assert calculate_ips(db_session, nim, "2026/2027-2") == 0.0


# ==============================================================================
# PENGUJIAN ATURAN PRESENSI (< 75%), AUDIT TRAIL TRIGGER, & PDF TRANSKRIP
# ==============================================================================

def test_validasi_presensi_kurang_dari_75_ditolak(db_session):
    with pytest.raises(NilaiBusinessError, match="75%"):
        input_nilai(
            db_session,
            nim="2026TIF0001",
            kode_mk="IF101",
            semester="2026/2027-1",
            presensi=74.9,
            nilai_huruf="A",
        )

    # Tepat 75.0% harus diterima
    grade = input_nilai(
        db_session,
        nim="2026TIF0001",
        kode_mk="IF101",
        semester="2026/2027-1",
        presensi=75.0,
        nilai_huruf="B",
    )
    assert grade.nilai_huruf == "B"


def test_audit_trail_trigger_saat_update_nilai(db_session):
    nim = "2026TIF0001"
    grade = input_nilai(
        db_session,
        nim=nim,
        kode_mk="IF101",
        semester="2026/2027-1",
        presensi=92.0,
        nilai_huruf="C",
        changed_by="Dr. Andi",
        reason="Input nilai awal",
    )
    assert get_grade_history_by_nim(db_session, nim) == []

    # Lakukan UPDATE nilai -> trigger SQLite otomatis mencatat ke grade_history
    update_nilai(
        db_session,
        grade_id=grade.id,
        nilai_huruf="A",
        changed_by="Prof. Budi",
        reason="Koreksi nilai praktikum dan UAS",
    )

    histories = get_grade_history_by_nim(db_session, nim)
    assert len(histories) == 1
    assert histories[0]["grade_id"] == grade.id
    assert histories[0]["old_value"] == "C"
    assert histories[0]["new_value"] == "A"
    assert histories[0]["changed_by"] == "Prof. Budi"
    assert histories[0]["reason"] == "Koreksi nilai praktikum dan UAS"


def test_end_to_end_api_portal_dan_download_pdf(client):
    nim = "2026TIF0001"

    # 1. Input nilai via REST API
    res_post = client.post(
        "/api/nilai/",
        json={
            "nim": nim,
            "kode_mk": "IF101",
            "semester": "2026/2027-1",
            "presensi": 88.0,
            "nilai_huruf": "B",
            "changed_by": "Dr. Citra",
            "reason": "Input nilai semester 1",
        },
    )
    assert res_post.status_code == 201
    grade_id = res_post.json()["id"]
    assert res_post.json()["ipk_terbaru"] == 3.0

    # 2. Update nilai via REST API -> memicu audit trail & memperbarui IPK otomatis
    res_put = client.put(
        f"/api/nilai/{grade_id}",
        json={
            "nilai_huruf": "A",
            "changed_by": "Dr. Citra",
            "reason": "Revisi nilai setelah ujian susulan",
        },
    )
    assert res_put.status_code == 200
    assert res_put.json()["ipk_terbaru"] == 4.0

    # 3. Cek endpoint history per mahasiswa
    res_hist = client.get(f"/api/nilai/history/{nim}")
    assert res_hist.status_code == 200
    assert len(res_hist.json()) == 1
    assert res_hist.json()[0]["old_value"] == "B"
    assert res_hist.json()[0]["new_value"] == "A"

    # 4. Cek form web portal & HTML transkrip
    res_portal = client.get(f"/api/nilai/portal?nim={nim}")
    assert res_portal.status_code == 200
    assert "Ahmad Fauzi" in res_portal.text

    res_html = client.get(f"/api/nilai/transcript/{nim}/html")
    assert res_html.status_code == 200
    assert "TRANSKRIP AKADEMIK" in res_html.text

    # 5. Download PDF transkrip resmi
    res_pdf = client.get(f"/api/nilai/transcript/{nim}/pdf")
    assert res_pdf.status_code == 200
    assert res_pdf.headers["content-type"] == "application/pdf"
    assert res_pdf.content.startswith(b"%PDF-")