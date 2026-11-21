
from fastapi import FastAPI

from app.routers.pmb import router as pmb_router
from app.routers.krs import router as krs_router
from app.routers.jadwal import router as jadwal_router
app = FastAPI(
    title="Sistem Penerimaan Mahasiswa Baru",
    description="REST API untuk sistem PMB",
    version="1.0.0"
)


# Menghubungkan router PMB ke aplikasi utama
app.include_router(pmb_router)
app.include_router(krs_router)
app.include_router(jadwal_router)
@app.get("/")
def home():
    return {
        "message": "Sistem PMB berhasil dijalankan"
    }
