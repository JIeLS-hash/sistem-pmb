from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.matakuliah import MataKuliah

MAX_SKS_PER_SEMESTER = 24


@dataclass
class ValidationResult:
    is_valid: bool
    message: str = "Validasi berhasil"


@dataclass
class ValidationContext:
    db: Session
    nim: str
    target_mk: MataKuliah
    current_courses: list[MataKuliah]


class Validator(ABC):
    """Abstract base class untuk Chain of Responsibility validasi KRS."""

    def __init__(self) -> None:
        self._next_validator: Validator | None = None

    def set_next(self, validator: Validator) -> Validator:
        self._next_validator = validator
        return validator

    def validate(self, context: ValidationContext) -> ValidationResult:
        result = self._check(context)
        # Chain langsung berhenti (fail-fast) saat ada kegagalan
        if not result.is_valid:
            return result
        if self._next_validator is not None:
            return self._next_validator.validate(context)
        return ValidationResult(is_valid=True)

    @abstractmethod
    def _check(self, context: ValidationContext) -> ValidationResult:
        """Implementasi aturan validasi spesifik pada masing-masing subclass."""
        raise NotImplementedError


class DuplicateValidator(Validator):
    """1. Mencegah double enrollment pada mata kuliah yang sama dalam satu KRS."""

    def _check(self, context: ValidationContext) -> ValidationResult:
        for mk in context.current_courses:
            if mk.kode_mk == context.target_mk.kode_mk:
                return ValidationResult(
                    is_valid=False,
                    message=f"Mata kuliah sudah ada di KRS: {context.target_mk.nama} ({context.target_mk.kode_mk})",
                )
        return ValidationResult(is_valid=True)


class PrerequisiteValidator(Validator):
    """2. Memeriksa apakah seluruh prasyarat mata kuliah telah lulus (nilai >= C)."""

    _QUERY = text("""
        SELECT
            p.kode_mk_prasyarat,
            mk.nama AS nama_prasyarat
        FROM prerequisite p
        JOIN matakuliah mk
            ON mk.kode_mk = p.kode_mk_prasyarat
        JOIN skala_nilai sn_min
            ON sn_min.huruf = p.min_nilai_huruf
        WHERE p.kode_mk = :kode_mk
          AND NOT EXISTS (
              SELECT 1
              FROM riwayat_nilai rn
              JOIN skala_nilai sn_mhs
                  ON sn_mhs.huruf = rn.nilai_huruf
              WHERE rn.nim = :nim
                AND rn.kode_mk = p.kode_mk_prasyarat
                AND sn_mhs.bobot >= sn_min.bobot
          );
    """)

    def _check(self, context: ValidationContext) -> ValidationResult:
        rows = context.db.execute(
            self._QUERY,
            {"nim": context.nim, "kode_mk": context.target_mk.kode_mk},
        ).fetchall()

        if rows:
            belum_lulus = ", ".join(row.nama_prasyarat for row in rows)
            return ValidationResult(
                is_valid=False,
                message=f"Prasyarat tidak terpenuhi: {belum_lulus}",
            )
        return ValidationResult(is_valid=True)


class ConflictValidator(Validator):
    """3. Mendeteksi bentrok jadwal (hari sama dan irisan interval jam)."""

    def _check(self, context: ValidationContext) -> ValidationResult:
        target = context.target_mk
        for existing in context.current_courses:
            if existing.hari.lower() == target.hari.lower():
                # Irisan interval: mulai_A < selesai_B dan selesai_A > mulai_B
                is_overlap = (
                    target.jam_mulai < existing.jam_selesai
                    and target.jam_selesai > existing.jam_mulai
                )
                if is_overlap:
                    jam_eksisting = (
                        f"{existing.jam_mulai.strftime('%H:%M')}-"
                        f"{existing.jam_selesai.strftime('%H:%M')}"
                    )
                    return ValidationResult(
                        is_valid=False,
                        message=(
                            f"Jadwal bentrok dengan {existing.nama} "
                            f"({existing.hari} {jam_eksisting})"
                        ),
                    )
        return ValidationResult(is_valid=True)


class SKSValidator(Validator):
    """4. Memastikan total SKS per semester tidak melebihi batas 24 SKS."""

    def _check(self, context: ValidationContext) -> ValidationResult:
        current_sks = sum(mk.sks for mk in context.current_courses)
        projected_sks = current_sks + context.target_mk.sks

        if projected_sks > MAX_SKS_PER_SEMESTER:
            return ValidationResult(
                is_valid=False,
                message=(
                    f"Total SKS melebihi batas maksimal {MAX_SKS_PER_SEMESTER} SKS "
                    f"(saat ini {current_sks} SKS + {context.target_mk.sks} SKS = {projected_sks} SKS)"
                ),
            )
        return ValidationResult(is_valid=True)


def build_chain() -> Validator:
    """Merangkai validator sesuai urutan prioritas pengecekan."""
    duplicate_validator = DuplicateValidator()
    prerequisite_validator = PrerequisiteValidator()
    conflict_validator = ConflictValidator()
    sks_validator = SKSValidator()

    duplicate_validator.set_next(prerequisite_validator).set_next(
        conflict_validator
    ).set_next(sks_validator)

    return duplicate_validator