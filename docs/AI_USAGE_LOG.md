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

---

## Modul Jadwal & Ruangan (Minggu 7)

### 1. Riwayat Prompt & Revisi Kode
| Tahap | Ringkasan Prompt ke AI | Hasil & Revisi yang Dilakukan |
| :--- | :--- | :--- |
| **Model & Migrasi Alembic** | Merancang model SQLAlchemy 2.0 (`Ruangan`, `Dosen`, `Kelas`, `Jadwal`) dan kolom relasi `krs_detail.kelas_id` dengan tipe `Time` serta *check constraint*. | Menambahkan nama *foreign key* eksplisit (`fk_krs_detail_kelas_id`) dan mengaktifkan `render_as_batch=True` di `alembic/env.py` agar migrasi `ALTER TABLE` pada SQLite berjalan lancar. |
| **Seed Data Jadwal** | Membuat skrip *seed data* idempotent untuk $\ge 10$ ruangan, $\ge 15$ dosen, dan $\ge 40$ jadwal termasuk beberapa skenario bentrok yang disengaja. | Memperbaiki pengecekan `MataKuliah` menggunakan `select(MataKuliah).where(MataKuliah.kode_mk == kode_mk)` menggantikan `db.get()` karena `kode_mk` merupakan kolom `UNIQUE` non-PK, menghasilkan 12 ruangan, 16 dosen, 21 kelas, dan 42 jadwal. |
| **Conflict Detector & ADR** | Mengimplementasikan `detect_naive` ($O(N^2)$) dan `detect_schedule_conflict` ($O(N \log N + K)$) berbasis *sweep-line* dengan interval setengah terbuka `[jam_mulai, jam_selesai)`. | Mendokumentasikan perbandingan kompleksitas dan pertimbangan struktur data (*Sweep-Line* vs *Interval Tree* vs *Naive*) di `docs/ADR_002_CONFLICT_DETECTION.md` serta memverifikasi deteksi 4 bentrok awal. |
| **SchedulingService & API** | Membuat layanan CRUD jadwal dengan *row locking* (`with_for_update`), *capacity check*, dan 5 endpoint FastAPI termasuk `GET /api/jadwal/conflicts`. | Menangani kode status HTTP `201`, `204`, `404`, `409` (beserta rincian objek bentrok), dan `422` pada `app/routers/jadwal.py`. |
| **Testing & Hypothesis** | Menyusun *unit/integration test*, 2 *property-based test* (`hypothesis`), dan *differential test* antara `detect_schedule_conflict` dan `detect_naive`. | Menggunakan database SQLite in-memory terisolasi (`StaticPool`) dengan `dependency_overrides` di `tests/test_jadwal.py` sehingga seluruh pengujian PMB, KRS, dan Jadwal lulus tanpa saling mengganggu. |

### 2. Refleksi OPAR (Observe, Plan, Act, Reflect)
- **Observe:** Pada modul KRS sebelumnya, jadwal masih menempel langsung pada tabel `matakuliah` sehingga belum mampu memodelkan kelas paralel, kapasitas ruangan, maupun bentrok dosen yang mengajar di dua ruangan bersamaan.
- **Plan:** Memisahkan entitas `Ruangan`, `Dosen`, `Kelas`, dan `Jadwal`, menyusun detektor bentrok 3 dimensi (`hari × waktu × ruangan × dosen`) berbasis *sweep-line*, serta membungkus aturan *hard constraint* ke dalam `SchedulingService` sebelum disimpan ke database.
- **Act:** Mengimplementasikan migrasi *batch* Alembic, skrip *seed* 42 jadwal, modul `conflict_detector.py` beserta ADR-nya, endpoint REST API `/api/jadwal`, serta pengujian berbasis properti dan *differential testing* dengan Hypothesis.
- **Reflect:** Pengujian diferensial (*differential testing*) antara fungsi teroptimasi (`sweep-line`) dan fungsi referensi sederhana (`detect_naive`) sangat membantu memastikan tidak ada *edge case* irisan waktu (seperti jadwal berurutan tepat di menit yang sama) yang terlewat akibat logika pengurutan.

