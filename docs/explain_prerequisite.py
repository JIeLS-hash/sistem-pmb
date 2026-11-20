from sqlalchemy import text
from app.database import engine

PREREQUISITE_CHECK_SQL = """
SELECT
    p.kode_mk_prasyarat,
    mk.nama AS nama_prasyarat,
    p.min_nilai_huruf
FROM prerequisite p
JOIN matakuliah mk
    ON mk.kode_mk = p.kode_mk_prasyarat
JOIN skala_nilai sn_min
    ON sn_min.huruf = p.min_nilai_huruf
WHERE p.kode_mk = :kode_mk
  AND NOT EXISTS (
      SELECT 1
      FROM riwayat_nilai rn
      JOIN skala_nilai sn_mhs
          ON sn_mhs.huruf = rn.nilai_huruf
      WHERE rn.nim = :nim
        AND rn.kode_mk = p.kode_mk_prasyarat
        AND sn_mhs.bobot >= sn_min.bobot
  );
"""


def run_explain_and_test() -> None:
    params = {"nim": "2026001001", "kode_mk": "IF203"}

    with engine.connect() as conn:
        print("=== 1. HASIL QUERY PRASYARAT BELUM TERPENUHI (NIM: 2026001001, MK: IF203) ===")
        rows = conn.execute(text(PREREQUISITE_CHECK_SQL), params).fetchall()
        for row in rows:
            print(dict(row._mapping))

        print("\n=== 2. BUKTI EXPLAIN QUERY PLAN (OPTIMASI INDEX) ===")
        explain_rows = conn.execute(
            text(f"EXPLAIN QUERY PLAN {PREREQUISITE_CHECK_SQL}"), params
        ).fetchall()
        for row in explain_rows:
            print(row)


if __name__ == "__main__":
    run_explain_and_test()