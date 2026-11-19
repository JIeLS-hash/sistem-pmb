
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.calon_mahasiswa import CalonMahasiswa


def generate_nim(
    tahun: int,
    kode_prodi: str,
    db: Session
) -> str:
    """
    Membuat NIM dengan format:
    YYYY + KODE_PRODI + - + RUNNING_NUMBER

    Contoh:
    2026001-0001

    Fungsi ini harus dipanggil di dalam transaksi
    yang sudah mengunci database SQLite.
    """

    # Validasi tahun dan kode program studi
    if not 1000 <= tahun <= 9999:
        raise ValueError("Tahun harus terdiri dari 4 digit")

    if len(kode_prodi) != 3:
        raise ValueError("Kode program studi harus 3 karakter")

    # Membuat awalan NIM
    prefix = f"{tahun}{kode_prodi}"

    # Mencari NIM terakhir untuk tahun dan prodi tersebut
    last_nim = db.execute(
        select(CalonMahasiswa.nim)
        .where(
            CalonMahasiswa.nim.like(f"{prefix}-%")
        )
        .order_by(CalonMahasiswa.nim.desc())
        .limit(1)
    ).scalar_one_or_none()

    # Menentukan nomor urut berikutnya
    if last_nim is None:
        next_number = 1
    else:
        last_number = int(last_nim.rsplit("-", 1)[1])
        next_number = last_number + 1

    # Memeriksa batas nomor urut
    if next_number > 9999:
        raise ValueError(
            "Nomor urut NIM sudah mencapai batas maksimum"
        )

    # Membentuk NIM baru
    nim = f"{prefix}-{next_number:04d}"

    return nim
