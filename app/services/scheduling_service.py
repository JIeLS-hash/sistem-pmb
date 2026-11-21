from __future__ import annotations

from datetime import time
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.jadwal import Dosen, Jadwal, Kelas, Ruangan
from app.models.krs import KRSDetail
from app.schemas.jadwal import JadwalCreate, JadwalUpdate
from app.services.conflict_detector import (
    _normalize,
    _pair_conflicts,
    detect_schedule_conflict,
)
from app.services.krs_invalidator import KRSInvalidator
from app.services.observer import EventType, ScheduleEvent
from app.services.outbox_dispatcher import OutboxDispatcher


class SchedulingNotFoundError(Exception):
    """Dilempar saat entitas jadwal, kelas, ruangan, atau dosen tidak ditemukan (404)."""


class SchedulingValidationError(Exception):
    """Dilempar saat aturan input waktu/hari tidak valid (422)."""


class SchedulingConflictError(Exception):
    """Dilempar saat terjadi bentrok ruangan, dosen, atau kapasitas ruangan (409)."""

    def __init__(self, message: str, conflicts: list[dict[str, Any]]) -> None:
        super().__init__(message)
        self.message = message
        self.conflicts = conflicts

    def to_detail(self) -> dict[str, Any]:
        return {
            "message": self.message,
            "conflicts": self.conflicts,
        }


