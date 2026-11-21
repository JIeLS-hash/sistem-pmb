from __future__ import annotations

import json
from datetime import time
from typing import Any, Callable, Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.jadwal import Dosen, Jadwal, Kelas, Ruangan
from app.models.krs import KRSDetail
from app.services.conflict_detector import _normalize, _pair_conflicts
from app.services.scheduling_service import SchedulingNotFoundError

HARI_MAP: dict[int, str] = {
    1: "Senin",
    2: "Selasa",
    3: "Rabu",
    4: "Kamis",
    5: "Jumat",
    6: "Sabtu",
}


def _parse_time_safe(val: time | str) -> time:
    if isinstance(val, time):
        return val
    parts = [int(p) for p in str(val).strip().split(":")]
    return time(parts[0], parts[1], parts[2] if len(parts) > 2 else 0)


def build_reschedule_prompt(
    target_jadwal: Jadwal,
    kelas: Kelas,
    dosen: Dosen,
    ruangan_list: Sequence[Ruangan],
    all_schedules: Sequence[Jadwal],
) -> str:
    """Menyusun Prompt Step 3 (Context + Constraints + Output Schema) untuk AI Rescheduling."""
    ruang_str = ", ".join(
        f"{r.kode} (kapasitas={r.kapasitas})" for r in ruangan_list
    )
    occupied_lines = [
        f"- Jadwal #{j.id}: Hari {j.hari} ({HARI_MAP.get(j.hari, '?')}) "
        f"{j.jam_mulai.strftime('%H:%M')}-{j.jam_selesai.strftime('%H:%M')} | "
        f"Ruang={j.ruangan_kode} | DosenID={j.dosen_id}"
        for j in all_schedules
        if j.id != target_jadwal.id
    ]
    occupied_block = "\n".join(occupied_lines[:30]) or "- Tidak ada jadwal lain"

    return (
        "=== PROMPT STEP 3: AI SCHEDULE CONFLICT RESOLVER ===\n"
        "PERAN: Asisten Penjadwalan Akademik Universitas.\n"
        "TUGAS: Berikan 3 sampai 5 alternatif slot jadwal pengganti untuk kelas yang bentrok.\n\n"
        "DATA JADWAL BERMASALAH:\n"
        f"- Jadwal ID   : {target_jadwal.id}\n"
        f"- Mata Kuliah : {kelas.kode_mk} - Kelas {kelas.nama} (Kuota={kelas.kuota})\n"
        f"- Dosen       : {dosen.nama} (ID={dosen.id})\n"
        f"- Slot Lama   : Hari {target_jadwal.hari} ({HARI_MAP.get(target_jadwal.hari, '?')}) "
        f"{target_jadwal.jam_mulai.strftime('%H:%M')}-{target_jadwal.jam_selesai.strftime('%H:%M')} "
        f"di {target_jadwal.ruangan_kode}\n\n"
        "HARD CONSTRAINTS (WAJIB DIPATUHI):\n"
        "1. Hari bernilai 1 (Senin) sampai 6 (Sabtu), dan jam_mulai < jam_selesai.\n"
        f"2. Kapasitas ruangan harus >= kuota kelas ({kelas.kuota}). Daftar ruangan: [{ruang_str}].\n"
        "3. Tidak boleh bentrok ruangan maupun bentrok dosen pada interval [jam_mulai, jam_selesai).\n\n"
        "JADWAL EKSISTING (RINGKASAN):\n"
        f"{occupied_block}\n\n"
        "FORMAT KELUARAN WAJIB (JSON Array):\n"
        '[{"hari": 1..6, "jam_mulai": "HH:MM", "jam_selesai": "HH:MM", '
        '"ruangan_kode": "KODE", "alasan": "..."}]'
    )


