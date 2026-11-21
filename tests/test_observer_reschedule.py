from __future__ import annotations

from datetime import time
from typing import Any, Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.database import Base, get_db
from app.main import app
from app.models.jadwal import Dosen, Jadwal, Kelas, Ruangan
from app.models.krs import KRS, KRSDetail
from app.models.matakuliah import MataKuliah
from app.models.outbox import OutboxEvent
from app.services.krs_invalidator import (
    ALLOWED_TRANSITIONS,
    Actor,
    IllegalStateTransitionError,
    KRSStatus,
    validate_transition,
)
from app.services.observer import (
    EventType,
    NotificationManager,
    ScheduleEvent,
    notification_manager,
)
from app.services.outbox_dispatcher import OutboxDispatcher

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
    notification_manager.clear_logs()
    OutboxDispatcher.reset_idempotency_cache()
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
        notification_manager.clear_logs()
        OutboxDispatcher.reset_idempotency_cache()
        session.close()
        Base.metadata.drop_all(bind=test_engine)


@pytest.fixture(scope="module", autouse=True)
def dispose_test_engine() -> Generator[None, None, None]:
    yield
    test_engine.dispose()


def _create_krs_row(db: Session, nim: str, semester: str, status: str) -> KRS:
    kwargs: dict[str, Any] = {}
    for col in KRS.__table__.columns:
        if col.primary_key:
            continue
        if col.name == "nim":
            kwargs[col.name] = nim
        elif col.name == "semester":
            kwargs[col.name] = semester
        elif col.name == "status":
            kwargs[col.name] = status
        elif not col.nullable and col.default is None and col.server_default is None:
            py_type = col.type.python_type
            if py_type is str:
                kwargs[col.name] = nim
            elif py_type is int:
                kwargs[col.name] = 0
            elif py_type is bool:
                kwargs[col.name] = False
    krs = KRS(**kwargs)
    db.add(krs)
    db.flush()
    return krs


def _seed_jadwal_fixture(db: Session) -> dict[str, Any]:
    r1 = Ruangan(kode="R201", kapasitas=40)
    r2 = Ruangan(kode="R202", kapasitas=20)
    d1 = Dosen(nidn="0488001101", nama="Dr. Citra Lestari, M.Kom.")
    d2 = Dosen(nidn="0488001102", nama="Dr. Dimas Saputra, M.T.")
    mk = MataKuliah(
        kode_mk="IF501",
        nama="Arsitektur Perangkat Lunak",
        sks=3,
        semester_paket=5,
        is_wajib=True,
        hari="Senin",
        jam_mulai=time(8, 0),
        jam_selesai=time(10, 0),
    )
    db.add_all([r1, r2, d1, d2, mk])
    db.flush()

    kelas = Kelas(kode_mk="IF501", nama="A", kuota=30, semester="2026/2027-1")
    db.add(kelas)
    db.flush()

    jadwal = Jadwal(
        kelas_id=kelas.id,
        hari=1,
        jam_mulai=time(8, 0),
        jam_selesai=time(10, 0),
        ruangan_kode="R201",
        dosen_id=d1.id,
    )
    db.add(jadwal)
    db.commit()

    return {
        "r1": r1,
        "r2": r2,
        "d1": d1,
        "d2": d2,
        "kelas": kelas,
        "jadwal": jadwal,
    }


def test_observer_three_channels_and_fault_isolation() -> None:
    """Test 1: Observer mengirim ke Email/SMS/Push dan tetap lanjut jika satu observer gagal."""

    class BrokenObserver:
        def update(self, event: ScheduleEvent) -> None:
            raise RuntimeError("Simulasi gangguan observer")

    nm = NotificationManager()
    nm.subject.attach(BrokenObserver())

    event = ScheduleEvent(
        event_type=EventType.SCHEDULE_CHANGED,
        jadwal_id=10,
        before={"hari": 1, "dosen_id": 1, "kelas_id": 3},
        after={"hari": 2, "dosen_id": 2, "kelas_id": 3},
    )
    nm.dispatch(event)

    channels = {entry["channel"] for entry in nm.logs}
    assert channels == {"EMAIL", "SMS", "PUSH"}
    assert len(nm.subject.errors) == 1
    assert nm.subject.errors[0]["observer"] == "BrokenObserver"


def test_outbox_post_commit_dispatch_and_idempotency(db_session: Session) -> None:
    """Test 2: Outbox dikirim setelah commit, tahan rollback, dan idempoten terhadap duplikasi."""
    fx = _seed_jadwal_fixture(db_session)
    client = TestClient(app)

    # Buat jadwal kedua untuk memicu bentrok saat update gagal
    j2 = Jadwal(
        kelas_id=fx["kelas"].id,
        hari=3,
        jam_mulai=time(10, 0),
        jam_selesai=time(12, 0),
        ruangan_kode="R201",
        dosen_id=fx["d2"].id,
    )
    db_session.add(j2)
    db_session.commit()

    # 1. Update gagal (409 bentrok) -> transaksi rollback, outbox kosong & notifikasi = 0
    fail_res = client.put(
        f"/api/jadwal/{fx['jadwal'].id}",
        json={"hari": 3, "jam_mulai": "10:30:00", "jam_selesai": "11:30:00"},
    )
    assert fail_res.status_code == 409
    assert db_session.scalars(select(OutboxEvent)).all() == []
    assert len(notification_manager.logs) == 0

    # 2. Update sukses -> Outbox tersimpan & terkirim setelah commit
    ok_res = client.put(
        f"/api/jadwal/{fx['jadwal'].id}",
        json={"hari": 2, "jam_mulai": "13:00:00", "jam_selesai": "15:00:00"},
    )
    assert ok_res.status_code == 200

    outbox_rows = db_session.scalars(select(OutboxEvent)).all()
    assert len(outbox_rows) == 1
    assert outbox_rows[0].status == "SENT"
    initial_log_count = len(notification_manager.logs)
    assert initial_log_count > 0

    # 3. Pengiriman ulang event yang sama diabaikan (idempotency key)
    assert OutboxDispatcher.dispatch_event_record(db_session, outbox_rows[0]) is False
    assert len(notification_manager.logs) == initial_log_count


