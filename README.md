# Sistem Penerimaan Mahasiswa Baru (PMB)

## Deskripsi Proyek

Sistem Penerimaan Mahasiswa Baru (PMB) merupakan aplikasi berbasis web yang dikembangkan menggunakan Python dan FastAPI. Aplikasi ini bertujuan untuk membantu proses pendaftaran calon mahasiswa, pengecekan status pendaftaran, persetujuan pendaftaran, serta melihat statistik pendaftar.

Proyek ini dibuat sebagai bagian dari tugas perkuliahan.

## Teknologi yang Digunakan

- **Python** – Bahasa pemrograman utama.
- **FastAPI** – Framework untuk membangun REST API.
- **SQLite** – Database untuk menyimpan data.
- **SQLAlchemy** – ORM untuk mengelola database.
- **Alembic** – Mengelola migrasi database.
- **Pydantic** – Validasi data.
- **Pytest** – Pengujian aplikasi.
- **Pytest-Cov** – Mengukur test coverage.

## Fitur Aplikasi

1. Registrasi calon mahasiswa baru.
2. Pembuatan NIM secara otomatis.
3. Pengecekan status pendaftaran.
4. Persetujuan pendaftaran calon mahasiswa.
5. Melihat statistik pendaftaran.
6. Validasi data dan penanganan pendaftaran dengan email duplikat.

## Struktur Folder

```text
PMB - Project/
│
├── alembic/
│   └── versions/
│
├── app/
│   ├── models/
│   ├── routers/
│   ├── schemas/
│   ├── services/
│   ├── database.py
│   ├── main.py
│   └── seed.py
│
├── docs/
│   └── AI_USAGE_LOG.md
│
├── reports/
│   ├── coverage-report.txt
│   └── pytest-report.txt
│
├── tests/
│   ├── conftest.py
│   └── test_pmb.py
│
├── .gitignore
├── alembic.ini
├── requirements.txt
└── README.md
```

## Persyaratan

Pastikan perangkat sudah memiliki:

- Python
- Git
- Visual Studio Code

## Instalasi dan Menjalankan Aplikasi

### 1. Clone Repository

```bash
git clone https://github.com/JIeLS-hash/sistem-pmb.git
```

### 2. Masuk ke Folder Proyek

```bash
cd sistem-pmb
```

### 3. Membuat Virtual Environment

```bash
py -m venv .venv
```

### 4. Mengaktifkan Virtual Environment

```powershell
.\.venv\Scripts\Activate.ps1
```

### 5. Menginstal Library

```bash
python -m pip install -r requirements.txt
```

### 6. Menjalankan Migrasi Database

```bash
python -m alembic upgrade head
```

### 7. Menjalankan Aplikasi

```bash
python -m uvicorn app.main:app --reload
```

Aplikasi dapat diakses melalui:

- **API:** http://127.0.0.1:8000
- **Swagger UI:** http://127.0.0.1:8000/docs

## Daftar Endpoint API

| Method | Endpoint | Fungsi |
|---|---|---|
| POST | `/api/pmb/register` | Mendaftarkan calon mahasiswa |
| GET | `/api/pmb/status/{id}` | Mengecek status pendaftaran |
| PUT | `/api/pmb/approve/{id}` | Menyetujui pendaftaran |
| GET | `/api/pmb/stats` | Melihat statistik pendaftar |

## Pengujian Aplikasi

Pengujian dilakukan menggunakan Pytest.

Jalankan perintah berikut untuk menjalankan seluruh pengujian:

```bash
python -m pytest -v
```

Untuk melihat hasil test coverage:

```bash
python -m pytest --cov=app --cov-report=term-missing
```

### Hasil Pengujian

- Total pengujian: **19**
- Pengujian berhasil: **19**
- Pengujian gagal: **0**
- Test coverage: **93%**

## Dokumentasi Penggunaan AI

Dokumentasi penggunaan AI selama proses pengembangan proyek tersedia pada:

`docs/AI_USAGE_LOG.md`

## Repository

GitHub: https://github.com/JIeLS-hash/sistem-pmb

---

**Sistem Penerimaan Mahasiswa Baru (PMB)**  
Dikembangkan menggunakan Python dan FastAPI.