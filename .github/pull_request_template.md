## Deskripsi Perubahan
- [ ] Skema database & migrasi Alembic (`calon_mahasiswa`, `program_studi`, `jalur_masuk`)
- [ ] Endpoint REST API PMB (`register`, `status`, `approve`, `reject`, `stats`)
- [ ] Generator NIM otomatis (`YYYY[KODE]-XXXX`), *idempotent*, dan aman dari *race condition*
- [ ] Unit test `pytest` dengan *coverage* >= 80%

## Bukti Pengujian
- `python -m pytest --cov=app --cov-report=term-missing` lulus 100%
- Swagger UI (`/docs`) terverifikasi