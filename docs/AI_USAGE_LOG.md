# AI Usage Log
## Proyek Sistem Penerimaan Mahasiswa Baru (PMB)

### 1. Informasi Proyek
- **Nama Proyek:** Sistem Penerimaan Mahasiswa Baru (PMB)
- **Bahasa Pemrograman:** Python
- **Framework:** FastAPI
- **Database:** SQLite
- **Tools:** Visual Studio Code

### 2. Penggunaan AI
Dalam proses pengerjaan proyek ini, AI digunakan sebagai alat bantu pembelajaran dan pengembangan program.

AI membantu dalam beberapa hal berikut:
1. Memberikan penjelasan mengenai struktur proyek dan pembagian folder.
2. Membantu memahami penggunaan Python dan framework FastAPI.
3. Memberikan panduan dalam pembuatan database dan model.
4. Membantu memahami pembuatan API endpoints.
5. Membantu proses pembuatan dan perbaikan unit test.
6. Membantu menganalisis pesan error selama proses pengembangan.

### 3. Pengujian Program
Pengujian dilakukan menggunakan library Pytest dan Pytest-Cov.

Hasil pengujian terakhir:
- Total pengujian: 21
- Pengujian berhasil: 21
- Pengujian gagal: 0
- Test coverage: 94%

### 4. Peran AI dan Pengembang
AI digunakan sebagai pendamping untuk memberikan penjelasan, saran, dan bantuan teknis.

Pengembang tetap bertanggung jawab untuk:
- Memahami kode program.
- Menjalankan dan menguji program.
- Memeriksa hasil pengujian.
- Memperbaiki kode berdasarkan hasil pemeriksaan.

### 5. Kesimpulan
Penggunaan AI membantu proses pembelajaran dan pengembangan Sistem Penerimaan Mahasiswa Baru (PMB), terutama dalam memahami struktur program, pembuatan API, pengujian, dan penyelesaian masalah teknis.

### 6. Contoh Prompt Terbaik & Analisis OPAR
- **Prompt Terbaik:** *"Buat fungsi generate_nim dengan format YYYY[KODE]-XXXX di SQLAlchemy 2.0 yang idempotent dan aman dari race condition pada database SQLite."*
- **Observation (Observasi):** Dua request persetujuan yang masuk bersamaan berpotensi membaca nomor urut terakhir yang sama sebelum data disimpan.
- **Problem (Masalah):** Tanpa penguncian transaksi, *race condition* dapat memicu duplikasi NIM.
- **Action (Tindakan):** Menerapkan penguncian transaksi SQLite (`BEGIN IMMEDIATE`), menambahkan constraint `UNIQUE` pada kolom `nim`, serta pengecekan *idempotent* sebelum generate NIM.
- **Result (Hasil):** Nomor NIM selalu unik, berurutan, dan seluruh 21 pengujian `pytest` berhasil dijalankan.

---

## Modul KRS (Kartu Rencana Studi) — Minggu 5 & 6

### 1. Riwayat Prompt & Revisi Kode
| Tahap | Ringkasan Prompt ke AI | Hasil & Revisi yang Dilakukan |
| :--- | :--- | :--- |
| **Database & Query** | Merancang model SQLAlchemy 2.0 untuk `matakuliah`, `krs`, `krs_detail`, `prerequisite`, `skala_nilai`, dan `riwayat_nilai` beserta query `NOT EXISTS`. | Menghubungkan relasi `nim` dari tabel `calon_mahasiswa`, menambahkan index komposit (`ix_riwayat_nilai_lookup`, `ix_matakuliah_jadwal`), serta memverifikasi penggunaan index lewat `EXPLAIN QUERY PLAN`. |
| **Validation Chain** | Mengimplementasikan pola *Chain of Responsibility* untuk 4 validator KRS (`Duplicate`, `Prerequisite`, `Conflict`, `SKS <= 24`) dan dokumen ADR. | Menyusun eksekusi *fail-fast* pada `krs_validator.py` dan mendokumentasikan alasan urutan rantai validasi pada `docs/ADR_001_VALIDATION_CHAIN.md`. |
| **KRS Manager & State Machine** | Membuat service `KRSManager` dengan manajemen transaksi dan *state machine* (`DRAFT -> SUBMITTED -> APPROVED / REVISION`). | Menambahkan `with_for_update()` untuk *row locking* saat perubahan keranjang KRS, mengunci transisi ilegal (seperti `DRAFT -> APPROVED`), dan menghubungkannya ke 8 endpoint API di `app/routers/krs.py`. |
| **Testing & Hypothesis** | Membuat *integration test* API dan *property-based test* `hypothesis` untuk 1.000 kombinasi acak mata kuliah. | Memperbaiki urutan impor `app.models` sebelum `app.main` di `tests/test_krs.py`, menyesuaikan impor `MAX_SKS_PER_SEMESTER`, dan menambahkan `engine.dispose()` agar tidak muncul `ResourceWarning`. |

### 2. Refleksi OPAR (Observe, Plan, Act, Reflect)
- **Observe:** Modul KRS merupakan kelanjutan langsung dari modul PMB bagi mahasiswa yang telah lulus seleksi dan memiliki NIM. Tantangan utamanya adalah menjaga konsistensi aturan akademik (prasyarat nilai minimal C, larangan mata kuliah ganda, deteksi irisan jam kuliah, dan batas maksimal 24 SKS) sekaligus mencegah lompatan status persetujuan KRS.
- **Plan:** Memisahkan tanggung jawab sistem ke dalam tiga lapisan: skema database terindeks dengan migrasi Alembic, rantai validator berbasis pola *Chain of Responsibility* untuk validasi aturan bisnis, serta `KRSManager` untuk mengelola transaksi dan transisi status *state machine*.
- **Act:** Membangun 6 tabel baru beserta skrip *seed data* khusus (`app/seed_krs.py`), menguji rencana eksekusi query prasyarat dengan `EXPLAIN QUERY PLAN`, mengintegrasikan endpoint FastAPI, serta memverifikasi seluruh skenario normal dan *edge case* melalui 27 pengujian otomatis di Pytest dan Hypothesis.
- **Reflect:** Penggunaan pola *Chain of Responsibility* membuat setiap aturan validasi terisolasi dan mudah diuji secara terpisah tanpa menumpuk logika di *router*. Selain itu, *property-based testing* dengan Hypothesis terbukti sangat efektif menguji invarian batas maksimal 24 SKS pada 1.000 kombinasi acak yang sulit dijangkau jika hanya mengandalkan kasus uji manual.