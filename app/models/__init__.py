
from app.models.program_studi import ProgramStudi
from app.models.jalur_masuk import JalurMasuk
from app.models.calon_mahasiswa import CalonMahasiswa
from app.models.skala_nilai import SkalaNilai
from app.models.matakuliah import MataKuliah
from app.models.prerequisite import Prerequisite
from app.models.krs import KRS, KRSDetail
from app.models.riwayat_nilai import RiwayatNilai
from app.models.jadwal import Ruangan, Dosen, Kelas, Jadwal
from app.models.outbox import OutboxEvent
__all__ = [
    "ProgramStudi",
    "JalurMasuk",
    "CalonMahasiswa",
]
