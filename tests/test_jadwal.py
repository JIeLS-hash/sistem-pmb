from __future__ import annotations

from datetime import time
from typing import Generator

import pytest
from fastapi.testclient import TestClient
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.database import Base, get_db
from app.main import app
from app.models.jadwal import Dosen, Kelas, Ruangan
from app.models.krs import KRSDetail
from app.models.matakuliah import MataKuliah
from app.seed_jadwal import seed_jadwal_data
from app.services.conflict_detector import detect_naive, detect_schedule_conflict

TEST_DATABASE_URL = "sqlite://"
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(autouse=True)
def db_session() -> Generator[Session, None, None]:
    Base.metadata.create_all(bind=test_engine)
    session = TestingSessionLocal()

    def override_get_db() -> Generator[Session, None, None]:
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield session
    finally:
        app.dependency_overrides.clear()
        session.close()
        Base.metadata.drop_all(bind=test_engine)


@pytest.fixture(scope="module", autouse=True)
def dispose_test_engine() -> Generator[None, None, None]:
    yield
    test_engine.dispose()


def _setup_basic_master(db: Session) -> dict[str, int | str]:
    r1 = Ruangan(kode="R101", kapasitas=40)
    r2 = Ruangan(kode="R102", kapasitas=25)
    d1 = Dosen(nidn="0499001101", nama="Dr. Andi Pratama, M.Kom.")
    d2 = Dosen(nidn="0499001102", nama="Dr. Bella Kusuma, M.T.")
    mk1 = MataKuliah(
        kode_mk="MK101",
        nama="Pemrograman Dasar",
        sks=3,
        semester_paket=1,
        is_wajib=True,
        hari="Senin",
        jam_mulai=time(8, 0),
        jam_selesai=time(10, 0),
    )
    mk2 = MataKuliah(
        kode_mk="MK102",
        nama="Basis Data Lanjut",
        sks=3,
        semester_paket=2,
        is_wajib=True,
        hari="Selasa",
        jam_mulai=time(8, 0),
        jam_selesai=time(10, 0),
    )
    db.add_all([r1, r2, d1, d2, mk1, mk2])
    db.flush()

    k1 = Kelas(kode_mk="MK101", nama="A", kuota=35, semester="2026/2027-1")
    k2 = Kelas(kode_mk="MK102", nama="A", kuota=35, semester="2026/2027-1")
    k_small = Kelas(kode_mk="MK101", nama="B", kuota=20, semester="2026/2027-1")
    db.add_all([k1, k2, k_small])
    db.commit()

    return {
        "r1": r1.kode,
        "r2": r2.kode,
        "d1": d1.id,
        "d2": d2.id,
        "k1": k1.id,
        "k2": k2.id,
        "k_small": k_small.id,
    }


def test_create_jadwal_and_adjacent_interval_no_conflict(db_session: Session) -> None:
    master = _setup_basic_master(db_session)
    client = TestClient(app)

    # Jadwal 1: Senin 08:00 - 10:00 di R101 oleh d1
    res1 = client.post(
        "/api/jadwal",
        json={
            "kelas_id": master["k1"],
            "hari": 1,
            "jam_mulai": "08:00:00",
            "jam_selesai": "10:00:00",
            "ruangan_kode": master["r1"],
            "dosen_id": master["d1"],
        },
    )
    assert res1.status_code == 201

    # Jadwal 2: Senin 10:00 - 12:00 di R101 oleh d1 (berurutan tanpa jeda -> tidak bentrok)
    res2 = client.post(
        "/api/jadwal",
        json={
            "kelas_id": master["k2"],
            "hari": 1,
            "jam_mulai": "10:00:00",
            "jam_selesai": "12:00:00",
            "ruangan_kode": master["r1"],
            "dosen_id": master["d1"],
        },
    )
    assert res2.status_code == 201


