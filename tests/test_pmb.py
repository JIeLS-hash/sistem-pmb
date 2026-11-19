
import pytest

from datetime import date, datetime

from app.database import get_db
from app.models import (
    ProgramStudi,
    JalurMasuk,
    CalonMahasiswa
)

from app.services.nim_generator import generate_nim
from app import seed

# Data master untuk kebutuhan pengujian
@pytest.fixture
def master_data(test_session_factory):
    db = test_session_factory()

    try:
        # Membuat program studi
        program = ProgramStudi(
            kode="001",
            nama="Teknik Informatika",
            fakultas="Teknik"
        )

        # Membuat jalur masuk
        jalur = JalurMasuk(
            nama="SNBP"
        )

        db.add_all([program, jalur])
        db.commit()

        db.refresh(program)
        db.refresh(jalur)

        return {
            "program_studi_id": program.id,
            "jalur_masuk_id": jalur.id
        }

    finally:
        db.close()


# Membuat data pendaftaran contoh
def buat_data_mahasiswa(master_data, email="budi@example.com"):
    return {
        "nama_lengkap": "Budi Santoso",
        "email": email,
        "phone": "081234567890",
        "tanggal_lahir": "2005-05-20",
        "alamat": "Jakarta Selatan",
        "program_studi_id": master_data["program_studi_id"],
        "jalur_masuk_id": master_data["jalur_masuk_id"]
    }


# TEST 1: Halaman utama berhasil diakses
def test_home(client):
    response = client.get("/")

    assert response.status_code == 200

    assert response.json() == {
        "message": "Sistem PMB berhasil dijalankan"
    }


# TEST 2: Registrasi mahasiswa berhasil
def test_register_success(client, master_data):
    response = client.post(
        "/api/pmb/register",
        json=buat_data_mahasiswa(master_data)
    )

    assert response.status_code == 201

    data = response.json()

    assert data["nama_lengkap"] == "Budi Santoso"
    assert data["email"] == "budi@example.com"
    assert data["status"] == "pending"
    assert data["nim"] is None


# TEST 3: Email duplikat harus ditolak
def test_register_duplicate_email(client, master_data):
    payload = buat_data_mahasiswa(master_data)

    # Pendaftaran pertama
    response_pertama = client.post(
        "/api/pmb/register",
        json=payload
    )

    assert response_pertama.status_code == 201

    # Pendaftaran kedua menggunakan email sama
    response_kedua = client.post(
        "/api/pmb/register",
        json=payload
    )

    assert response_kedua.status_code == 409

    assert response_kedua.json()["detail"] == (
        "Email sudah terdaftar"
    )


# TEST 4: Nomor telepon tidak valid harus ditolak
def test_invalid_phone_format(client, master_data):
    payload = buat_data_mahasiswa(master_data)

    payload["phone"] = "08123ABC890"

    response = client.post(
        "/api/pmb/register",
        json=payload
    )

    assert response.status_code == 422



# TEST 5: Persetujuan menghasilkan NIM otomatis
def test_approve_generate_nim(client, master_data):
    payload = buat_data_mahasiswa(
        master_data,
        email="approve@example.com"
    )

    # Mendaftarkan mahasiswa
    register = client.post(
        "/api/pmb/register",
        json=payload
    )

    assert register.status_code == 201

    mahasiswa_id = register.json()["id"]

    # Menyetujui mahasiswa
    response = client.put(
        f"/api/pmb/approve/{mahasiswa_id}"
    )

    assert response.status_code == 200

    data = response.json()

    expected_nim = f"{datetime.now().year}001-0001"

    assert data["status"] == "approved"
    assert data["nim"] == expected_nim
    assert data["approved_at"] is not None


