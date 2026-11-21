# ADR 002: Pemilihan Algoritma Deteksi Bentrok Jadwal 3 Dimensi (Sweep-Line vs Interval Tree vs Naive)

- **Status:** Accepted
- **Tanggal:** 2026-11-21
- **Konteks Modul:** Minggu 7 — Modul Jadwal & Ruangan (`app/services/conflict_detector.py`)

## 1. Konteks & Masalah
Sistem penjadwalan kuliah harus mendeteksi dua jenis pelanggaran *hard constraint* secara akurat di tiga dimensi (`hari × waktu × ruangan × dosen`):
1. **Bentrok Ruangan (`room_conflict`):** Dua kelas dijadwalkan pada hari yang sama, irisan waktu yang sama, dan ruangan yang sama.
2. **Bentrok Dosen (`lecturer_conflict`):** Seorang dosen dijadwalkan mengajar dua kelas pada hari yang sama dan irisan waktu yang sama.

Selain itu, dua kelas yang berlangsung berurutan tanpa jeda (misalnya `08:00–10:00` dan `10:00–12:00`) **tidak boleh** dianggap bentrok.

## 2. Keputusan Arsitektur
1. **Representasi Interval Setengah Terbuka `[jam_mulai, jam_selesai)`:**
   Dua jadwal $A = [s_A, e_A)$ dan $B = [s_B, e_B)$ dinyatakan beririsan jika dan hanya jika:
   $$s_A < e_B \land s_B < e_A$$
   Dengan pertidaksamaan tegas (`<`), kelas yang berakhir pukul `10:00` tidak beririsan dengan kelas yang mulai pukul `10:00`.
2. **Algoritma *Sweep-Line* (`detect_schedule_conflict`) untuk Pemindaian Batch:**
   Jadwal dikelompokkan per `hari` lalu diurutkan berdasarkan `jam_mulai`. Garis sapu (*sweep line*) memelihara daftar *active intervals* yang memenuhi `prev.jam_selesai > current.jam_mulai`, sehingga pengecekan ruangan dan dosen hanya dilakukan terhadap jadwal yang benar-benar aktif pada rentang waktu yang sama.
3. **Fungsi Pembanding `detect_naive` untuk *Differential Testing*:**
   Implementasi $O(N^2)$ tetap dipertahankan sebagai *oracle* kebenaran pada *differential test* untuk memastikan `detect_schedule_conflict(S) == detect_naive(S)` pada seluruh kasus uji acak.

## 3. Perbandingan Alternatif
| Kriteria | Naive Pairwise | Sweep-Line (Dipilih) | Interval Tree |
| :--- | :--- | :--- | :--- |
| **Kompleksitas Waktu (Batch)** | $O(N^2)$ | $O(N \log N + K)$ | $O(N \log N + K)$ |
| **Kompleksitas Ruang** | $O(1)$ tambahan | $O(N)$ | $O(N)$ |
| **Kueri Dinamis (1 jadwal baru)** | $O(N)$ | $O(N)$ (atau terindeks SQL) | $O(\log N + k)$ |
| **Kompleksitas Implementasi** | Sangat rendah | Rendah, murni struktur bawaan Python | Tinggi (perlu *self-balancing BST* seperti AVL/Red-Black) |

## 4. Konsekuensi
- **Positif:** Pada skala jadwal satu semester ($N \approx 50\text{–}1.000$ pertemuan per hari), *sweep-line* memangkas perbandingan pasangan hingga >90% dibanding pendekatan naif tanpa ketergantungan pustaka pohon eksternal. Untuk validasi satu jadwal saat `POST/PUT`, database memanfaatkan indeks komposit `ix_jadwal_ruang(hari, ruangan_kode)` dan `ix_jadwal_dosen(hari, dosen_id)`.
- **Trade-off:** Jika sistem berkembang menjadi penjadwalan otomatis real-time berskala puluhan ribu kelas dengan ratusan perubahan per detik di memori, struktur *Augmented Interval Tree* dapat menggantikan *sweep-line* pada lapisan *in-memory solver*.