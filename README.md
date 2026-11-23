## Arsitektur & Perancangan UML Sistem Akademik 

Rancangan arsitektur sistem informasi akademik (`SEVIMA-Mini`) terdokumentasi dalam format Mermaid dan PDF siap cetak:
- **Class Diagram:** [`diagrams/class-diagram.mmd`](diagrams/class-diagram.mmd) — Hierarki `User` (`CalonMahasiswa`, `Mahasiswa`, `Dosen`, `Admin`) dan entitas inti (`Payment`, `Course`, `KRS`, `Enrollment`, `Schedule`, `Grade`)[cite: 27, 31].
- **Use Case Diagram:** [`diagrams/usecase-diagram.mmd`](diagrams/usecase-diagram.mmd) — Pemetaan 5 aktor dan 11 *use case* dengan relasi `<<include>>` dan `<<extend>>`[cite: 27, 31].
- **Sequence Diagram:** [`diagrams/sequence-pmb.mmd`](diagrams/sequence-pmb.mmd), [`diagrams/sequence-krs.mmd`](diagrams/sequence-krs.mmd), dan [`docs/SEQUENCE_DIAGRAM_OBSERVER.md`](docs/SEQUENCE_DIAGRAM_OBSERVER.md)[cite: 27, 31].
- **Dokumentasi Prompt AI:** [`prompts/uml-prompts.md`](prompts/uml-prompts.md) — 6 *prompt* terbaik beserta perbandingan hasil AI vs revisi manual[cite: 27, 31].
- **Dokumen PDF Final:** [`docs/ADR-architecture-decisions.pdf`](docs/ADR-architecture-decisions.pdf) & [`docs/Final-UML-diagram.pdf`](docs/Final-UML-diagram.pdf)[cite: 31].

---


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
5. Penolakan pendaftaran calon mahasiswa.
6. Melihat statistik pendaftaran.
7. Validasi data dan penanganan pendaftaran dengan email duplikat.

## Struktur Folder

```text
PMB - Project/
│
├── .github/
│   └── pull_request_template.md
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
| PUT | `/api/pmb/reject/{id}` | Menolak pendaftaran |
| GET | `/api/pmb/stats` | Melihat statistik pendaftar |

## Format NIM Otomatis

NIM dibuat secara otomatis ketika admin menyetujui pendaftaran (`PUT /api/pmb/approve/{id}`) dengan format:

`[Tahun: 4 digit][Kode Prodi: 3 karakter]-[Nomor Urut: 4 digit]`

- **Contoh:** `2026001-0001` (`2026` = tahun pendaftaran, `001` = Teknik Informatika, `0001` = pendaftar pertama yang disetujui).
- **Idempotent & Thread-Safe:** Pemanggilan berulang pada pendaftar yang sama tidak menghasilkan NIM baru, dan transaksi dikunci (`BEGIN IMMEDIATE` + constraint `UNIQUE`) untuk mencegah duplikasi akibat *race condition*.

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

- Total pengujian: **21**
- Pengujian berhasil: **21**
- Pengujian gagal: **0**
- Test coverage: **94%**

## Dokumentasi Penggunaan AI

Dokumentasi penggunaan AI selama proses pengembangan proyek tersedia pada:

`docs/AI_USAGE_LOG.md`

## Repository

GitHub: https://github.com/JIeLS-hash/sistem-pmb

---

**Sistem Penerimaan Mahasiswa Baru (PMB)**  
Dikembangkan menggunakan Python dan FastAPI.

---

## Modul 2: Sistem Pengisian Kartu Rencana Studi (KRS)

Modul lanjutan dari sistem PMB yang memungkinkan mahasiswa ber-NIM menyusun rencana studi per semester dengan validasi aturan akademik dan alur persetujuan Dosen PA[cite: 3, 5].

### Fitur & Arsitektur Utama
- **Skema Database Terindeks:** Tabel `matakuliah`, `krs`, `krs_detail`, `prerequisite`, `skala_nilai`, dan `riwayat_nilai` dikelola melalui migrasi Alembic[cite: 1, 4, 5].
- **Rantai Validasi (*Chain of Responsibility*):** Eksekusi *fail-fast* pada `app/services/krs_validator.py` untuk mengecek:
  1. Tidak ada pengambilan mata kuliah ganda (*double enrollment*)[cite: 5, 6].
  2. Seluruh prasyarat mata kuliah lulus dengan nilai minimal **C**[cite: 5, 6].
  3. Tidak ada bentrok jadwal pada hari dan irisan jam kuliah yang sama[cite: 4, 5, 6].
  4. Total beban studi maksimal **24 SKS** per semester[cite: 5, 6].
  *(Keputusan desain selengkapnya tercatat di `docs/ADR_001_VALIDATION_CHAIN.md`[cite: 4]).*
- **Manajemen Transaksi & *State Machine*:** `KRSManager` (`app/services/krs_manager.py`) menggunakan *row locking* (`FOR UPDATE`) serta menegakkan transisi status ketat: `DRAFT` → `SUBMITTED` → `APPROVED` / `REVISION`[cite: 3, 5, 6].

### Menjalankan Seed Data & Bukti Optimasi Query
```bash
# 1. Jalankan migrasi database terbaru
alembic upgrade head

