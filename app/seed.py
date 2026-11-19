
from app.database import SessionLocal
from app.models import ProgramStudi, JalurMasuk


def seed_master_data():
    db = SessionLocal()

    try:
        # Data program studi
        programs = [
            {
                "kode": "001",
                "nama": "Teknik Informatika",
                "fakultas": "Teknik"
            },
            {
                "kode": "002",
                "nama": "Sistem Informasi",
                "fakultas": "Teknik"
            },
            {
                "kode": "003",
                "nama": "Manajemen",
                "fakultas": "Ekonomi"
            }
        ]

        for item in programs:
            existing = db.query(ProgramStudi).filter_by(
                kode=item["kode"]
            ).first()

            if existing is None:
                db.add(ProgramStudi(**item))

        # Data jalur masuk
        admission_paths = ["SNBP", "SNBT", "Mandiri"]

        for nama in admission_paths:
            existing = db.query(JalurMasuk).filter_by(
                nama=nama
            ).first()

            if existing is None:
                db.add(JalurMasuk(nama=nama))

        db.commit()

        print("DATA MASTER BERHASIL DISIAPKAN")

        print("\nDAFTAR PROGRAM STUDI:")
        for item in db.query(ProgramStudi).order_by(
            ProgramStudi.id
        ).all():
            print(item.id, item.kode, item.nama)

        print("\nDAFTAR JALUR MASUK:")
        for item in db.query(JalurMasuk).order_by(
            JalurMasuk.id
        ).all():
            print(item.id, item.nama)

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


if __name__ == "__main__":
    seed_master_data()