def test_krs_invalidation_and_42_illegal_state_transitions(db_session: Session) -> None:
    """Test 3: Verifikasi tepat 42 transisi status KRS ilegal dan invalidasi otomatis ke REVISION."""
    # Uji matriks penuh: 3 aktor x 4 status asal x 4 status tujuan = 48 kombinasi
    # 6 kombinasi valid (2 per aktor) dan 42 kombinasi wajib ditolak (IllegalStateTransitionError)
    allowed_count = 0
    illegal_count = 0

    for actor in Actor:
        for src in KRSStatus:
            for dst in KRSStatus:
                if (src, dst) in ALLOWED_TRANSITIONS[actor]:
                    assert validate_transition(actor, src, dst) == dst
                    allowed_count += 1
                else:
                    with pytest.raises(IllegalStateTransitionError):
                        validate_transition(actor, src, dst)
                    illegal_count += 1

    assert allowed_count == 6
    assert illegal_count == 42

    # Uji integrasi: jadwal berubah -> KRS SUBMITTED & APPROVED terdampak kembali ke REVISION
    fx = _seed_jadwal_fixture(db_session)
    db_session.execute(text("PRAGMA foreign_keys = OFF"))

    krs_approved = _create_krs_row(
        db_session, nim="2026010001", semester="2026/2027-1", status="APPROVED"
    )
    krs_submitted = _create_krs_row(
        db_session, nim="2026010002", semester="2026/2027-1", status="SUBMITTED"
    )
    krs_draft = _create_krs_row(
        db_session, nim="2026010003", semester="2026/2027-1", status="DRAFT"
    )

    db_session.add_all(
        [
            KRSDetail(krs_id=krs_approved.id, kode_mk="IF501", kelas_id=fx["kelas"].id),
            KRSDetail(krs_id=krs_submitted.id, kode_mk="IF501", kelas_id=fx["kelas"].id),
            KRSDetail(krs_id=krs_draft.id, kode_mk="IF501", kelas_id=fx["kelas"].id),
        ]
    )
    db_session.commit()

    client = TestClient(app)
    res = client.put(
        f"/api/jadwal/{fx['jadwal'].id}",
        json={"hari": 4, "jam_mulai": "08:00:00", "jam_selesai": "10:00:00"},
    )
    assert res.status_code == 200

    db_session.refresh(krs_approved)
    db_session.refresh(krs_submitted)
    db_session.refresh(krs_draft)

    assert krs_approved.status == "REVISION"
    assert krs_submitted.status == "REVISION"
    assert krs_draft.status == "DRAFT"


def test_ai_reschedule_filter_ics_export_and_dashboard_ui(db_session: Session) -> None:
    """Test 4: Saringan validator saran AI, ekspor kalender .ics, dan Conflict Resolver UI."""
    fx = _seed_jadwal_fixture(db_session)
    # Tambahkan jadwal pemblokir di Hari 2 jam 08:00-10:00 pada R201
    blocker = Jadwal(
        kelas_id=fx["kelas"].id,
        hari=2,
        jam_mulai=time(8, 0),
        jam_selesai=time(10, 0),
        ruangan_kode="R201",
        dosen_id=fx["d2"].id,
    )
    db_session.add(blocker)
    db_session.commit()

    client = TestClient(app)
    raw_candidates = [
        # Ditolak: jam_mulai >= jam_selesai
        {"hari": 2, "jam_mulai": "12:00", "jam_selesai": "10:00", "ruangan_kode": "R201"},
        # Ditolak: ruangan tidak terdaftar
        {"hari": 2, "jam_mulai": "13:00", "jam_selesai": "15:00", "ruangan_kode": "Z999"},
        # Ditolak: kapasitas R202 (20) < kuota kelas (30)
        {"hari": 2, "jam_mulai": "13:00", "jam_selesai": "15:00", "ruangan_kode": "R202"},
        # Ditolak: bentrok ruangan dengan blocker di Hari 2 08:00-10:00 R201
        {"hari": 2, "jam_mulai": "08:30", "jam_selesai": "10:30", "ruangan_kode": "R201"},
        # Diterima: Hari 5 jam 08:00-10:00 di R201 (kapasitas 40, bebas bentrok)
        {
            "hari": 5,
            "jam_mulai": "08:00",
            "jam_selesai": "10:00",
            "ruangan_kode": "R201",
            "alasan": "Slot Jumat pagi tersedia",
        },
    ]

    suggest_res = client.post(
        f"/api/jadwal/{fx['jadwal'].id}/suggest-reschedule",
        json={"raw_candidates": raw_candidates, "limit": 5},
    )
    assert suggest_res.status_code == 200
    body = suggest_res.json()
    assert body["valid_count"] == 1
    assert body["rejected_count"] == 4
    assert body["suggestions"][0]["hari"] == 5

    # Uji ekspor .ics
    ics_res = client.get("/api/jadwal/export/ics")
    assert ics_res.status_code == 200
    assert "BEGIN:VCALENDAR" in ics_res.text
    assert "BEGIN:VEVENT" in ics_res.text

    # Uji halaman dashboard Conflict Resolver UI
    dash_res = client.get("/api/jadwal/dashboard")
    assert dash_res.status_code == 200
    assert "Conflict Resolver UI" in dash_res.text