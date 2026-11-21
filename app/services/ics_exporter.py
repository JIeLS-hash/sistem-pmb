from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.jadwal import Dosen, Jadwal, Kelas

BYDAY_MAP: dict[int, str] = {
    1: "MO",
    2: "TU",
    3: "WE",
    4: "TH",
    5: "FR",
    6: "SA",
}

# Tanggal patokan Senin awal semester (Senin, 7 September 2026)
SEMESTER_START_MONDAY = date(2026, 9, 7)


def _format_ics_dt(d: date, t: time) -> str:
    return f"{d.strftime('%Y%m%d')}T{t.strftime('%H%M%S')}"


def export_schedules_to_ics(
    db: Session,
    schedules: Sequence[Jadwal] | None = None,
    calendar_name: str = "Jadwal Kuliah PMB-KRS",
) -> str:
    """Mengekspor daftar jadwal kuliah ke format standar iCalendar (.ics / RFC 5545)."""
    if schedules is None:
        schedules = list(
            db.scalars(select(Jadwal).order_by(Jadwal.hari, Jadwal.jam_mulai, Jadwal.id)).all()
        )

    kelas_map = {k.id: k for k in db.scalars(select(Kelas)).all()}
    dosen_map = {d.id: d for d in db.scalars(select(Dosen)).all()}
    dtstamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    lines: list[str] = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//PMB-Project//Jadwal Kuliah//ID",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{calendar_name}",
    ]

    for j in schedules:
        kelas = kelas_map.get(j.kelas_id)
        dosen = dosen_map.get(j.dosen_id)
        kelas_label = f"{kelas.kode_mk} - Kelas {kelas.nama}" if kelas else f"Kelas #{j.kelas_id}"
        dosen_label = dosen.nama if dosen else f"Dosen #{j.dosen_id}"

        event_date = SEMESTER_START_MONDAY + timedelta(days=max(0, j.hari - 1))
        byday = BYDAY_MAP.get(j.hari, "MO")

        lines.extend(
            [
                "BEGIN:VEVENT",
                f"UID:jadwal-{j.id}@pmb-project.local",
                f"DTSTAMP:{dtstamp}",
                f"DTSTART:{_format_ics_dt(event_date, j.jam_mulai)}",
                f"DTEND:{_format_ics_dt(event_date, j.jam_selesai)}",
                f"RRULE:FREQ=WEEKLY;COUNT=16;BYDAY={byday}",
                f"SUMMARY:{kelas_label}",
                f"LOCATION:Ruang {j.ruangan_kode}",
                f"DESCRIPTION:Pengampu: {dosen_label} | Jadwal ID: {j.id}",
                "END:VEVENT",
            ]
        )

    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"