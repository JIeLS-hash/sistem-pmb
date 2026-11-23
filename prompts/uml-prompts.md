# Dokumentasi Prompt Engineering & Revisi Desain UML (Minggu 1–2)

Dokumen ini mencatat kumpulan *prompt* terbaik yang digunakan untuk menghasilkan rancangan UML Sistem Informasi Akademik (`SEVIMA-Mini`), hasil keluaran awal AI, serta revisi manual yang dilakukan agar sesuai dengan prinsip SOLID dan kebutuhan domain[cite: 26, 27, 30].

---

## Prompt 1: Perancangan Class Diagram Inti & Hierarki User
**Prompt yang Digunakan:**
> "Anda adalah arsitek sistem. Buat class diagram UML untuk sistem akademik dengan komponen berikut: `User` sebagai base class (`Mahasiswa`, `Dosen`, `Admin`, `CalonMahasiswa`), `Course` dengan atribut kode, nama, SKS, prasyarat, `Enrollment` yang menghubungkan Mahasiswa dan Course, `Schedule` dengan hari, jam, ruangan, `Grade` untuk nilai mahasiswa, serta `Payment`. Terapkan prinsip SOLID. Gunakan *composition* untuk relasi kuat dan *aggregation* untuk relasi lemah. Output dalam format Mermaid."[cite: 28]

**Perbandingan Hasil AI vs Revisi Manual:**
- **Hasil Awal AI:** AI menghubungkan `Mahasiswa` langsung ke `Course` menggunakan relasi *many-to-many* tanpa entitas transaksi `KRS`, serta meletakkan seluruh logika validasi dan penjadwalan di dalam class `Admin` (*God Object*)[cite: 30].
- **Revisi Manual:** Memisahkan entitas `KRS` sebagai agregator semester (`Mahasiswa "1" *-- "0..*" KRS` dan `KRS "1" *-- "1..*" Enrollment`), menambahkan *visibility modifier* (`#` untuk atribut *inherited* pada `User`, `-` untuk atribut privat, `+` untuk method publik), serta membedakan *composition* (`*--`) dari *aggregation* (`o--`) pada relasi prasyarat `Course`[cite: 27, 28, 30].

---

## Prompt 2: Audit SOLID & Pencegahan God Object
**Prompt yang Digunakan:**
> "Audit class diagram sistem akademik terhadap prinsip SOLID. Identifikasi potensi pelanggaran *Single Responsibility Principle* (SRP) dan *Dependency Inversion Principle* (DIP), lalu berikan rekomendasi pemisahan service agar tidak terjadi *God Object*."[cite: 30]

**Perbandingan Hasil AI vs Revisi Manual:**
- **Hasil Awal AI:** AI menyarankan pemecahan setiap entitas menjadi *service* terpisah namun masih menimbulkan *circular dependency* antara `Course` dan `Schedule`[cite: 28, 30].
- **Revisi Manual:** Menjadikan `Course` sebagai pemilik jadwal (`Course "1" *-- "1..*" Schedule`) dengan arah dependensi satu arah sehingga tidak ada siklus referensi antar-class[cite: 28].

---

## Prompt 3: Perancangan Use Case Diagram & Relasi Include/Extend
**Prompt yang Digunakan:**
> "Buat use case diagram untuk sistem akademik dengan aktor: `Calon Mahasiswa`, `Mahasiswa`, `Dosen / Dosen PA`, `Admin Akademik`, dan `Sistem PMB & Notifikasi`. Use case utama: registrasi PMB, pembayaran pendaftaran, verifikasi & generate NIM, isi KRS, validasi KRS, approve KRS, kelola jadwal, deteksi bentrok, input nilai, dan generate transkrip. Tandai relasi `<<include>>` dan `<<extend>>`."[cite: 27, 29]

