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