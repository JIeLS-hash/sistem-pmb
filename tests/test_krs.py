from datetime import date, time
import pytest
from fastapi.testclient import TestClient
from hypothesis import given, settings, strategies as st
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
import app.models  # noqa: F401 - memastikan seluruh model PMB & KRS terdaftar di Base.metadata
from app.main import app
from app.models.program_studi import ProgramStudi
from app.models.jalur_masuk import JalurMasuk
from app.models.calon_mahasiswa import CalonMahasiswa
from app.models.skala_nilai import SkalaNilai
from app.models.matakuliah import MataKuliah
from app.models.prerequisite import Prerequisite
from app.models.riwayat_nilai import RiwayatNilai
from app.services.krs_manager import KRSManager
from app.services.krs_validator import MAX_SKS_PER_SEMESTER


def _seed_base_data(db) -> str:
    """Mengisi data referensi dasar untuk pengujian KRS dan mengembalikan NIM mahasiswa."""
    for huruf, bobot in [("A", 4.0), ("B", 3.0), ("C", 2.0), ("D", 1.0), ("E", 0.0)]:
        db.add(SkalaNilai(huruf=huruf, bobot=bobot))

    prodi = ProgramStudi(kode="TIF", nama="Teknik Informatika", fakultas="Ilmu Komputer")
    jalur = JalurMasuk(nama="Reguler")
    db.add_all([prodi, jalur])
    db.flush()

    nim = "2026001001"
    mhs = CalonMahasiswa(
        nama_lengkap="Budi Santoso",
        email="budi.test@kampus.ac.id",
        phone="081234567890",
        tanggal_lahir=date(2005, 5, 14),
        alamat="Jl. Margonda Raya No. 100, Depok",
        program_studi_id=prodi.id,
        jalur_masuk_id=jalur.id,
        status="approved",
        nim=nim,
    )
    db.add(mhs)
    db.commit()
    return nim


