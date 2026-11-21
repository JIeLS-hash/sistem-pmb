from __future__ import annotations

from enum import StrEnum

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.jadwal import Kelas
from app.models.krs import KRS, KRSDetail


class Actor(StrEnum):
    MAHASISWA = "MAHASISWA"
    DOSEN_PA = "DOSEN_PA"
    SISTEM = "SISTEM"


class KRSStatus(StrEnum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"
    REVISION = "REVISION"


class IllegalStateTransitionError(Exception):
    """Dilempar saat aktor mencoba melakukan transisi status KRS yang tidak diizinkan."""


ALLOWED_TRANSITIONS: dict[Actor, set[tuple[KRSStatus, KRSStatus]]] = {
    Actor.MAHASISWA: {
        (KRSStatus.DRAFT, KRSStatus.SUBMITTED),
        (KRSStatus.REVISION, KRSStatus.SUBMITTED),
    },
    Actor.DOSEN_PA: {
        (KRSStatus.SUBMITTED, KRSStatus.APPROVED),
        (KRSStatus.SUBMITTED, KRSStatus.REVISION),
    },
    Actor.SISTEM: {
        (KRSStatus.SUBMITTED, KRSStatus.REVISION),
        (KRSStatus.APPROVED, KRSStatus.REVISION),
    },
}


def validate_transition(
    actor: Actor, current_status: str | KRSStatus, target_status: str | KRSStatus
) -> KRSStatus:
    """Memvalidasi apakah aktor berhak mengubah status KRS dari current_status ke target_status."""
    curr = KRSStatus(current_status)
    target = KRSStatus(target_status)

    if (curr, target) not in ALLOWED_TRANSITIONS.get(actor, set()):
        raise IllegalStateTransitionError(
            f"Transisi ilegal oleh {actor.value}: {curr.value} -> {target.value}"
        )
    return target


class KRSInvalidator:
    """Mengelola transisi status KRS dan invalidasi otomatis saat jadwal berubah/dihapus."""

    @staticmethod
    def transition_krs(
        krs: KRS,
        target_status: KRSStatus,
        actor: Actor,
        reason: str | None = None,
    ) -> KRS:
        validated = validate_transition(actor, krs.status, target_status)
        krs.status = validated.value

        if reason:
            for note_field in ("catatan", "catatan_pa", "alasan_revisi", "keterangan"):
                if hasattr(krs, note_field):
                    setattr(krs, note_field, reason)
                    break

        return krs

    @classmethod
    def invalidate_affected_krs(
        cls, db: Session, kelas_id: int, reason: str
    ) -> list[int]:
        """Mengembalikan seluruh KRS aktif (SUBMITTED/APPROVED) yang terdampak perubahan kelas ke REVISION."""
        kelas = db.get(Kelas, kelas_id)
        if kelas is None:
            return []

        stmt = (
            select(KRS)
            .join(KRSDetail, KRSDetail.krs_id == KRS.id)
            .where(
                KRS.semester == kelas.semester,
                KRS.status.in_([KRSStatus.SUBMITTED.value, KRSStatus.APPROVED.value]),
                or_(
                    KRSDetail.kelas_id == kelas.id,
                    (KRSDetail.kelas_id.is_(None)) & (KRSDetail.kode_mk == kelas.kode_mk),
                ),
            )
            .distinct()
        )
        affected_krs_list = list(db.scalars(stmt).all())

        invalidated_ids: list[int] = []
        for krs in affected_krs_list:
            cls.transition_krs(
                krs,
                target_status=KRSStatus.REVISION,
                actor=Actor.SISTEM,
                reason=reason,
            )
            invalidated_ids.append(krs.id)

        return invalidated_ids