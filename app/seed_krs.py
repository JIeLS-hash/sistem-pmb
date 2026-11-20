from datetime import date, time
from sqlalchemy import select

from app.database import SessionLocal
from app.models.program_studi import ProgramStudi
from app.models.jalur_masuk import JalurMasuk
from app.models.calon_mahasiswa import CalonMahasiswa
from app.models.skala_nilai import SkalaNilai
from app.models.matakuliah import MataKuliah
from app.models.prerequisite import Prerequisite
from app.models.riwayat_nilai import RiwayatNilai


def seed_krs_data() -> None:
    db = SessionLocal()
    try:
        # 1. Seed Skala Nilai (A - E)
        skala_data = [
            ("A", 4.0),
            ("B", 3.0),
            ("C", 2.0),
            ("D", 1.0),
            ("E", 0.0),
        ]
        for huruf, bobot in skala_data:
            exists = db.scalar(select(SkalaNilai).where(SkalaNilai.huruf == huruf))
            if not exists:
                db.add(SkalaNilai(huruf=huruf, bobot=bobot))
        db.commit()

        # 2. Seed Mata Kuliah (beragam SKS, wajib/pilihan, & skenario bentrok)
        mk_data = [
            # Semester 1 (Dasar)
            MataKuliah(
                kode_mk="IF101", nama="Algoritma dan Pemrograman", sks=4,
                semester_paket=1, is_wajib=True,
                hari="Senin", jam_mulai=time(8, 0), jam_selesai=time(10, 30)
            ),
            MataKuliah(
                kode_mk="IF102", nama="Kalkulus I", sks=3,
                semester_paket=1, is_wajib=True,
                hari="Selasa", jam_mulai=time(8, 0), jam_selesai=time(10, 0)
            ),
            # Semester 2 & 3 (Memiliki Prasyarat & Skenario Bentrok)
            MataKuliah(
                kode_mk="IF201", nama="Struktur Data", sks=4,
                semester_paket=2, is_wajib=True,
                hari="Rabu", jam_mulai=time(8, 0), jam_selesai=time(10, 30)
            ),
            MataKuliah(
                kode_mk="IF202", nama="Basis Data", sks=3,
                semester_paket=2, is_wajib=True,
                # Sengaja bentrok dengan IF201 (Rabu 09:30 - 10:30 beririsan)
                hari="Rabu", jam_mulai=time(9, 30), jam_selesai=time(11, 30)
            ),
            MataKuliah(
                kode_mk="IF203", nama="Aljabar Linear", sks=3,
                semester_paket=2, is_wajib=True,
                hari="Kamis", jam_mulai=time(10, 0), jam_selesai=time(12, 0)
            ),
            MataKuliah(
                kode_mk="IF301", nama="Kecerdasan Buatan", sks=3,
                semester_paket=3, is_wajib=False,
                hari="Jumat", jam_mulai=time(8, 0), jam_selesai=time(10, 0)
            ),
            # Tambahan MK tanpa bentrok untuk simulasi batas > 24 SKS
            MataKuliah(
                kode_mk="IF302", nama="Jaringan Komputer", sks=4,
                semester_paket=3, is_wajib=True,
                hari="Senin", jam_mulai=time(13, 0), jam_selesai=time(15, 30)
            ),
            MataKuliah(
                kode_mk="IF303", nama="Sistem Operasi", sks=4,
                semester_paket=3, is_wajib=True,
                hari="Selasa", jam_mulai=time(13, 0), jam_selesai=time(15, 30)
            ),
            MataKuliah(
                kode_mk="IF304", nama="Rekayasa Perangkat Lunak", sks=4,
                semester_paket=3, is_wajib=True,
                hari="Kamis", jam_mulai=time(13, 0), jam_selesai=time(15, 30)
            ),
            MataKuliah(
                kode_mk="IF305", nama="Pemrograman Web", sks=4,
                semester_paket=3, is_wajib=False,
                hari="Jumat", jam_mulai=time(13, 0), jam_selesai=time(15, 30)
            ),
        ]
        for mk in mk_data:
            exists = db.scalar(select(MataKuliah).where(MataKuliah.kode_mk == mk.kode_mk))
            if not exists:
                db.add(mk)
        db.commit()

        # 3. Seed Relasi Prerequisite
        prereq_data = [
            ("IF201", "IF101", "C"),  # Struktur Data butuh Algoritma >= C
            ("IF203", "IF102", "C"),  # Aljabar Linear butuh Kalkulus I >= C
            ("IF301", "IF201", "C"),  # Kecerdasan Buatan butuh Struktur Data >= C
            ("IF301", "IF203", "C"),  # Kecerdasan Buatan butuh Aljabar Linear >= C
        ]
        for kode_mk, kode_prereq, min_huruf in prereq_data:
            exists = db.scalar(
                select(Prerequisite).where(
                    Prerequisite.kode_mk == kode_mk,
                    Prerequisite.kode_mk_prasyarat == kode_prereq,
                )
            )
            if not exists:
                db.add(
                    Prerequisite(
                        kode_mk=kode_mk,
                        kode_mk_prasyarat=kode_prereq,
                        min_nilai_huruf=min_huruf,
                    )
                )
        db.commit()

        # 4. Pastikan referensi Prodi & Jalur Masuk tersedia untuk Mahasiswa Dummy
        prodi = db.scalar(select(ProgramStudi))
        if not prodi:
            prodi = ProgramStudi(kode="TIF", nama="Teknik Informatika", fakultas="Ilmu Komputer")
            db.add(prodi)
            db.commit()
            db.refresh(prodi)

        jalur = db.scalar(select(JalurMasuk))
        if not jalur:
            jalur = JalurMasuk(nama="Reguler")
            db.add(jalur)
            db.commit()
            db.refresh(jalur)

        # 5. Seed Mahasiswa Dummy ber-NIM (status approved)
        nim_dummy = "2026001001"
        mhs = db.scalar(select(CalonMahasiswa).where(CalonMahasiswa.nim == nim_dummy))
        if not mhs:
            mhs = CalonMahasiswa(
                nama_lengkap="Budi Santoso",
                email="budi.santoso@kampus.ac.id",
                phone="081234567890",
                tanggal_lahir=date(2005, 5, 14),
                alamat="Jl. Margonda Raya No. 100, Depok",
                program_studi_id=prodi.id,
                jalur_masuk_id=jalur.id,
                status="approved",
                nim=nim_dummy,
            )
            db.add(mhs)
            db.commit()

        # 6. Seed Riwayat Nilai Semester Lalu untuk NIM 2026001001
        # Lulus IF101 (B >= C), tetapi TIDAK lulus IF102 (D < C)
        riwayat_data = [
            ("2026001001", "IF101", "2025/2026-1", "B"),
            ("2026001001", "IF102", "2025/2026-1", "D"),
        ]
        for nim, kode_mk, smt, huruf in riwayat_data:
            exists = db.scalar(
                select(RiwayatNilai).where(
                    RiwayatNilai.nim == nim,
                    RiwayatNilai.kode_mk == kode_mk,
                    RiwayatNilai.semester == smt,
                )
            )
            if not exists:
                db.add(
                    RiwayatNilai(
                        nim=nim,
                        kode_mk=kode_mk,
                        semester=smt,
                        nilai_huruf=huruf,
                    )
                )
        db.commit()
        print("Seed data KRS, mata kuliah, prasyarat, dan riwayat nilai berhasil dijalankan!")
    finally:
        db.close()


if __name__ == "__main__":
    seed_krs_data()