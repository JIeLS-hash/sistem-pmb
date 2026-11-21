from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import time
from typing import Any, Sequence


@dataclass(frozen=True)
class NormalizedSchedule:
    """Representasi seragam untuk objek ORM Jadwal maupun dict pengujian."""

    idx: int
    id: int | None
    kelas_id: int | None
    hari: int | str
    jam_mulai: time
    jam_selesai: time
    ruangan: str | None
    dosen: int | str | None
    raw: Any

    @property
    def sort_key(self) -> tuple[int, int]:
        return (0, self.id) if self.id is not None else (1, self.idx)


def _parse_time(value: time | str) -> time:
    if isinstance(value, time):
        return value
    parts = [int(p) for p in value.split(":")]
    return time(parts[0], parts[1], parts[2] if len(parts) > 2 else 0)


def _normalize(item: Any, idx: int) -> NormalizedSchedule:
    if isinstance(item, dict):
        sched_id = item.get("id")
        kelas_id = item.get("kelas_id")
        hari = item["hari"]
        jam_mulai = _parse_time(item["jam_mulai"])
        jam_selesai = _parse_time(item["jam_selesai"])
        ruangan = item.get("ruangan_kode") or item.get("ruangan")
        dosen = item.get("dosen_id") if item.get("dosen_id") is not None else item.get("dosen")
    else:
        sched_id = getattr(item, "id", None)
        kelas_id = getattr(item, "kelas_id", None)
        hari = getattr(item, "hari")
        jam_mulai = _parse_time(getattr(item, "jam_mulai"))
        jam_selesai = _parse_time(getattr(item, "jam_selesai"))
        ruangan = getattr(item, "ruangan_kode", None) or getattr(item, "ruangan", None)
        dosen = getattr(item, "dosen_id", None)
        if dosen is None:
            dosen = getattr(item, "dosen", None)

    return NormalizedSchedule(
        idx=idx,
        id=sched_id,
        kelas_id=kelas_id,
        hari=hari,
        jam_mulai=jam_mulai,
        jam_selesai=jam_selesai,
        ruangan=ruangan,
        dosen=dosen,
        raw=item,
    )


def _serialize_schedule(s: NormalizedSchedule) -> dict[str, Any]:
    return {
        "id": s.id,
        "kelas_id": s.kelas_id,
        "hari": s.hari,
        "jam_mulai": s.jam_mulai.strftime("%H:%M"),
        "jam_selesai": s.jam_selesai.strftime("%H:%M"),
        "ruangan": s.ruangan,
        "dosen": s.dosen,
    }


def is_time_overlap(
    start_a: time, end_a: time, start_b: time, end_b: time
) -> bool:
    """Cek irisan dua interval setengah terbuka [start, end)."""
    return start_a < end_b and start_b < end_a


def _pair_conflicts(a: NormalizedSchedule, b: NormalizedSchedule) -> list[dict[str, Any]]:
    if a.hari != b.hari:
        return []
    if not is_time_overlap(a.jam_mulai, a.jam_selesai, b.jam_mulai, b.jam_selesai):
        return []

    first, second = (a, b) if a.sort_key <= b.sort_key else (b, a)
    affected = [_serialize_schedule(first), _serialize_schedule(second)]
    found: list[dict[str, Any]] = []

    if first.ruangan is not None and first.ruangan == second.ruangan:
        found.append(
            {
                "type": "room_conflict",
                "hari": first.hari,
                "ruangan": first.ruangan,
                "affected_schedules": affected,
            }
        )

    if first.dosen is not None and first.dosen == second.dosen:
        found.append(
            {
                "type": "lecturer_conflict",
                "hari": first.hari,
                "dosen": first.dosen,
                "affected_schedules": affected,
            }
        )

    return found


def _conflict_sort_key(conflict: dict[str, Any]) -> tuple[Any, ...]:
    s1, s2 = conflict["affected_schedules"]
    k1 = (0, s1["id"]) if s1["id"] is not None else (1, s1["jam_mulai"], str(s1["ruangan"]))
    k2 = (0, s2["id"]) if s2["id"] is not None else (1, s2["jam_mulai"], str(s2["ruangan"]))
    return (str(conflict["hari"]), k1, k2, conflict["type"])


def detect_naive(schedules: Sequence[Any]) -> list[dict[str, Any]]:
    """Deteksi bentrok 3 dimensi dengan perbandingan pasangan naif O(N^2)."""
    normalized = [_normalize(item, idx) for idx, item in enumerate(schedules)]
    conflicts: list[dict[str, Any]] = []

    n = len(normalized)
    for i in range(n):
        for j in range(i + 1, n):
            conflicts.extend(_pair_conflicts(normalized[i], normalized[j]))

    conflicts.sort(key=_conflict_sort_key)
    return conflicts


def detect_schedule_conflict(schedules: Sequence[Any]) -> list[dict[str, Any]]:
    """Deteksi bentrok 3 dimensi teroptimasi dengan Sweep-Line O(N log N + K)."""
    normalized = [_normalize(item, idx) for idx, item in enumerate(schedules)]
    by_day: dict[int | str, list[NormalizedSchedule]] = defaultdict(list)
    for item in normalized:
        by_day[item.hari].append(item)

    conflicts: list[dict[str, Any]] = []

    for _hari, day_items in by_day.items():
        # Urutkan berdasarkan jam_mulai agar garis sapu bergerak kronologis
        day_items.sort(key=lambda s: (s.jam_mulai, s.jam_selesai, s.sort_key))
        active: list[NormalizedSchedule] = []

        for current in day_items:
            # Buang jadwal yang sudah selesai sebelum atau tepat saat current mulai
            active = [prev for prev in active if prev.jam_selesai > current.jam_mulai]

            # Semua jadwal yang tersisa di 'active' pasti beririsan waktu dengan 'current'
            for prev in active:
                conflicts.extend(_pair_conflicts(prev, current))

            active.append(current)

    conflicts.sort(key=_conflict_sort_key)
    return conflicts


if __name__ == "__main__":
    from sqlalchemy import select
    import app.models  # noqa: F401
    from app.database import SessionLocal
    from app.models.jadwal import Jadwal

    db = SessionLocal()
    try:
        all_schedules = db.scalars(select(Jadwal)).all()
        naive_res = detect_naive(all_schedules)
        sweep_res = detect_schedule_conflict(all_schedules)
        assert naive_res == sweep_res, "Hasil naive dan sweep-line tidak identik!"
        print(f"Total jadwal diperiksa : {len(all_schedules)}")
        print(f"Total bentrok terdeteksi: {len(sweep_res)}")
        for idx, c in enumerate(sweep_res, start=1):
            s1, s2 = c["affected_schedules"]
            print(
                f"  {idx}. [{c['type']}] Hari {c['hari']} | "
                f"Jadwal #{s1['id']} ({s1['jam_mulai']}-{s1['jam_selesai']}) vs "
                f"Jadwal #{s2['id']} ({s2['jam_mulai']}-{s2['jam_selesai']})"
            )
    finally:
        db.close()