@pytest.fixture()
def krs_client():
    """Fixture FastAPI TestClient dengan database SQLite in-memory terisolasi."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    db = TestingSessionLocal()
    nim = _seed_base_data(db)

    # Tambah data mata kuliah, prasyarat, dan riwayat nilai
    mk_list = [
        MataKuliah(
            kode_mk="IF101", nama="Algoritma", sks=4, semester_paket=1, is_wajib=True,
            hari="Senin", jam_mulai=time(8, 0), jam_selesai=time(10, 0)
        ),
        MataKuliah(
            kode_mk="IF102", nama="Kalkulus I", sks=3, semester_paket=1, is_wajib=True,
            hari="Selasa", jam_mulai=time(8, 0), jam_selesai=time(10, 0)
        ),
        MataKuliah(
            kode_mk="IF201", nama="Struktur Data", sks=4, semester_paket=2, is_wajib=True,
            hari="Rabu", jam_mulai=time(8, 0), jam_selesai=time(10, 30)
        ),
        MataKuliah(
            kode_mk="IF202", nama="Basis Data", sks=3, semester_paket=2, is_wajib=True,
            # Jadwal sengaja bentrok dengan IF201
            hari="Rabu", jam_mulai=time(9, 30), jam_selesai=time(11, 30)
        ),
        MataKuliah(
            kode_mk="IF203", nama="Aljabar Linear", sks=3, semester_paket=2, is_wajib=True,
            hari="Kamis", jam_mulai=time(10, 0), jam_selesai=time(12, 0)
        ),
    ]
    db.add_all(mk_list)
    db.flush()

    db.add_all([
        Prerequisite(kode_mk="IF201", kode_mk_prasyarat="IF101", min_nilai_huruf="C"),
        Prerequisite(kode_mk="IF203", kode_mk_prasyarat="IF102", min_nilai_huruf="C"),
    ])
    # IF101 lulus (B >= C), IF102 tidak lulus (D < C)
    db.add_all([
        RiwayatNilai(nim=nim, kode_mk="IF101", semester="2025/2026-1", nilai_huruf="B"),
        RiwayatNilai(nim=nim, kode_mk="IF102", semester="2025/2026-1", nilai_huruf="D"),
    ])
    db.commit()

    def override_get_db():
        session = TestingSessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client, nim
    app.dependency_overrides.clear()
    db.close()
    engine.dispose()

# =====================================================================
# 1. UNIT & INTEGRATION TESTS (API, VALIDATION CHAIN, & STATE MACHINE)
# =====================================================================

def test_add_and_remove_course_via_api(krs_client):
    client, nim = krs_client

    # Tambah IF201 (prasyarat IF101 lulus nilai B -> sukses)
    res_add = client.post("/api/krs/add-course", json={"nim": nim, "kode_mk": "IF201"})
    assert res_add.status_code == 201
    data = res_add.json()
    assert data["status"] == "DRAFT"
    assert data["total_sks"] == 4
    assert len(data["details"]) == 1

    # Hapus IF201 -> total SKS kembali 0
    res_del = client.request(
        "DELETE", "/api/krs/remove-course", json={"nim": nim, "kode_mk": "IF201"}
    )
    assert res_del.status_code == 200
    assert res_del.json()["total_sks"] == 0
    assert len(res_del.json()["details"]) == 0


def test_add_course_without_prerequisite_fails(krs_client):
    client, nim = krs_client

    # IF203 membutuhkan Kalkulus I (IF102 >= C), sedangkan nilai mahasiswa adalah D
    res = client.post("/api/krs/add-course", json={"nim": nim, "kode_mk": "IF203"})
    assert res.status_code == 400
    assert "Prasyarat tidak terpenuhi: Kalkulus I" in res.json()["detail"]


def test_add_course_schedule_conflict_fails(krs_client):
    client, nim = krs_client

    # Tambah IF201 (Rabu 08:00 - 10:30)
    res1 = client.post("/api/krs/add-course", json={"nim": nim, "kode_mk": "IF201"})
    assert res1.status_code == 201

    # Tambah IF202 (Rabu 09:30 - 11:30) -> bentrok
    res2 = client.post("/api/krs/add-course", json={"nim": nim, "kode_mk": "IF202"})
    assert res2.status_code == 400
    assert "Jadwal bentrok" in res2.json()["detail"]


def test_add_duplicate_course_fails(krs_client):
    client, nim = krs_client

    res1 = client.post("/api/krs/add-course", json={"nim": nim, "kode_mk": "IF201"})
    assert res1.status_code == 201

    res2 = client.post("/api/krs/add-course", json={"nim": nim, "kode_mk": "IF201"})
    assert res2.status_code == 400
    assert "Mata kuliah sudah ada di KRS" in res2.json()["detail"]


def test_state_machine_cannot_skip_steps(krs_client):
    client, nim = krs_client

    client.post("/api/krs/add-course", json={"nim": nim, "kode_mk": "IF201"})

    # Coba lompat DRAFT -> APPROVED langsung (harus gagal 409 Conflict)
    res_skip = client.put("/api/krs/approve", json={"nim": nim, "dosen_pa_id": 101})
    assert res_skip.status_code == 409
    assert "Transisi status tidak valid" in res_skip.json()["detail"]

    # Alur sah: DRAFT -> SUBMITTED -> REVISION -> SUBMITTED -> APPROVED
    res_sub1 = client.put("/api/krs/submit", json={"nim": nim})
    assert res_sub1.status_code == 200
    assert res_sub1.json()["status"] == "SUBMITTED"

    res_rev = client.put(
        "/api/krs/reject",
        json={"nim": nim, "dosen_pa_id": 101, "catatan_revisi": "Perbaiki pilihan MK"},
    )
    assert res_rev.status_code == 200
    assert res_rev.json()["status"] == "REVISION"

    res_sub2 = client.put("/api/krs/submit", json={"nim": nim})
    assert res_sub2.status_code == 200
    assert res_sub2.json()["status"] == "SUBMITTED"

    res_app = client.put("/api/krs/approve", json={"nim": nim, "dosen_pa_id": 101})
    assert res_app.status_code == 200
    assert res_app.json()["status"] == "APPROVED"


# =====================================================================
# 2. PROPERTY-BASED TESTING (HYPOTHESIS - 1.000 KOMBINASI RANDOM)
# =====================================================================

@settings(max_examples=1000, deadline=None)
@given(
    courses=st.lists(
        st.integers(min_value=1, max_value=4),
        min_size=1,
        max_size=15,
    )
)
def test_total_sks_never_exceeds_limit(courses: list[int]):
    """
    Property: Apapun kombinasi random mata kuliah (SKS 1-4) yang dicoba
    ditambahkan ke dalam KRS, total_sks tidak pernah melebihi 24 SKS.
    Diuji sebanyak 1.000 kombinasi acak.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SessionTest = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    db = SessionTest()
    try:
        nim = _seed_base_data(db)
        days = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu"]

        # Buat mata kuliah dengan jadwal berbeda-beda agar tidak bentrok,
        # sehingga batas 24 SKS benar-benar teruji secara murni
        for idx, sks_val in enumerate(courses):
            hari = days[idx % len(days)]
            slot = idx // len(days)
            jam_mulai = time(7 + slot * 3, 0)
            jam_selesai = time(9 + slot * 3, 0)
            db.add(
                MataKuliah(
                    kode_mk=f"MK{idx:03d}",
                    nama=f"Mata Kuliah {idx}",
                    sks=sks_val,
                    semester_paket=1,
                    is_wajib=True,
                    hari=hari,
                    jam_mulai=jam_mulai,
                    jam_selesai=jam_selesai,
                )
            )
        db.commit()

        manager = KRSManager(db)
        for idx in range(len(courses)):
            try:
                manager.add_course(nim, f"MK{idx:03d}")
            except Exception:
                # Ditolak oleh SKSValidator saat total > 24 SKS
                pass

        krs = manager.get_krs(nim)
        assert krs.total_sks <= MAX_SKS_PER_SEMESTER
        assert krs.total_sks <= 24
    finally:
        db.close()
        engine.dispose()