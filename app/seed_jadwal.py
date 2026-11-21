from __future__ import annotations

from datetime import time
from sqlalchemy import select
from sqlalchemy.orm import Session

import app.models  # noqa: F401
from app.database import SessionLocal
from app.models.jadwal import Dosen, Jadwal, Kelas, Ruangan
from app.models.matakuliah import MataKuliah


def seed_jadwal_data(db: Session) -> dict[str, int]:
    """Mengisi data master ruangan (>=10), dosen (>=15), kelas, dan jadwal (>=40) secara idempotent."""

    # 1. Seed 12 Ruangan (>= 10 ruangan)
    ruangan_list = [
        ("A101", 40),
        ("A102", 40),
        ("A103", 35),
        ("A201", 50),
        ("A202", 50),
        ("B101", 30),
        ("B102", 30),
        ("B201", 45),
        ("B202", 45),
        ("C301", 60),
        ("LAB1", 35),
        ("LAB2", 35),
    ]
    for kode, kapasitas in ruangan_list:
        if db.get(Ruangan, kode) is None:
            db.add(Ruangan(kode=kode, kapasitas=kapasitas))

    # 2. Seed 16 Dosen (>= 15 dosen)
    dosen_list = [
        ("0401018501", "Dr. Budi Santoso, M.Kom."),
        ("0402028602", "Dr. Siti Aminah, M.T."),
        ("0403038703", "Ahmad Fauzi, M.Sc."),
        ("0404048804", "Rina Wijaya, M.Kom."),
        ("0405058905", "Prof. Hendra Kusuma, Ph.D."),
        ("0406069006", "Dewi Lestari, M.T."),
        ("0407079107", "Eko Prasetyo, M.Kom."),
        ("0408089208", "Nurul Hidayah, M.Si."),
        ("0409098309", "Rizky Pratama, M.Cs."),
        ("0410108410", "Maya Sari, M.Kom."),
        ("0411118511", "Fajar Nugroho, M.T."),
        ("0412128612", "Indah Permata, M.Sc."),
        ("0413138713", "Dimas Saputra, M.Kom."),
        ("0414148814", "Putri Maharani, M.T."),
        ("0415158915", "Arif Rahman, M.Kom."),
        ("0416169016", "Yuni Kartika, M.Si."),
    ]
    dosen_map: dict[str, Dosen] = {}
    for nidn, nama in dosen_list:
        existing = db.scalar(select(Dosen).where(Dosen.nidn == nidn))
        if existing is None:
            existing = Dosen(nidn=nidn, nama=nama)
            db.add(existing)
            db.flush()
        dosen_map[nidn] = existing

    # 3. Pastikan Mata Kuliah tersedia sebagai induk Kelas
    mk_list = [
        ("IF101", "Algoritma & Pemrograman", 4, 1, True),
        ("IF102", "Kalkulus I", 3, 1, True),
        ("IF103", "Matematika Diskrit", 3, 1, True),
        ("IF104", "Pengantar Teknologi Informasi", 2, 1, True),
        ("IF201", "Struktur Data", 4, 2, True),
        ("IF202", "Basis Data", 3, 2, True),
        ("IF203", "Aljabar Linear", 3, 2, True),
        ("IF204", "Arsitektur Komputer", 3, 2, True),
        ("IF301", "Pemrograman Berorientasi Objek", 4, 3, True),
        ("IF302", "Sistem Operasi", 3, 3, True),
        ("IF303", "Jaringan Komputer", 3, 3, True),
        ("IF304", "Rekayasa Perangkat Lunak", 3, 3, True),
        ("IF401", "Kecerdasan Buatan", 3, 4, True),
        ("IF402", "Pemrograman Web", 3, 4, False),
    ]
    for kode_mk, nama_mk, sks, sem_paket, wajib in mk_list:
        
        if db.scalar(select(MataKuliah).where(MataKuliah.kode_mk == kode_mk)) is None:
            db.add(
        
                MataKuliah(
                    kode_mk=kode_mk,
                    nama=nama_mk,
                    sks=sks,
                    semester_paket=sem_paket,
                    is_wajib=wajib,
                    hari="Senin",
                    jam_mulai=time(8, 0),
                    jam_selesai=time(10, 0),
                )
            )
    db.flush()

    # 4. Seed 21 Kelas Paralel (Semester 2026/2027-1)
    semester_aktif = "2026/2027-1"
    kelas_specs = [
        ("IF101", "A", 35),
        ("IF101", "B", 35),
        ("IF102", "A", 40),
        ("IF102", "B", 40),
        ("IF103", "A", 35),
        ("IF104", "A", 45),
        ("IF201", "A", 30),
        ("IF201", "B", 30),
        ("IF202", "A", 35),
        ("IF202", "B", 35),
        ("IF203", "A", 40),
        ("IF204", "A", 40),
        ("IF301", "A", 30),
        ("IF301", "B", 30),
        ("IF302", "A", 35),
        ("IF303", "A", 35),
        ("IF304", "A", 45),
        ("IF401", "A", 35),
        ("IF401", "B", 35),
        ("IF402", "A", 30),
        ("IF402", "B", 30),
    ]
    kelas_map: dict[tuple[str, str], Kelas] = {}
    for kode_mk, nama_kelas, kuota in kelas_specs:
        existing_k = db.scalar(
            select(Kelas).where(
                Kelas.kode_mk == kode_mk,
                Kelas.nama == nama_kelas,
                Kelas.semester == semester_aktif,
            )
        )
        if existing_k is None:
            existing_k = Kelas(
                kode_mk=kode_mk,
                nama=nama_kelas,
                kuota=kuota,
                semester=semester_aktif,
            )
            db.add(existing_k)
            db.flush()
        kelas_map[(kode_mk, nama_kelas)] = existing_k

    # 5. Seed 42 Jadwal (>= 40 jadwal), hanya jika tabel jadwal masih kosong
    existing_jadwal_count = len(db.scalars(select(Jadwal)).all())
    if existing_jadwal_count == 0:
        d_ids = [dosen_map[nidn].id for nidn, _ in dosen_list]
        # Format: (kode_mk, kelas, hari[1..6], jam_mulai, jam_selesai, ruangan_kode, dosen_index)
        jadwal_specs = [
            # --- 38 Jadwal Normal (Bebas Bentrok) ---
            ("IF101", "A", 1, time(8, 0), time(10, 0), "A101", 0),
            ("IF101", "A", 4, time(8, 0), time(10, 0), "LAB1", 0),   # Praktikum
            ("IF101", "B", 1, time(10, 0), time(12, 0), "A102", 1),
            ("IF101", "B", 4, time(10, 0), time(12, 0), "LAB2", 1),  # Praktikum
            ("IF102", "A", 1, time(13, 0), time(15, 30), "A201", 2),
            ("IF102", "B", 1, time(15, 30), time(18, 0), "A202", 3),
            ("IF103", "A", 2, time(8, 0), time(10, 30), "A101", 4),
            ("IF104", "A", 2, time(10, 30), time(12, 10), "A201", 5),
            ("IF201", "A", 2, time(8, 0), time(10, 0), "B101", 6),
            ("IF201", "A", 5, time(8, 0), time(10, 0), "LAB1", 6),   # Praktikum
            ("IF201", "B", 2, time(10, 0), time(12, 0), "B102", 7),
            ("IF201", "B", 5, time(10, 0), time(12, 0), "LAB2", 7),  # Praktikum
            ("IF202", "A", 2, time(13, 0), time(15, 0), "B201", 8),
            ("IF202", "A", 5, time(13, 0), time(15, 0), "LAB1", 8),  # Praktikum
            ("IF202", "B", 2, time(15, 0), time(17, 0), "B202", 9),
            ("IF202", "B", 5, time(15, 0), time(17, 0), "LAB2", 9),  # Praktikum
            ("IF203", "A", 3, time(8, 0), time(10, 30), "A102", 10),
            ("IF204", "A", 3, time(10, 30), time(13, 0), "A103", 11),
            ("IF301", "A", 3, time(8, 0), time(10, 0), "B101", 12),
            ("IF301", "A", 6, time(8, 0), time(10, 0), "LAB1", 12),  # Praktikum
            ("IF301", "B", 3, time(10, 0), time(12, 0), "B102", 13),
            ("IF301", "B", 6, time(10, 0), time(12, 0), "LAB2", 13), # Praktikum
            ("IF302", "A", 3, time(13, 0), time(15, 30), "B201", 14),
            ("IF303", "A", 3, time(15, 30), time(18, 0), "B202", 15),
            ("IF304", "A", 4, time(8, 0), time(10, 30), "C301", 2),
            ("IF401", "A", 4, time(10, 30), time(13, 0), "A101", 4),
            ("IF401", "B", 4, time(13, 0), time(15, 30), "A102", 3),
            ("IF402", "A", 4, time(15, 30), time(17, 30), "LAB1", 10),
            ("IF402", "B", 5, time(8, 0), time(10, 0), "A103", 11),
            ("IF103", "A", 5, time(10, 0), time(11, 30), "A201", 4),
            ("IF203", "A", 5, time(13, 0), time(14, 30), "A202", 10),
            ("IF204", "A", 6, time(8, 0), time(9, 30), "A101", 11),
            ("IF302", "A", 6, time(10, 0), time(11, 30), "A102", 14),
            ("IF303", "A", 6, time(13, 0), time(15, 0), "B201", 15),
            ("IF304", "A", 1, time(8, 0), time(10, 0), "C301", 5),
            ("IF401", "A", 1, time(10, 30), time(12, 30), "C301", 6),
            ("IF402", "A", 2, time(13, 0), time(15, 0), "C301", 7),
            ("IF104", "A", 3, time(13, 30), time(15, 0), "C301", 8),

            # --- 4 Jadwal Bentrok yang Disengaja (untuk uji detector & GET /conflicts) ---
            # 1. Bentrok Ruangan (room_conflict): Senin 08:30-10:30 di A101 (bentrok dengan IF101-A 08:00-10:00)
            ("IF102", "A", 1, time(8, 30), time(10, 30), "A101", 12),
            # 2. Bentrok Dosen (lecturer_conflict): Selasa 09:00-11:00 dosen_index=6 di B202 (bentrok dengan IF201-A 08:00-10:00)
            ("IF401", "B", 2, time(9, 0), time(11, 0), "B202", 6),
            # 3. Bentrok Ruangan (room_conflict): Kamis 08:30-10:30 di LAB1 (bentrok dengan IF101-A 08:00-10:00)
            ("IF402", "B", 4, time(8, 30), time(10, 30), "LAB1", 13),
            # 4. Bentrok Dosen (lecturer_conflict): Jumat 13:30-15:30 dosen_index=8 di C301 (bentrok dengan IF202-A 13:00-15:00)
            ("IF304", "A", 5, time(13, 30), time(15, 30), "C301", 8),
        ]

        for kode_mk, nama_kelas, hari, mulai, selesai, ruang, d_idx in jadwal_specs:
            kelas_obj = kelas_map[(kode_mk, nama_kelas)]
            db.add(
                Jadwal(
                    kelas_id=kelas_obj.id,
                    hari=hari,
                    jam_mulai=mulai,
                    jam_selesai=selesai,
                    ruangan_kode=ruang,
                    dosen_id=d_ids[d_idx],
                )
            )

    db.commit()
    return {
        "ruangan": len(db.scalars(select(Ruangan)).all()),
        "dosen": len(db.scalars(select(Dosen)).all()),
        "kelas": len(db.scalars(select(Kelas)).all()),
        "jadwal": len(db.scalars(select(Jadwal)).all()),
    }


if __name__ == "__main__":
    session = SessionLocal()
    try:
        summary = seed_jadwal_data(session)
        print("Seed Jadwal & Ruangan selesai:", summary)
    finally:
        session.close()