def saring_saran(
    raw_suggestions: Sequence[dict[str, Any]],
    target_jadwal: Jadwal,
    kelas: Kelas,
    enrolled_count: int,
    ruangan_map: dict[str, Ruangan],
    existing_schedules: Sequence[Jadwal],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Saringan validator deterministik untuk memfilter saran mentah AI terhadap seluruh
    hard constraint (format waktu, keberadaan & kapasitas ruangan, dan bentrok 3 dimensi).
    """
    valid_suggestions: list[dict[str, Any]] = []
    rejected_suggestions: list[dict[str, Any]] = []
    seen_keys: set[tuple[int, str, str, str]] = set()
    required_seats = max(kelas.kuota, enrolled_count)

    for raw in raw_suggestions:
        try:
            hari = int(raw["hari"])
            jam_mulai = _parse_time_safe(raw["jam_mulai"])
            jam_selesai = _parse_time_safe(raw["jam_selesai"])
            ruangan_kode = str(raw["ruangan_kode"]).strip()
            alasan = str(raw.get("alasan", "Saran alternatif tervalidasi oleh sistem"))
        except (KeyError, ValueError, TypeError) as exc:
            rejected_suggestions.append(
                {"candidate": dict(raw), "reason": f"Format saran tidak valid: {exc}"}
            )
            continue

        if not (1 <= hari <= 6) or jam_mulai >= jam_selesai:
            rejected_suggestions.append(
                {
                    "candidate": dict(raw),
                    "reason": "Hari di luar 1..6 atau jam_mulai >= jam_selesai",
                }
            )
            continue

        ruangan = ruangan_map.get(ruangan_kode)
        if ruangan is None:
            rejected_suggestions.append(
                {
                    "candidate": dict(raw),
                    "reason": f"Ruangan '{ruangan_kode}' tidak terdaftar",
                }
            )
            continue

        if ruangan.kapasitas < required_seats:
            rejected_suggestions.append(
                {
                    "candidate": dict(raw),
                    "reason": (
                        f"Kapasitas {ruangan.kode} ({ruangan.kapasitas}) < "
                        f"kebutuhan kursi ({required_seats})"
                    ),
                }
            )
            continue

        dedup_key = (
            hari,
            jam_mulai.strftime("%H:%M"),
            jam_selesai.strftime("%H:%M"),
            ruangan_kode,
        )
        if dedup_key in seen_keys:
            continue
        seen_keys.add(dedup_key)

        candidate_norm = _normalize(
            {
                "id": target_jadwal.id,
                "kelas_id": kelas.id,
                "hari": hari,
                "jam_mulai": jam_mulai,
                "jam_selesai": jam_selesai,
                "ruangan_kode": ruangan_kode,
                "dosen_id": target_jadwal.dosen_id,
            },
            idx=len(existing_schedules),
        )

        conflicts: list[dict[str, Any]] = []
        for idx, existing in enumerate(existing_schedules):
            if existing.id == target_jadwal.id:
                continue
            existing_norm = _normalize(existing, idx=idx)
            conflicts.extend(_pair_conflicts(existing_norm, candidate_norm))

        if conflicts:
            rejected_suggestions.append(
                {
                    "candidate": dict(raw),
                    "reason": f"Masih bentrok ({conflicts[0]['type']})",
                }
            )
            continue

        valid_suggestions.append(
            {
                "hari": hari,
                "hari_nama": HARI_MAP.get(hari, str(hari)),
                "jam_mulai": jam_mulai.strftime("%H:%M:%S"),
                "jam_selesai": jam_selesai.strftime("%H:%M:%S"),
                "ruangan_kode": ruangan.kode,
                "kapasitas_ruangan": ruangan.kapasitas,
                "dosen_id": target_jadwal.dosen_id,
                "alasan": alasan,
            }
        )

    return valid_suggestions, rejected_suggestions


class AIRescheduler:
    """Layanan rekomendasi penjadwalan ulang berbantuan AI yang disaring validator sistem."""

    @staticmethod
    def _default_ai_candidate_generator(
        target_jadwal: Jadwal,
        kelas: Kelas,
        ruangan_list: Sequence[Ruangan],
    ) -> list[dict[str, Any]]:
        """
        Menghasilkan kandidat mentah (termasuk beberapa kandidat spekulatif/berisiko
        layaknya keluaran LLM sebelum disaring oleh `saring_saran`).
        """
        duration_minutes = (
            target_jadwal.jam_selesai.hour * 60 + target_jadwal.jam_selesai.minute
        ) - (target_jadwal.jam_mulai.hour * 60 + target_jadwal.jam_mulai.minute)
        if duration_minutes <= 0:
            duration_minutes = 120

        candidates: list[dict[str, Any]] = []

        # Kandidat spekulatif pertama: sengaja memakai ruangan kecil / jam padat untuk diuji saringan
        if ruangan_list:
            smallest_room = min(ruangan_list, key=lambda r: r.kapasitas)
            candidates.append(
                {
                    "hari": target_jadwal.hari,
                    "jam_mulai": target_jadwal.jam_mulai.strftime("%H:%M"),
                    "jam_selesai": target_jadwal.jam_selesai.strftime("%H:%M"),
                    "ruangan_kode": smallest_room.kode,
                    "alasan": "Kandidat AI awal pada hari yang sama",
                }
            )

        # Eksplorasi kombinasi hari (1..6), slot waktu standar, dan seluruh ruangan
        candidate_starts = [time(8, 0), time(10, 0), time(13, 0), time(15, 30)]
        for hari in range(1, 7):
            for start_t in candidate_starts:
                end_total = start_t.hour * 60 + start_t.minute + duration_minutes
                if end_total > 18 * 60:
                    continue
                end_t = time(end_total // 60, end_total % 60)
                for room in ruangan_list:
                    candidates.append(
                        {
                            "hari": hari,
                            "jam_mulai": start_t.strftime("%H:%M"),
                            "jam_selesai": end_t.strftime("%H:%M"),
                            "ruangan_kode": room.kode,
                            "alasan": (
                                f"Slot alternatif {HARI_MAP[hari]} "
                                f"{start_t.strftime('%H:%M')}-{end_t.strftime('%H:%M')} "
                                f"di ruang {room.kode} (kapasitas {room.kapasitas})"
                            ),
                        }
                    )
        return candidates

    @classmethod
    def suggest_reschedule_options(
        cls,
        db: Session,
        jadwal_id: int,
        raw_candidates: Sequence[dict[str, Any]] | None = None,
        llm_fn: Callable[[str], str] | None = None,
        limit: int = 5,
    ) -> dict[str, Any]:
        target_jadwal = db.get(Jadwal, jadwal_id)
        if target_jadwal is None:
            raise SchedulingNotFoundError(f"Jadwal dengan id={jadwal_id} tidak ditemukan")

        kelas = db.get(Kelas, target_jadwal.kelas_id)
        if kelas is None:
            raise SchedulingNotFoundError(
                f"Kelas dengan id={target_jadwal.kelas_id} tidak ditemukan"
            )

        dosen = db.get(Dosen, target_jadwal.dosen_id)
        if dosen is None:
            raise SchedulingNotFoundError(
                f"Dosen dengan id={target_jadwal.dosen_id} tidak ditemukan"
            )

        ruangan_list = list(db.scalars(select(Ruangan).order_by(Ruangan.kode)).all())
        ruangan_map = {r.kode: r for r in ruangan_list}
        all_schedules = list(
            db.scalars(select(Jadwal).order_by(Jadwal.hari, Jadwal.jam_mulai, Jadwal.id)).all()
        )
        enrolled_count = (
            db.scalar(
                select(func.count(KRSDetail.id)).where(KRSDetail.kelas_id == kelas.id)
            )
            or 0
        )

        prompt_step_3 = build_reschedule_prompt(
            target_jadwal, kelas, dosen, ruangan_list, all_schedules
        )

        if raw_candidates is not None:
            candidates = list(raw_candidates)
        elif llm_fn is not None:
            raw_json_text = llm_fn(prompt_step_3)
            candidates = json.loads(raw_json_text)
        else:
            candidates = cls._default_ai_candidate_generator(
                target_jadwal, kelas, ruangan_list
            )

        valid, rejected = saring_saran(
            raw_suggestions=candidates,
            target_jadwal=target_jadwal,
            kelas=kelas,
            enrolled_count=enrolled_count,
            ruangan_map=ruangan_map,
            existing_schedules=all_schedules,
        )

        return {
            "jadwal_id": target_jadwal.id,
            "kelas_kode": f"{kelas.kode_mk}-{kelas.nama}",
            "prompt_step_3": prompt_step_3,
            "raw_count": len(candidates),
            "valid_count": len(valid[:limit]),
            "rejected_count": len(rejected),
            "suggestions": valid[:limit],
            "rejected_samples": rejected[:5],
        }