def test_create_jadwal_room_and_lecturer_conflicts_return_409(db_session: Session) -> None:
    master = _setup_basic_master(db_session)
    client = TestClient(app)

    base_res = client.post(
        "/api/jadwal",
        json={
            "kelas_id": master["k1"],
            "hari": 2,
            "jam_mulai": "08:00:00",
            "jam_selesai": "10:00:00",
            "ruangan_kode": master["r1"],
            "dosen_id": master["d1"],
        },
    )
    assert base_res.status_code == 201

    # Bentrok ruangan (ruang sama R101, dosen berbeda d2, waktu beririsan)
    room_conflict_res = client.post(
        "/api/jadwal",
        json={
            "kelas_id": master["k2"],
            "hari": 2,
            "jam_mulai": "09:00:00",
            "jam_selesai": "11:00:00",
            "ruangan_kode": master["r1"],
            "dosen_id": master["d2"],
        },
    )
    assert room_conflict_res.status_code == 409
    detail_room = room_conflict_res.json()["detail"]
    assert detail_room["conflicts"][0]["type"] == "room_conflict"

    # Bentrok dosen (ruang berbeda R102, dosen sama d1, waktu beririsan)
    lecturer_conflict_res = client.post(
        "/api/jadwal",
        json={
            "kelas_id": master["k_small"],
            "hari": 2,
            "jam_mulai": "08:30:00",
            "jam_selesai": "10:30:00",
            "ruangan_kode": master["r2"],
            "dosen_id": master["d1"],
        },
    )
    assert lecturer_conflict_res.status_code == 409
    detail_lect = lecturer_conflict_res.json()["detail"]
    assert detail_lect["conflicts"][0]["type"] == "lecturer_conflict"


def test_capacity_check_kuota_and_enrolled_students(db_session: Session) -> None:
    master = _setup_basic_master(db_session)
    client = TestClient(app)

    # 1. Kuota kelas (35) > kapasitas R102 (25) -> 409 capacity_conflict
    res_kuota = client.post(
        "/api/jadwal",
        json={
            "kelas_id": master["k1"],
            "hari": 3,
            "jam_mulai": "08:00:00",
            "jam_selesai": "10:00:00",
            "ruangan_kode": master["r2"],
            "dosen_id": master["d1"],
        },
    )
    assert res_kuota.status_code == 409
    assert res_kuota.json()["detail"]["conflicts"][0]["type"] == "capacity_conflict"

    # 2. Kuota kelas kecil (20) <= kapasitas R102 (25), tapi 28 mahasiswa enrolled -> 409
    db_session.execute(text("PRAGMA foreign_keys = OFF"))
    for idx in range(28):
        db_session.add(
            KRSDetail(
                krs_id=idx + 1,
                kode_mk="MK101",
                kelas_id=int(master["k_small"]),
            )
        )
    db_session.commit()

    res_enrolled = client.post(
        "/api/jadwal",
        json={
            "kelas_id": master["k_small"],
            "hari": 3,
            "jam_mulai": "10:00:00",
            "jam_selesai": "12:00:00",
            "ruangan_kode": master["r2"],
            "dosen_id": master["d2"],
        },
    )
    assert res_enrolled.status_code == 409
    conflict_info = res_enrolled.json()["detail"]["conflicts"][0]
    assert conflict_info["type"] == "capacity_conflict"
    assert conflict_info["mahasiswa_enrolled"] == 28


def test_update_delete_not_found_and_validation_errors(db_session: Session) -> None:
    master = _setup_basic_master(db_session)
    client = TestClient(app)

    # 422 jika jam_mulai >= jam_selesai
    bad_time = client.post(
        "/api/jadwal",
        json={
            "kelas_id": master["k1"],
            "hari": 4,
            "jam_mulai": "11:00:00",
            "jam_selesai": "09:00:00",
            "ruangan_kode": master["r1"],
            "dosen_id": master["d1"],
        },
    )
    assert bad_time.status_code == 422

    # 404 jika ruangan tidak terdaftar
    not_found_ruang = client.post(
        "/api/jadwal",
        json={
            "kelas_id": master["k1"],
            "hari": 4,
            "jam_mulai": "08:00:00",
            "jam_selesai": "10:00:00",
            "ruangan_kode": "Z999",
            "dosen_id": master["d1"],
        },
    )
    assert not_found_ruang.status_code == 404

    # Create -> Update -> Delete -> Get 404
    created = client.post(
        "/api/jadwal",
        json={
            "kelas_id": master["k1"],
            "hari": 4,
            "jam_mulai": "08:00:00",
            "jam_selesai": "10:00:00",
            "ruangan_kode": master["r1"],
            "dosen_id": master["d1"],
        },
    )
    assert created.status_code == 201
    jadwal_id = created.json()["id"]

    updated = client.put(
        f"/api/jadwal/{jadwal_id}",
        json={"hari": 5, "jam_mulai": "13:00:00", "jam_selesai": "15:00:00"},
    )
    assert updated.status_code == 200
    assert updated.json()["hari"] == 5

    deleted = client.delete(f"/api/jadwal/{jadwal_id}")
    assert deleted.status_code == 204

    after_delete = client.get(f"/api/jadwal/{jadwal_id}")
    assert after_delete.status_code == 404


