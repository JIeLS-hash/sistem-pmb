# ADR-001: Strategi Eksekusi dan Urutan Rantai Validasi KRS

- **Status:** Accepted
- **Tanggal:** 2026-11-20
- **Konteks:** Modul Pengisian Kartu Rencana Studi (KRS) — `app/services/krs_validator.py`

## 1. Konteks Masalah
Sistem KRS harus menegakkan empat aturan bisnis sebelum mata kuliah dapat ditambahkan ke dalam rancangan studi mahasiswa:
1. Tidak ada pengambilan mata kuliah ganda (*double enrollment*).
2. Seluruh mata kuliah prasyarat telah lulus dengan nilai minimal C.
3. Tidak terdapat irisan jadwal kuliah pada hari dan rentang jam yang sama.
4. Akumulasi SKS dalam satu semester tidak melebihi batas maksimal 24 SKS.

Terdapat dua keputusan arsitektur utama yang perlu ditetapkan pada pola *Chain of Responsibility*:
1. Apakah rantai validasi langsung berhenti saat menemukan error pertama (*fail-fast*) atau menjalankan seluruh validator untuk mengumpulkan semua error sekaligus?
2. Bagaimana urutan eksekusi keempat validator tersebut?

## 2. Keputusan Desain

### A. Strategi *Fail-Fast* (Berhenti Saat Ada Kegagalan)
Rantai validasi dirancang untuk **langsung berhenti dan mengembalikan `ValidationResult(is_valid=False, message=...)` pada kegagalan pertama**.

**Alasan:**
- **Efisiensi I/O Database:** Jika mata kuliah sudah duplikat di memori keranjang KRS, sistem tidak perlu mengeksekusi *query* SQL pengecekan prasyarat ke database.
- **Kejelasan Umpan Balik Pengguna:** Mahasiswa mendapatkan satu pesan kesalahan yang spesifik dan langsung dapat ditindaklanjuti (contoh: `"Prasyarat tidak terpenuhi: Kalkulus I"`) tanpa kebingungan akibat tumpukan error sekunder.
- **Kesesuaian Spesifikasi:** Mengikuti prinsip *Chain of Responsibility* di mana rantai pemrosesan berhenti segera setelah aturan dilanggar.

### B. Urutan Rantai Validasi
Urutan validator ditetapkan sebagai berikut:
`DuplicateValidator` -> `PrerequisiteValidator` -> `ConflictValidator` -> `SKSValidator`

**Alasan:**
1. **`DuplicateValidator` (Pertama):** Pengecekan paling ringan karena cukup membandingkan kode mata kuliah yang sudah ada di memori tanpa perlu menghitung SKS maupun melakukan *query* prasyarat.
2. **`PrerequisiteValidator` (Kedua):** Memverifikasi kelayakan akademik terlebih dahulu. Jika mahasiswa memang belum berhak mengambil mata kuliah tersebut, sistem langsung menolaknya sebelum memeriksa bentrok jadwal atau kuota SKS.
3. **`ConflictValidator` (Ketiga):** Memastikan slot waktu pada hari dan irisan jam tidak bertabrakan sebelum menghitung akumulasi beban SKS.
4. **`SKSValidator` (Keempat):** Ditempatkan di akhir karena bersifat agregasi keseluruhan keranjang KRS setelah mata kuliah dipastikan sah secara duplikasi, prasyarat, dan jadwal.

## 3. Konsekuensi
- **Positif:** Latensi validasi tetap rendah dan setiap kelas *validator* terisolasi dengan tanggung jawab tunggal (*Single Responsibility Principle*), sehingga mudah ditambah atau diubah tanpa memodifikasi kelas lain.
- **Negatif:** Jika satu mata kuliah melanggar dua aturan sekaligus (misalnya prasyarat belum lulus dan jadwalnya bentrok), error kedua baru akan muncul setelah pelanggaran pertama diperbaiki.