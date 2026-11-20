from __future__ import annotations

from enum import Enum
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.calon_mahasiswa import CalonMahasiswa
from app.models.matakuliah import MataKuliah
from app.models.krs import KRS, KRSDetail
from app.services.krs_validator import (
    ValidationContext,
    ValidationResult,
    build_chain,
)

DEFAULT_SEMESTER = "2026/2027-1"


class KRSStatus(str, Enum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"
    REVISION = "REVISION"


VALID_STATE_TRANSITIONS: dict[KRSStatus, set[KRSStatus]] = {
    KRSStatus.DRAFT: {KRSStatus.SUBMITTED},
    KRSStatus.SUBMITTED: {KRSStatus.APPROVED, KRSStatus.REVISION},
    KRSStatus.REVISION: {KRSStatus.SUBMITTED},
    KRSStatus.APPROVED: set(),
}


class KRSBusinessError(Exception):
    """Error pelanggaran aturan bisnis KRS."""


class KRSNotFoundError(KRSBusinessError):
    """Error ketika mahasiswa, mata kuliah, atau KRS tidak ditemukan."""


class InvalidStateTransitionError(KRSBusinessError):
    """Error ketika transisi status KRS melanggar aturan state machine."""


class KRSManager:
    def __init__(self, db: Session, semester: str = DEFAULT_SEMESTER) -> None:
        self.db = db
        self.semester = semester
        self.validator_chain = build_chain()

    def transition(self, krs: KRS, target_status: KRSStatus) -> KRS:
        """Menegakkan aturan transisi state machine KRS secara ketat."""
        current_status = KRSStatus(krs.status)
        allowed_targets = VALID_STATE_TRANSITIONS.get(current_status, set())

        if target_status not in allowed_targets:
            raise InvalidStateTransitionError(
                f"Transisi status tidak valid: {current_status.value} -> {target_status.value}"
            )

        krs.status = target_status.value
        return krs

    def _get_approved_student(self, nim: str) -> CalonMahasiswa:
        mahasiswa = self.db.scalar(
            select(CalonMahasiswa).where(CalonMahasiswa.nim == nim)
        )
        if not mahasiswa:
            raise KRSNotFoundError(f"Mahasiswa dengan NIM '{nim}' tidak ditemukan")
        if mahasiswa.status != "approved":
            raise KRSBusinessError(
                f"Mahasiswa dengan NIM '{nim}' belum berstatus approved"
            )
        return mahasiswa

    def _get_or_create_locked_krs(self, nim: str) -> KRS:
        """Mengambil header KRS dengan row lock (FOR UPDATE), atau membuatnya jika belum ada."""
        krs = self.db.scalar(
            select(KRS)
            .where(KRS.nim == nim, KRS.semester == self.semester)
            .with_for_update()
        )
        if krs is None:
            krs = KRS(
                nim=nim,
                semester=self.semester,
                status=KRSStatus.DRAFT.value,
                total_sks=0,
            )
            self.db.add(krs)
            self.db.flush()
            krs = self.db.scalar(
                select(KRS)
                .options(joinedload(KRS.details).joinedload(KRSDetail.matakuliah))
                .where(KRS.id == krs.id)
                .with_for_update()
            )
        return krs

    def get_krs(self, nim: str) -> KRS:
        krs = self.db.scalar(
            select(KRS)
            .options(joinedload(KRS.details).joinedload(KRSDetail.matakuliah))
            .where(KRS.nim == nim, KRS.semester == self.semester)
        )
        if not krs:
            raise KRSNotFoundError(
                f"KRS untuk NIM '{nim}' pada semester {self.semester} belum ditemukan"
            )
        return krs

    def add_course(self, nim: str, kode_mk: str) -> KRS:
        """Menambahkan mata kuliah ke KRS dengan transaksi atomik, row lock, dan rantai validasi."""
        try:
            self._get_approved_student(nim)

            target_mk = self.db.scalar(
                select(MataKuliah).where(MataKuliah.kode_mk == kode_mk)
            )
            if not target_mk:
                raise KRSNotFoundError(f"Mata kuliah '{kode_mk}' tidak ditemukan")

            krs = self._get_or_create_locked_krs(nim)

            if krs.status not in (KRSStatus.DRAFT.value, KRSStatus.REVISION.value):
                raise InvalidStateTransitionError(
                    f"Tidak dapat menambah mata kuliah saat KRS berstatus {krs.status}"
                )

            current_courses = [detail.matakuliah for detail in krs.details]

            # Jalankan Chain of Responsibility (Duplicate -> Prerequisite -> Conflict -> SKS)
            context = ValidationContext(
                db=self.db,
                nim=nim,
                target_mk=target_mk,
                current_courses=current_courses,
            )
            validation = self.validator_chain.validate(context)
            if not validation.is_valid:
                raise KRSBusinessError(validation.message)

            new_detail = KRSDetail(krs_id=krs.id, kode_mk=target_mk.kode_mk)
            self.db.add(new_detail)
            krs.total_sks = sum(mk.sks for mk in current_courses) + target_mk.sks

            self.db.commit()
            return self.get_krs(nim)
        except Exception:
            self.db.rollback()
            raise

    def remove_course(self, nim: str, kode_mk: str) -> KRS:
        """Menghapus mata kuliah dari KRS dan memperbarui total SKS secara atomik."""
        try:
            krs = self.db.scalar(
                select(KRS)
                .options(joinedload(KRS.details).joinedload(KRSDetail.matakuliah))
                .where(KRS.nim == nim, KRS.semester == self.semester)
                .with_for_update()
            )
            if not krs:
                raise KRSNotFoundError(
                    f"KRS untuk NIM '{nim}' pada semester {self.semester} tidak ditemukan"
                )

            if krs.status not in (KRSStatus.DRAFT.value, KRSStatus.REVISION.value):
                raise InvalidStateTransitionError(
                    f"Tidak dapat menghapus mata kuliah saat KRS berstatus {krs.status}"
                )

            detail_to_remove = next(
                (d for d in krs.details if d.kode_mk == kode_mk), None
            )
            if not detail_to_remove:
                raise KRSNotFoundError(
                    f"Mata kuliah '{kode_mk}' tidak ada di dalam KRS NIM '{nim}'"
                )

            self.db.delete(detail_to_remove)
            self.db.flush()

            remaining_courses = [
                d.matakuliah for d in krs.details if d.kode_mk != kode_mk
            ]
            krs.total_sks = sum(mk.sks for mk in remaining_courses)

            self.db.commit()
            return self.get_krs(nim)
        except Exception:
            self.db.rollback()
            raise

    def validate_krs(self, nim: str) -> ValidationResult:
        """Memvalidasi seluruh mata kuliah dalam KRS terhadap 4 aturan rantai validasi."""
        krs = self.get_krs(nim)
        courses = [detail.matakuliah for detail in krs.details]

        if not courses:
            return ValidationResult(
                is_valid=False,
                message="KRS masih kosong, minimal pilih 1 mata kuliah",
            )

        for idx, mk in enumerate(courses):
            other_courses = [c for i, c in enumerate(courses) if i != idx]
            context = ValidationContext(
                db=self.db,
                nim=nim,
                target_mk=mk,
                current_courses=other_courses,
            )
            result = self.validator_chain.validate(context)
            if not result.is_valid:
                return result

        return ValidationResult(is_valid=True, message="Seluruh aturan KRS terpenuhi")

    def submit_krs(self, nim: str) -> KRS:
        """Mengajukan KRS (DRAFT/REVISION -> SUBMITTED) setelah seluruh aturan lolos."""
        try:
            krs = self.db.scalar(
                select(KRS)
                .options(joinedload(KRS.details).joinedload(KRSDetail.matakuliah))
                .where(KRS.nim == nim, KRS.semester == self.semester)
                .with_for_update()
            )
            if not krs:
                raise KRSNotFoundError(
                    f"KRS untuk NIM '{nim}' pada semester {self.semester} tidak ditemukan"
                )

            validation = self.validate_krs(nim)
            if not validation.is_valid:
                raise KRSBusinessError(validation.message)

            self.transition(krs, KRSStatus.SUBMITTED)
            self.db.commit()
            return self.get_krs(nim)
        except Exception:
            self.db.rollback()
            raise

    def approve_krs(self, nim: str, dosen_pa_id: int) -> KRS:
        """Menyetujui KRS oleh Dosen PA (hanya sah dari status SUBMITTED -> APPROVED)."""
        try:
            krs = self.db.scalar(
                select(KRS)
                .where(KRS.nim == nim, KRS.semester == self.semester)
                .with_for_update()
            )
            if not krs:
                raise KRSNotFoundError(
                    f"KRS untuk NIM '{nim}' pada semester {self.semester} tidak ditemukan"
                )

            self.transition(krs, KRSStatus.APPROVED)
            krs.dosen_pa_id = dosen_pa_id
            krs.catatan_revisi = None

            self.db.commit()
            return self.get_krs(nim)
        except Exception:
            self.db.rollback()
            raise

    def reject_krs(
        self, nim: str, dosen_pa_id: int, catatan_revisi: str | None = None
    ) -> KRS:
        """Mengembalikan KRS ke mahasiswa untuk diperbaiki (SUBMITTED -> REVISION)."""
        try:
            krs = self.db.scalar(
                select(KRS)
                .where(KRS.nim == nim, KRS.semester == self.semester)
                .with_for_update()
            )
            if not krs:
                raise KRSNotFoundError(
                    f"KRS untuk NIM '{nim}' pada semester {self.semester} tidak ditemukan"
                )

            self.transition(krs, KRSStatus.REVISION)
            krs.dosen_pa_id = dosen_pa_id
            krs.catatan_revisi = catatan_revisi

            self.db.commit()
            return self.get_krs(nim)
        except Exception:
            self.db.rollback()
            raise