def test_seed_jadwal_and_conflicts_endpoint(db_session: Session) -> None:
    summary = seed_jadwal_data(db_session)
    assert summary["ruangan"] >= 10
    assert summary["dosen"] >= 15
    assert summary["jadwal"] >= 40

    client = TestClient(app)
    res = client.get("/api/jadwal/conflicts")
    assert res.status_code == 200
    body = res.json()
    assert body["total_schedules"] == 42
    assert body["total_conflicts"] == 4


# --- Property-Based Tests & Differential Test (Hypothesis) ---

@st.composite
def schedule_list_strategy(draw: st.DrawFn) -> list[dict[str, object]]:
    size = draw(st.integers(min_value=0, max_value=20))
    items: list[dict[str, object]] = []
    for idx in range(size):
        hari = draw(st.integers(min_value=1, max_value=6))
        start_hour = draw(st.integers(min_value=7, max_value=17))
        duration = draw(st.integers(min_value=1, max_value=3))
        ruangan = draw(st.sampled_from(["A101", "A102", "B101", "LAB1"]))
        dosen = draw(st.sampled_from([1, 2, 3, 4, 5]))
        items.append(
            {
                "id": idx + 1,
                "kelas_id": (idx % 5) + 1,
                "hari": hari,
                "jam_mulai": time(start_hour, 0),
                "jam_selesai": time(start_hour + duration, 0),
                "ruangan_kode": ruangan,
                "dosen_id": dosen,
            }
        )
    return items


@settings(max_examples=150, suppress_health_check=[HealthCheck.too_slow])
@given(schedules=schedule_list_strategy())
def test_property_differential_sweep_matches_naive(
    schedules: list[dict[str, object]],
) -> None:
    """Differential Test: hasil sweep-line harus 100% identik dengan naive O(N^2)."""
    assert detect_schedule_conflict(schedules) == detect_naive(schedules)


@settings(max_examples=150, suppress_health_check=[HealthCheck.too_slow])
@given(
    hari=st.integers(min_value=1, max_value=6),
    start_a=st.integers(min_value=7, max_value=12),
    dur_a=st.integers(min_value=1, max_value=3),
    gap=st.integers(min_value=0, max_value=3),
    dur_b=st.integers(min_value=1, max_value=3),
)
def test_property_non_overlapping_intervals_never_conflict(
    hari: int, start_a: int, dur_a: int, gap: int, dur_b: int
) -> None:
    """Property 1: interval berurutan atau berjeda (end_a <= start_b) tidak pernah bentrok."""
    end_a = start_a + dur_a
    start_b = end_a + gap
    end_b = start_b + dur_b

    schedules = [
        {
            "id": 1,
            "kelas_id": 1,
            "hari": hari,
            "jam_mulai": time(start_a, 0),
            "jam_selesai": time(end_a, 0),
            "ruangan_kode": "A101",
            "dosen_id": 1,
        },
        {
            "id": 2,
            "kelas_id": 2,
            "hari": hari,
            "jam_mulai": time(start_b, 0),
            "jam_selesai": time(end_b, 0),
            "ruangan_kode": "A101",
            "dosen_id": 1,
        },
    ]
    assert detect_schedule_conflict(schedules) == []


@settings(max_examples=150, suppress_health_check=[HealthCheck.too_slow])
@given(schedules=schedule_list_strategy())
def test_property_order_invariance(schedules: list[dict[str, object]]) -> None:
    """Property 2: membalik urutan daftar jadwal tidak mengubah hasil deteksi bentrok."""
    forward = detect_schedule_conflict(schedules)
    reversed_res = detect_schedule_conflict(list(reversed(schedules)))
    assert forward == reversed_res