---

## Observer Pattern, Outbox, & AI Rescheduling (Minggu 8)

### 1. Riwayat Prompt & Revisi Kode
| Tahap | Ringkasan Prompt ke AI | Hasil & Revisi yang Dilakukan |
| :--- | :--- | :--- |
| **Observer & Kanal Log** | Mengimplementasikan *Observer Pattern* (`ScheduleEvent`, `ScheduleSubject`, `StudentObserver`, `LecturerObserver`, `AdminObserver`) dengan kanal log `EMAIL`, `SMS`, dan `PUSH`. | Menambahkan blok `try/except` per *observer* pada salinan daftar `list(self._observers)` di `app/services/observer.py` agar kegagalan satu *observer* tidak menghentikan pengiriman ke *observer* lain. |
| **Outbox & Invalidasi KRS** | Membuat tabel `outbox_events`, `OutboxDispatcher` (pengiriman setelah `commit` + *idempotency key*), serta `KRSInvalidator` untuk transisi `Actor.SISTEM -> REVISION`. | Mengintegrasikan `KRSInvalidator` dan `OutboxDispatcher.enqueue_event()` sebelum `db.commit()` di `SchedulingService`, lalu memanggil `OutboxDispatcher.dispatch_pending()` setelah `commit` berhasil. |
| **AI Rescheduling & .ics** | Menyusun **Prompt Step 3** dan saringan validator `saring_saran` untuk memfilter kandidat jadwal alternatif dari AI, serta ekspor kalender `.ics`. | Membangun `app/services/ai_rescheduler.py` dan `app/services/ics_exporter.py` (RFC 5545) yang menolak kandidat dengan jam tidak valid, ruangan tidak ada, kapasitas kurang, atau masih bentrok 3D. |
| **Conflict Resolver UI** | Membuat halaman antarmuka admin interaktif untuk melihat bentrok, meminta saran AI, menerapkan jadwal, dan memantau log notifikasi. | Menambahkan `app/templates/conflict_resolver.html` dan endpoint `GET /api/jadwal/dashboard` di `app/routers/jadwal.py`. |
| **Pengujian Minggu 8** | Menyusun *test* untuk *observer* 3 kanal, *outbox* pasca-*commit*, 42 transisi status KRS ilegal, saringan saran AI, ekspor `.ics`, dan *dashboard*. | Menambahkan `tests/test_observer_reschedule.py` yang menguji seluruh 48 kombinasi matriks transisi status KRS (6 valid dan 42 ilegal). |

### 2. Refleksi OPAR (Observe, Plan, Act, Reflect)
- **Observe:** Mengirim notifikasi langsung di dalam `SchedulingService` sebelum `db.commit()` menimbulkan *tight coupling* (melanggar *Open-Closed Principle*) serta risiko mengirim notifikasi palsu apabila transaksi database gagal dan mengalami *rollback*.
- **Plan:** Memisahkan pengiriman notifikasi menggunakan *Observer Pattern*, menyimpan *event* ke tabel `outbox_events` dan mengembalikan KRS terdampak ke `REVISION` dalam satu transaksi database yang sama, serta menyaring saran AI melalui validator deterministik (`saring_saran`).
- **Act:** Mengimplementasikan `observer.py`, `outbox_dispatcher.py`, `krs_invalidator.py`, `ai_rescheduler.py`, `ics_exporter.py`, halaman *dashboard* `conflict_resolver.html`, UML *Sequence Diagram*, dan pengujian menyeluruh.
- **Reflect:** Pola *Transactional Outbox* dipadukan dengan *idempotency key* (`event_id`) memastikan notifikasi hanya terkirim jika perubahan jadwal dan status KRS benar-benar sah tersimpan di database, sementara `saring_saran` mencegah halusinasi slot jadwal dari AI masuk ke produksi.