# 2. Isi data dummy mata kuliah, prasyarat, skala nilai, dan riwayat nilai
python -m app.seed_krs

# 3. Cek hasil query prasyarat (NOT EXISTS) & rencana eksekusi index (EXPLAIN)
python -m docs.explain_prerequisite
```
---

## Modul 3: Sistem Penjadwalan Kuliah & Deteksi Bentrok 3 Dimensi (Minggu 7)

Modul manajemen jadwal kuliah dan ruangan yang mendeteksi bentrok 3 dimensi (`hari × waktu × ruangan × dosen`), memeriksa kapasitas ruangan, dan menyediakan laporan bentrok untuk admin.

### Fitur & Arsitektur Utama
- **Model Domain & Migrasi Batch:** Entitas `Ruangan`, `Dosen`, `Kelas`, dan `Jadwal` (dengan tipe `Time`, *check constraint*, dan indeks komposit `ix_jadwal_ruang` serta `ix_jadwal_dosen`), plus relasi `krs_detail.kelas_id`.
- **Deteksi Bentrok 3 Dimensi (*Sweep-Line*):** `detect_schedule_conflict` ($O(N \log N + K)$) pada `app/services/conflict_detector.py` menggunakan interval setengah terbuka `[jam_mulai, jam_selesai)` untuk mendeteksi `room_conflict` dan `lecturer_conflict` tanpa salah menandai kelas yang berurutan tanpa jeda. *(Keputusan desain tercatat di `docs/ADR_002_CONFLICT_DETECTION.md`).*
- **Layanan Penjadwalan (`SchedulingService`):** Operasi CRUD jadwal pada `app/services/scheduling_service.py` dengan *row locking* (`FOR UPDATE`), pengecekan kapasitas ruangan terhadap kuota kelas maupun jumlah mahasiswa terdaftar, serta respons HTTP `409 Conflict` lengkap dengan rincian jadwal yang berbenturan.

### Menjalankan Seed Data & Cek Detektor Bentrok
```bash
# 1. Jalankan migrasi database terbaru
alembic upgrade head

# 2. Isi data dummy (12 ruangan, 16 dosen, 21 kelas, 42 jadwal)
python -m app.seed_jadwal

# 3. Verifikasi deteksi bentrok (sweep-line vs naive)
python -m app.services.conflict_detector
```

---

## Modul 4: Observer Pattern, Outbox, & AI Rescheduling (Minggu 8)

Lanjutan modul penjadwalan yang membuat perubahan jadwal bersifat reaktif, aman secara transaksional, dan dilengkapi asisten penjadwalan ulang berbantuan AI.

### Fitur & Arsitektur Utama
- **Observer Pattern & Isolasi Error (`app/services/observer.py`):** `ScheduleSubject` menyiarkan `ScheduleEvent` ke `StudentObserver` (`PUSH` & `EMAIL`), `LecturerObserver` (`SMS` & `EMAIL`), dan `AdminObserver` (`EMAIL` audit).
- **Transactional Outbox (`app/services/outbox_dispatcher.py`):** Event disimpan ke tabel `outbox_events` dalam transaksi DB yang sama dan dikirimkan **setelah `db.commit()`** menggunakan *idempotency key* (`event_id`).
- **Invalidasi KRS Otomatis (`app/services/krs_invalidator.py`):** Saat jadwal kelas berubah atau dihapus, KRS berstatus `SUBMITTED`/`APPROVED` yang terdampak otomatis dikembalikan ke `REVISION` oleh `Actor.SISTEM`.
- **AI Rescheduling & Ekspor Kalender (`app/services/ai_rescheduler.py`, `app/services/ics_exporter.py`):** Menyusun *Prompt Step 3*, menyaring kandidat saran AI melalui validator deterministik `saring_saran`, dan mendukung unduhan kalender `.ics` (RFC 5545).
- **Conflict Resolver UI:** Dashboard interaktif admin dapat diakses melalui `GET /api/jadwal/dashboard`. *(Diagram alur tersedia di `docs/SEQUENCE_DIAGRAM_OBSERVER.md`).*

### Endpoint Tambahan Minggu 8
| Method | Endpoint | Deskripsi |
| :--- | :--- | :--- |
| `GET` | `/api/jadwal/dashboard` | Halaman web **Conflict Resolver UI** untuk admin akademik |
| `POST` | `/api/jadwal/{jadwal_id}/suggest-reschedule` | Menghasilkan saran slot pengganti bebas bentrok yang telah disaring validator |
| `GET` | `/api/jadwal/export/ics` | Mengekspor jadwal kuliah ke format standar iCalendar (`.ics`) |
| `GET` | `/api/jadwal/notifications` | Menampilkan riwayat log notifikasi lintas kanal (`EMAIL`, `SMS`, `PUSH`) |