**Perbandingan Hasil AI vs Revisi Manual:**
- **Hasil Awal AI:** AI menyamakan seluruh relasi sub-proses sebagai garis panah biasa (`-->`) tanpa membedakan perilaku wajib (`<<include>>`) dan opsional/kondisional (`<<extend>>`)[cite: 27, 29].
- **Revisi Manual:** Menambahkan relasi `<<include>>` dari *Pengisian KRS* ke *Validasi Prasyarat, SKS & Bentrok* dan dari *Input Nilai* ke *Validasi Presensi >= 75%*, serta relasi `<<extend>>` untuk alur *Approval/Revisi KRS* dan *Generate Transkrip*[cite: 27, 29].

---

## Prompt 4: Sequence Diagram Proses PMB dengan Penanganan Error
**Prompt yang Digunakan:**
> "Buat sequence diagram Mermaid untuk proses pendaftaran mahasiswa baru (PMB) mulai dari registrasi calon mahasiswa, verifikasi pembayaran, verifikasi berkas oleh admin, pembuatan NIM otomatis dengan row locking, hingga pengiriman notifikasi. Sertakan blok `alt/else` untuk menangani duplikasi data dan pembayaran yang belum lunas."[cite: 27, 30]

**Perbandingan Hasil AI vs Revisi Manual:**
- **Hasil Awal AI:** AI hanya membuat alur sukses (*happy path*) tanpa pengecekan duplikasi NIK/email maupun kegagalan pembayaran[cite: 30].
- **Revisi Manual:** Menambahkan dua blok *alternate flow* (`alt/else`) untuk mengembalikan status `409 Conflict` saat data ganda dan `402 Payment Required` saat tagihan belum lunas, serta menegaskan transaksi `FOR UPDATE` sebelum generasi NIM[cite: 30].

---

## Prompt 5: Sequence Diagram Validasi KRS (Chain of Responsibility)
**Prompt yang Digunakan:**
> "Buat sequence diagram untuk proses validasi KRS: 1) Mahasiswa submit KRS, 2) Sistem cek double enrollment, 3) Sistem cek prasyarat mata kuliah minimal nilai C, 4) Sistem cek jadwal bentrok, 5) Sistem cek batas SKS maksimal 24, 6) Jika lulus validasi status KRS menjadi SUBMITTED dan notifikasi dikirim ke Dosen PA. Tambahkan alur penolakan validasi dan alur review Dosen PA."[cite: 29, 30]

**Perbandingan Hasil AI vs Revisi Manual:**
- **Hasil Awal AI:** AI menggabungkan pengecekan validasi dan persetujuan Dosen PA dalam satu blok sinkron tanpa pemisahan transaksi database[cite: 29].
- **Revisi Manual:** Memisahkan fase `submit_krs` (dengan *rollback* otomatis jika rantai validasi gagal) dan fase `review_krs` oleh Dosen PA yang menghasilkan status `APPROVED` atau `REVISION` beserta notifikasi ke mahasiswa[cite: 29, 30].

---

## Prompt 6: Sequence Diagram Observer Pattern & Transactional Outbox
**Prompt yang Digunakan:**
> "Buat sequence diagram untuk skenario perubahan jadwal kuliah menggunakan Observer Pattern dan Transactional Outbox agar notifikasi lintas kanal (Email, SMS, Push) hanya dikirim setelah transaksi database berhasil di-commit dan KRS terdampak dikembalikan ke status REVISION."

**Perbandingan Hasil AI vs Revisi Manual:**
- **Hasil Awal AI:** AI memanggil layanan pengiriman email langsung sebelum `COMMIT` database[cite: 30].
- **Revisi Manual:** Menyimpan *event* ke tabel `outbox_events` dan mengubah status KRS menjadi `REVISION` sebelum `COMMIT`, lalu menjalankan `OutboxDispatcher` secara paralel (`par`) ke tiga *observer* setelah `COMMIT` selesai (tersimpan di `docs/SEQUENCE_DIAGRAM_OBSERVER.md`).