# TEST 6: Generator NIM berjalan berurutan
def test_nim_generator_sequential(client, master_data):

    # Mendaftarkan mahasiswa pertama
    mahasiswa_pertama = client.post(
        "/api/pmb/register",
        json=buat_data_mahasiswa(
            master_data,
            email="pertama@example.com"
        )
    )

    # Mendaftarkan mahasiswa kedua
    mahasiswa_kedua = client.post(
        "/api/pmb/register",
        json=buat_data_mahasiswa(
            master_data,
            email="kedua@example.com"
        )
    )

    assert mahasiswa_pertama.status_code == 201
    assert mahasiswa_kedua.status_code == 201

    id_pertama = mahasiswa_pertama.json()["id"]
    id_kedua = mahasiswa_kedua.json()["id"]

    # Menyetujui mahasiswa pertama
    approve_pertama = client.put(
        f"/api/pmb/approve/{id_pertama}"
    )

    # Menyetujui mahasiswa kedua
    approve_kedua = client.put(
        f"/api/pmb/approve/{id_kedua}"
    )

    nim_pertama = approve_pertama.json()["nim"]
    nim_kedua = approve_kedua.json()["nim"]

    assert approve_pertama.status_code == 200
    assert approve_kedua.status_code == 200

    assert nim_pertama.endswith("-0001")
    assert nim_kedua.endswith("-0002")


# TEST 7: Persetujuan dua kali tidak mengubah NIM
def test_approve_idempotent(client, master_data):

    register = client.post(
        "/api/pmb/register",
        json=buat_data_mahasiswa(
            master_data,
            email="idempotent@example.com"
        )
    )

    mahasiswa_id = register.json()["id"]

    # Persetujuan pertama
    response_pertama = client.put(
        f"/api/pmb/approve/{mahasiswa_id}"
    )

    nim_pertama = response_pertama.json()["nim"]

    # Persetujuan kedua
    response_kedua = client.put(
        f"/api/pmb/approve/{mahasiswa_id}"
    )

    nim_kedua = response_kedua.json()["nim"]

    assert response_pertama.status_code == 200
    assert response_kedua.status_code == 200

    assert nim_pertama == nim_kedua


# TEST 8: Persetujuan ID yang tidak ditemukan
def test_approve_invalid_id(client):

    response = client.put(
        "/api/pmb/approve/9999"
    )

    assert response.status_code == 404


# TEST 9: Pendaftar yang ditolak tidak bisa disetujui
def test_approve_rejected_student(
    client,
    master_data,
    test_session_factory
):

    register = client.post(
        "/api/pmb/register",
        json=buat_data_mahasiswa(
            master_data,
            email="rejected@example.com"
        )
    )

    mahasiswa_id = register.json()["id"]

    # Mengubah status mahasiswa menjadi rejected
    db = test_session_factory()

    try:
        mahasiswa = db.get(
            CalonMahasiswa,
            mahasiswa_id
        )

        mahasiswa.status = "rejected"
        db.commit()

    finally:
        db.close()

    # Mencoba menyetujui mahasiswa yang ditolak
    response = client.put(
        f"/api/pmb/approve/{mahasiswa_id}"
    )

    assert response.status_code == 400

    assert response.json()["detail"] == (
        "Pendaftaran yang ditolak tidak dapat disetujui"
    )


# TEST 10: Pengecekan status mahasiswa berhasil
def test_status_success(client, master_data):
    register = client.post(
        "/api/pmb/register",
        json=buat_data_mahasiswa(
            master_data,
            email="status@example.com"
        )
    )

    mahasiswa_id = register.json()["id"]

    response = client.get(
        f"/api/pmb/status/{mahasiswa_id}"
    )

    assert response.status_code == 200
    assert response.json()["status"] == "pending"


# TEST 11: Pengecekan ID mahasiswa tidak ditemukan
def test_status_not_found(client):
    response = client.get("/api/pmb/status/9999")

    assert response.status_code == 404


# TEST 12: Program studi tidak ditemukan
def test_register_invalid_program(client, master_data):
    payload = buat_data_mahasiswa(master_data)
    payload["program_studi_id"] = 9999

    response = client.post(
        "/api/pmb/register",
        json=payload
    )

    assert response.status_code == 404