class SchedulingService:
    """Layanan CRUD jadwal kuliah dengan capacity check, row locking, Outbox, dan invalidasi KRS."""

    @staticmethod
    def _snapshot_jadwal(jadwal: Jadwal) -> dict[str, Any]:
        return {
            "id": jadwal.id,
            "kelas_id": jadwal.kelas_id,
            "hari": jadwal.hari,
            "jam_mulai": jadwal.jam_mulai.strftime("%H:%M:%S"),
            "jam_selesai": jadwal.jam_selesai.strftime("%H:%M:%S"),
            "ruangan_kode": jadwal.ruangan_kode,
            "dosen_id": jadwal.dosen_id,
        }

    @staticmethod
    def _validate_time_and_day(hari: int, jam_mulai: time, jam_selesai: time) -> None:
        if not (1 <= hari <= 6):
            raise SchedulingValidationError("hari harus bernilai antara 1 (Senin) sampai 6 (Sabtu)")
        if jam_mulai >= jam_selesai:
            raise SchedulingValidationError("jam_mulai harus lebih awal dari jam_selesai")

    @staticmethod
    def _lock_and_fetch_master(
        db: Session,
        kelas_id: int,
        ruangan_kode: str,
        dosen_id: int,
    ) -> tuple[Kelas, Ruangan, Dosen]:
        kelas = db.scalar(
            select(Kelas).where(Kelas.id == kelas_id).with_for_update()
        )
        if kelas is None:
            raise SchedulingNotFoundError(f"Kelas dengan id={kelas_id} tidak ditemukan")

        ruangan = db.scalar(
            select(Ruangan).where(Ruangan.kode == ruangan_kode).with_for_update()
        )
        if ruangan is None:
            raise SchedulingNotFoundError(f"Ruangan '{ruangan_kode}' tidak ditemukan")

        dosen = db.scalar(
            select(Dosen).where(Dosen.id == dosen_id).with_for_update()
        )
        if dosen is None:
            raise SchedulingNotFoundError(f"Dosen dengan id={dosen_id} tidak ditemukan")

        return kelas, ruangan, dosen

    @staticmethod
    def _check_capacity(db: Session, kelas: Kelas, ruangan: Ruangan) -> None:
        enrolled_count = (
            db.scalar(
                select(func.count(KRSDetail.id)).where(KRSDetail.kelas_id == kelas.id)
            )
            or 0
        )
        required_seats = max(kelas.kuota, enrolled_count)
        if required_seats > ruangan.kapasitas:
            raise SchedulingConflictError(
                message=(
                    f"Kapasitas ruangan {ruangan.kode} ({ruangan.kapasitas}) tidak mencukupi "
                    f"untuk kelas {kelas.kode_mk}-{kelas.nama} "
                    f"(kuota={kelas.kuota}, enrolled={enrolled_count})"
                ),
                conflicts=[
                    {
                        "type": "capacity_conflict",
                        "kelas_id": kelas.id,
                        "ruangan": ruangan.kode,
                        "kapasitas_ruangan": ruangan.kapasitas,
                        "kuota_kelas": kelas.kuota,
                        "mahasiswa_enrolled": enrolled_count,
                    }
                ],
            )

    @staticmethod
    def _check_3d_conflicts(
        db: Session,
        candidate_data: dict[str, Any],
        exclude_jadwal_id: int | None = None,
    ) -> None:
        stmt = (
            select(Jadwal)
            .where(Jadwal.hari == candidate_data["hari"])
            .with_for_update()
        )
        if exclude_jadwal_id is not None:
            stmt = stmt.where(Jadwal.id != exclude_jadwal_id)

        same_day_schedules = db.scalars(stmt).all()
        candidate_norm = _normalize(candidate_data, idx=len(same_day_schedules))

        detected: list[dict[str, Any]] = []
        for idx, existing in enumerate(same_day_schedules):
            existing_norm = _normalize(existing, idx=idx)
            detected.extend(_pair_conflicts(existing_norm, candidate_norm))

        if detected:
            raise SchedulingConflictError(
                message="Jadwal bentrok dengan jadwal lain yang sudah terdaftar",
                conflicts=detected,
            )

    @classmethod
    def list_jadwal(
        cls,
        db: Session,
        hari: int | None = None,
        ruangan_kode: str | None = None,
        dosen_id: int | None = None,
        kelas_id: int | None = None,
    ) -> list[Jadwal]:
        stmt = select(Jadwal).order_by(Jadwal.hari, Jadwal.jam_mulai, Jadwal.id)
        if hari is not None:
            stmt = stmt.where(Jadwal.hari == hari)
        if ruangan_kode is not None:
            stmt = stmt.where(Jadwal.ruangan_kode == ruangan_kode)
        if dosen_id is not None:
            stmt = stmt.where(Jadwal.dosen_id == dosen_id)
        if kelas_id is not None:
            stmt = stmt.where(Jadwal.kelas_id == kelas_id)
        return list(db.scalars(stmt).all())

    @classmethod
    def get_jadwal(cls, db: Session, jadwal_id: int) -> Jadwal:
        jadwal = db.get(Jadwal, jadwal_id)
        if jadwal is None:
            raise SchedulingNotFoundError(f"Jadwal dengan id={jadwal_id} tidak ditemukan")
        return jadwal

    @classmethod
    def get_all_conflicts(cls, db: Session) -> dict[str, Any]:
        schedules = list(
            db.scalars(select(Jadwal).order_by(Jadwal.hari, Jadwal.jam_mulai, Jadwal.id)).all()
        )
        conflicts = detect_schedule_conflict(schedules)
        return {
            "total_schedules": len(schedules),
            "total_conflicts": len(conflicts),
            "conflicts": conflicts,
        }

    @classmethod
    def create_jadwal(cls, db: Session, payload: JadwalCreate) -> Jadwal:
        cls._validate_time_and_day(payload.hari, payload.jam_mulai, payload.jam_selesai)
        kelas, ruangan, dosen = cls._lock_and_fetch_master(
            db, payload.kelas_id, payload.ruangan_kode, payload.dosen_id
        )
        cls._check_capacity(db, kelas, ruangan)
        cls._check_3d_conflicts(
            db,
            {
                "id": None,
                "kelas_id": kelas.id,
                "hari": payload.hari,
                "jam_mulai": payload.jam_mulai,
                "jam_selesai": payload.jam_selesai,
                "ruangan_kode": ruangan.kode,
                "dosen_id": dosen.id,
            },
        )

        jadwal = Jadwal(
            kelas_id=kelas.id,
            hari=payload.hari,
            jam_mulai=payload.jam_mulai,
            jam_selesai=payload.jam_selesai,
            ruangan_kode=ruangan.kode,
            dosen_id=dosen.id,
        )
        db.add(jadwal)
        db.flush()

        event = ScheduleEvent(
            event_type=EventType.SCHEDULE_CREATED,
            jadwal_id=jadwal.id,
            before=None,
            after=cls._snapshot_jadwal(jadwal),
        )
        OutboxDispatcher.enqueue_event(db, event)

        db.commit()
        db.refresh(jadwal)

        # Kirim notifikasi hanya setelah transaksi utama berhasil di-commit
        OutboxDispatcher.dispatch_pending(db)
        return jadwal

    @classmethod
    def update_jadwal(
        cls, db: Session, jadwal_id: int, payload: JadwalUpdate
    ) -> Jadwal:
        jadwal = db.scalar(
            select(Jadwal).where(Jadwal.id == jadwal_id).with_for_update()
        )
        if jadwal is None:
            raise SchedulingNotFoundError(f"Jadwal dengan id={jadwal_id} tidak ditemukan")

        before_snapshot = cls._snapshot_jadwal(jadwal)

        new_kelas_id = payload.kelas_id if payload.kelas_id is not None else jadwal.kelas_id
        new_hari = payload.hari if payload.hari is not None else jadwal.hari
        new_jam_mulai = payload.jam_mulai if payload.jam_mulai is not None else jadwal.jam_mulai
        new_jam_selesai = (
            payload.jam_selesai if payload.jam_selesai is not None else jadwal.jam_selesai
        )
        new_ruangan_kode = (
            payload.ruangan_kode if payload.ruangan_kode is not None else jadwal.ruangan_kode
        )
        new_dosen_id = payload.dosen_id if payload.dosen_id is not None else jadwal.dosen_id

        cls._validate_time_and_day(new_hari, new_jam_mulai, new_jam_selesai)
        kelas, ruangan, dosen = cls._lock_and_fetch_master(
            db, new_kelas_id, new_ruangan_kode, new_dosen_id
        )
        cls._check_capacity(db, kelas, ruangan)
        cls._check_3d_conflicts(
            db,
            {
                "id": jadwal.id,
                "kelas_id": kelas.id,
                "hari": new_hari,
                "jam_mulai": new_jam_mulai,
                "jam_selesai": new_jam_selesai,
                "ruangan_kode": ruangan.kode,
                "dosen_id": dosen.id,
            },
            exclude_jadwal_id=jadwal.id,
        )

        jadwal.kelas_id = kelas.id
        jadwal.hari = new_hari
        jadwal.jam_mulai = new_jam_mulai
        jadwal.jam_selesai = new_jam_selesai
        jadwal.ruangan_kode = ruangan.kode
        jadwal.dosen_id = dosen.id

        invalidated_krs_ids = KRSInvalidator.invalidate_affected_krs(
            db,
            kelas_id=kelas.id,
            reason=f"Jadwal #{jadwal.id} mengalami perubahan waktu/ruangan/dosen.",
        )

        after_snapshot = cls._snapshot_jadwal(jadwal)
        event = ScheduleEvent(
            event_type=EventType.SCHEDULE_CHANGED,
            jadwal_id=jadwal.id,
            before=before_snapshot,
            after=after_snapshot,
        )
        OutboxDispatcher.enqueue_event(
            db, event, invalidated_krs_ids=invalidated_krs_ids
        )

        db.commit()
        db.refresh(jadwal)

        # Kirim notifikasi setelah commit
        OutboxDispatcher.dispatch_pending(db)
        return jadwal

    @classmethod
    def delete_jadwal(cls, db: Session, jadwal_id: int) -> None:
        jadwal = db.scalar(
            select(Jadwal).where(Jadwal.id == jadwal_id).with_for_update()
        )
        if jadwal is None:
            raise SchedulingNotFoundError(f"Jadwal dengan id={jadwal_id} tidak ditemukan")

        before_snapshot = cls._snapshot_jadwal(jadwal)
        deleted_id = jadwal.id
        kelas_id = jadwal.kelas_id

        db.delete(jadwal)

        invalidated_krs_ids = KRSInvalidator.invalidate_affected_krs(
            db,
            kelas_id=kelas_id,
            reason=f"Jadwal #{deleted_id} telah dihapus dari jadwal kuliah.",
        )

        event = ScheduleEvent(
            event_type=EventType.SCHEDULE_DELETED,
            jadwal_id=deleted_id,
            before=before_snapshot,
            after=None,
        )
        OutboxDispatcher.enqueue_event(
            db, event, invalidated_krs_ids=invalidated_krs_ids
        )

        db.commit()

        # Kirim notifikasi setelah commit
        OutboxDispatcher.dispatch_pending(db)