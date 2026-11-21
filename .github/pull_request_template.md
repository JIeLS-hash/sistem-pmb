## Deskripsi Perubahan
- [ ] Skema database & migrasi Alembic (`calon_mahasiswa`, `program_studi`, `jalur_masuk`)
- [ ] Endpoint REST API PMB (`register`, `status`, `approve`, `reject`, `stats`)
- [ ] Generator NIM otomatis (`YYYY[KODE]-XXXX`), *idempotent*, dan aman dari *race condition*
- [ ] Unit test `pytest` dengan *coverage* >= 80%

## Bukti Pengujian
- `python -m pytest --cov=app --cov-report=term-missing` lulus 100%
- Swagger UI (`/docs`) terverifikasi

### Checklist Minggu 7 & Minggu 8 (Jadwal, Observer, & AI Rescheduling)
- [x] Model `Ruangan`, `Dosen`, `Kelas`, `Jadwal`, dan `OutboxEvent` termigrasi via Alembic
- [x] Detektor bentrok 3D (`sweep-line` vs `naive`) dan ADR terdokumentasi di `docs/ADR_002_CONFLICT_DETECTION.md`
- [x] *Observer Pattern* (`ScheduleSubject`, 3 *observer*, kanal log `EMAIL`/`SMS`/`PUSH`) + *OutboxDispatcher* pasca-`commit`
- [x] `KRSInvalidator` mengembalikan KRS terdampak ke `REVISION` via `Actor.SISTEM` + teruji 42 transisi ilegal
- [x] AI Rescheduling (`Prompt Step 3` + `saring_saran`), ekspor `.ics`, dan Conflict Resolver UI (`/api/jadwal/dashboard`)
- [x] UML Sequence Diagram di `docs/SEQUENCE_DIAGRAM_OBSERVER.md`, AI Log & OPAR diperbarui, dan seluruh `pytest` lulus