# TEST 13: Jalur masuk tidak ditemukan
def test_register_invalid_path(client, master_data):
    payload = buat_data_mahasiswa(master_data)
    payload["jalur_masuk_id"] = 9999

    response = client.post(
        "/api/pmb/register",
        json=payload
    )

    assert response.status_code == 404


# TEST 14: Statistik pendaftar
def test_pmb_stats(client, master_data, test_session_factory):

    # Membuat tiga mahasiswa
    emails = [
        "pending@example.com",
        "approved@example.com",
        "rejected@example.com"
    ]

    mahasiswa_ids = []

    for email in emails:
        response = client.post(
            "/api/pmb/register",
            json=buat_data_mahasiswa(master_data, email)
        )

        assert response.status_code == 201
        mahasiswa_ids.append(response.json()["id"])

    # Menyetujui mahasiswa kedua
    client.put(
        f"/api/pmb/approve/{mahasiswa_ids[1]}"
    )

    # Mengubah status mahasiswa ketiga menjadi rejected
    db = test_session_factory()

    try:
        mahasiswa = db.get(
            CalonMahasiswa,
            mahasiswa_ids[2]
        )

        mahasiswa.status = "rejected"
        db.commit()

    finally:
        db.close()

    # Mengambil statistik
    response = client.get("/api/pmb/stats")

    assert response.status_code == 200

    data = response.json()

    assert data["total_pendaftar"] == 3
    assert data["pending"] == 1
    assert data["approved"] == 1
    assert data["rejected"] == 1


# TEST 15: Memastikan koneksi database ditutup
def test_get_db_lifecycle():
    generator = get_db()

    db = next(generator)

    assert db is not None

    with pytest.raises(StopIteration):
        next(generator)


# TEST 16: Validasi tahun generator NIM
def test_nim_invalid_year(db_session):

    with pytest.raises(ValueError, match="Tahun"):
        generate_nim(
            tahun=999,
            kode_prodi="001",
            db=db_session
        )


# TEST 17: Validasi kode program studi generator NIM
def test_nim_invalid_program_code(db_session):

    with pytest.raises(ValueError, match="Kode program studi"):
        generate_nim(
            tahun=datetime.now().year,
            kode_prodi="01",
            db=db_session
        )


# TEST 18: Batas maksimum nomor urut NIM
def test_nim_maximum_sequence(db_session):

    tahun = datetime.now().year

    program = ProgramStudi(
        kode="001",
        nama="Teknik Informatika",
        fakultas="Teknik"
    )

    jalur = JalurMasuk(nama="SNBP")

    db_session.add_all([program, jalur])
    db_session.flush()

    mahasiswa = CalonMahasiswa(
        nama_lengkap="Mahasiswa Terakhir",
        email="terakhir@example.com",
        phone="081234567890",
        tanggal_lahir=date(2005, 5, 20),
        alamat="Jakarta Selatan",
        program_studi_id=program.id,
        jalur_masuk_id=jalur.id,
        status="approved",
        nim=f"{tahun}001-9999",
        approved_at=datetime.now()
    )

    db_session.add(mahasiswa)
    db_session.commit()

    with pytest.raises(ValueError, match="batas maksimum"):
        generate_nim(
            tahun=tahun,
            kode_prodi="001",
            db=db_session
        )


# TEST 19: Seed data master dan memastikan tidak duplikat
def test_seed_master_data_idempotent(
    monkeypatch,
    test_session_factory
):

    # Menggunakan database sementara
    monkeypatch.setattr(
        seed,
        "SessionLocal",
        test_session_factory
    )

    # Menjalankan seed pertama kali
    seed.seed_master_data()

    db = test_session_factory()

    try:
        assert db.query(ProgramStudi).count() == 3
        assert db.query(JalurMasuk).count() == 3

    finally:
        db.close()

    # Menjalankan seed untuk kedua kalinya
    seed.seed_master_data()

    db = test_session_factory()

    try:
        assert db.query(ProgramStudi).count() == 3
        assert db.query(JalurMasuk).count() == 3

    finally:
        db.close()
