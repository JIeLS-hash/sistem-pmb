from __future__ import annotations

import base64
import io
import re
import ssl
import urllib.request
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

ROOT_DIR = Path(__file__).resolve().parent.parent
DIAGRAMS_DIR = ROOT_DIR / "diagrams"
DOCS_DIR = ROOT_DIR / "docs"


def _build_styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "CustomTitle",
            parent=base["Title"],
            fontSize=18,
            leading=22,
            textColor=colors.HexColor("#0f172a"),
            alignment=TA_CENTER,
            spaceAfter=6,
        ),
        "subtitle": ParagraphStyle(
            "CustomSubtitle",
            parent=base["Normal"],
            fontSize=10.5,
            leading=14,
            textColor=colors.HexColor("#475569"),
            alignment=TA_CENTER,
            spaceAfter=16,
        ),
        "h1": ParagraphStyle(
            "CustomH1",
            parent=base["Heading1"],
            fontSize=13,
            leading=17,
            textColor=colors.HexColor("#1e3a8a"),
            spaceBefore=12,
            spaceAfter=6,
        ),
        "h2": ParagraphStyle(
            "CustomH2",
            parent=base["Heading2"],
            fontSize=11,
            leading=15,
            textColor=colors.HexColor("#0f172a"),
            spaceBefore=8,
            spaceAfter=4,
        ),
        "body": ParagraphStyle(
            "CustomBody",
            parent=base["Normal"],
            fontSize=9.8,
            leading=14,
            textColor=colors.HexColor("#1e293b"),
            alignment=TA_JUSTIFY,
            spaceAfter=6,
        ),
        "bullet": ParagraphStyle(
            "CustomBullet",
            parent=base["Normal"],
            fontSize=9.6,
            leading=13.5,
            textColor=colors.HexColor("#1e293b"),
            leftIndent=14,
            spaceAfter=4,
        ),
        "code": ParagraphStyle(
            "CustomCode",
            parent=base["Code"],
            fontName="Courier",
            fontSize=7.5,
            leading=9.5,
            textColor=colors.HexColor("#0f172a"),
            backColor=colors.HexColor("#f1f5f9"),
        ),
        "caption": ParagraphStyle(
            "CustomCaption",
            parent=base["Normal"],
            fontSize=8.8,
            leading=12,
            textColor=colors.HexColor("#64748b"),
            alignment=TA_CENTER,
            spaceBefore=4,
            spaceAfter=10,
        ),
    }


def _render_mermaid_image(mermaid_code: str, max_w: float, max_h: float) -> Image | None:
    """Merender kode Mermaid menjadi gambar PNG via mermaid.ink untuk disisipkan ke PDF."""
    encoded = base64.urlsafe_b64encode(mermaid_code.strip().encode("utf-8")).decode("ascii")
    url = f"https://mermaid.ink/img/{encoded}?bgColor=white"
    ctx = ssl.create_default_context()
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=20, context=ctx) as resp:
            png_bytes = resp.read()
        buf = io.BytesIO(png_bytes)
        reader = ImageReader(buf)
        orig_w, orig_h = reader.getSize()
        scale = min(max_w / orig_w, max_h / orig_h, 1.0)
        buf.seek(0)
        return Image(buf, width=orig_w * scale, height=orig_h * scale)
    except Exception:
        return None


def _extract_mermaid_from_md(md_path: Path) -> str:
    text = md_path.read_text(encoding="utf-8")
    match = re.search(r"```mermaid\s+(.*?)```", text, flags=re.DOTALL)
    return match.group(1).strip() if match else text.strip()


def generate_adr_pdf(output_path: Path) -> None:
    styles = _build_styles()
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=1.8 * cm,
        bottomMargin=1.8 * cm,
        title="Architecture Decision Record (ADR) - Sistem Akademik SEVIMA-Mini",
    )

    story = [
        Paragraph("ARCHITECTURE DECISION RECORD (ADR)", styles["title"]),
        Paragraph(
            "Perancangan Arsitektur Sistem Informasi Akademik (PMB, KRS, Jadwal, & Nilai) — SEVIMA-Mini",
            styles["subtitle"],
        ),
        Paragraph("1. Konteks & Permasalahan Arsitektur", styles["h1"]),
        Paragraph(
            "Sistem Informasi Akademik mencakup siklus hidup data mahasiswa yang saling terhubung: "
            "Penerimaan Mahasiswa Baru (PMB), Pengisian Kartu Rencana Studi (KRS), Penjadwalan Kuliah & Ruangan, "
            "serta Penilaian & Transkrip. Tanpa batas tanggung jawab yang tegas, entitas utama seperti Admin atau "
            "KRS berisiko tumbuh menjadi God Object yang sulit diuji, rentan terhadap race condition saat generasi NIM "
            "maupun pemesanan ruangan, serta melanggar prinsip SOLID.",
            styles["body"],
        ),
        Paragraph("2. Keputusan Desain Struktur Class & Prinsip SOLID", styles["h1"]),
        Paragraph(
            "• <b>Hierarki Pewarisan User (Inheritance):</b> Atribut umum identitas (id, nama, email, password_hash) "
            "ditempatkan pada base class <i>User</i> dengan visibility protected (#), lalu diturunkan ke "
            "<i>CalonMahasiswa</i>, <i>Mahasiswa</i>, <i>Dosen</i>, dan <i>Admin</i> sesuai peran masing-masing.",
            styles["bullet"],
        ),
        Paragraph(
            "• <b>Pemisahan Entitas Transaksi KRS:</b> Alih-alih menghubungkan <i>Mahasiswa</i> langsung ke <i>Course</i> "
            "secara many-to-many, sistem memperkenalkan entitas agregator <i>KRS</i> per semester yang membawahi "
            "<i>Enrollment</i> melalui relasi <i>Composition</i> (*--), sehingga status persetujuan (DRAFT, SUBMITTED, "
            "APPROVED, REVISION) dapat dikelola per semester.",
            styles["bullet"],
        ),
        Paragraph(
            "• <b>Composition vs Aggregation:</b> Relasi siklus hidup kuat menggunakan <i>Composition</i> (*--) "
            "(misalnya <i>Course</i> memiliki <i>Schedule</i>, <i>Enrollment</i> memiliki <i>Grade</i>), sedangkan "
            "relasi referensi longgar menggunakan <i>Aggregation</i> (o--) seperti relasi prasyarat antar-<i>Course</i>.",
            styles["bullet"],
        ),
        Paragraph("3. Design Patterns yang Diterapkan", styles["h1"]),
    ]

    pattern_data = [
        ["Design Pattern", "Modul Penerapan", "Alasan & Manfaat Arsitektural"],
        [
            "Chain of Responsibility",
            "Validasi KRS\n(KRSValidationChain)",
            "Memecah aturan validasi (double enrollment, prasyarat >= C, bentrok jadwal, maks 24 SKS) menjadi handler independen berurutan (fail-fast).",
        ],
        [
            "State Machine &\nRow Locking",
            "PMB & KRS\n(FOR UPDATE)",
            "Mencegah generasi NIM ganda pada pendaftaran bersamaan dan membatasi transisi status KRS berdasarkan aktor (Mahasiswa, Dosen PA, Sistem).",
        ],
        [
            "Observer Pattern &\nTransactional Outbox",
            "Jadwal & Notifikasi\n(ScheduleSubject)",
            "Memisahkan logika penjadwalan dari kanal notifikasi (Email, SMS, Push) (OCP) dan menjamin notifikasi hanya terkirim setelah transaksi DB commit.",
        ],
        [
            "Sweep-Line Interval",
            "Deteksi Bentrok 3D\n(ConflictDetector)",
            "Mendeteksi bentrok ruangan dan dosen secara efisien O(N log N + K) menggunakan interval setengah terbuka [jam_mulai, jam_selesai).",
        ],
    ]
    th = ParagraphStyle("TH", parent=styles["body"], fontName="Helvetica-Bold", fontSize=8.8, leading=12, textColor=colors.white, alignment=TA_LEFT, spaceAfter=0)
    td = ParagraphStyle("TD", parent=styles["body"], fontName="Helvetica", fontSize=8.8, leading=12, textColor=colors.HexColor("#1e293b"), alignment=TA_LEFT, spaceAfter=0)
    esc = lambda x: x.replace("&", "&").replace("<", "<").replace(">", ">").replace("\n", "<br/>")
    pattern_data = [[Paragraph(esc(c), th if i == 0 else td) for c in r] for i, r in enumerate(pattern_data)]
    tbl = Table(pattern_data, colWidths=[3.8 * cm, 3.8 * cm, 9.4 * cm])
    tbl.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e3a8a")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8.8),
                ("LEADING", (0, 0), (-1, -1), 12),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(tbl)
    story.append(Spacer(1, 10))

    story.extend(
        [
            Paragraph("4. Pertimbangan Trade-Off Arsitektur", styles["h1"]),
            Paragraph(
                "• <b>SQLite + Row Locking vs Distributed Broker:</b> Penggunaan tabel <i>outbox_events</i> di database "
                "relasional dipilih dibanding langsung memasang message broker terpisah (Kafka/RabbitMQ) karena menjaga "
                "atomisitas transaksi dalam satu proses aplikasi tanpa menambah kompleksitas infrastruktur.",
                styles["bullet"],
            ),
            Paragraph(
                "• <b>AI-Assisted Design dengan Validator Deterministik:</b> Keluaran AI pada perancangan UML maupun "
                "rekomendasi penjadwalan ulang selalu melewati tahap audit manual dan saringan aturan bisnis agar bebas "
                "dari kesalahan kardinalitas maupun halusinasi jadwal.",
                styles["bullet"],
            ),
        ]
    )

    doc.build(story)


def generate_final_uml_pdf(output_path: Path) -> None:
    styles = _build_styles()
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=1.8 * cm,
        rightMargin=1.8 * cm,
        topMargin=1.8 * cm,
        bottomMargin=1.8 * cm,
        title="Laporan Final UML Diagram - Sistem Informasi Akademik",
    )

    diagrams_spec = [
        (
            "1. Class Diagram Sistem Informasi Akademik",
            DIAGRAMS_DIR / "class-diagram.mmd",
            "Menampilkan hierarki User (CalonMahasiswa, Mahasiswa, Dosen, Admin), entitas inti "
            "(Payment, Course, KRS, Enrollment, Schedule, Grade), visibility modifier, serta relasi "
            "inheritance, composition (*--), dan aggregation (o--).",
        ),
        (
            "2. Use Case Diagram Sistem Informasi Akademik",
            DIAGRAMS_DIR / "usecase-diagram.mmd",
            "Memetakan 5 aktor (Calon Mahasiswa, Mahasiswa, Dosen/PA, Admin Akademik, Sistem PMB) "
            "dan 11 use case utama lengkap dengan relasi <<include>> dan <<extend>>.",
        ),
        (
            "3. Sequence Diagram — Proses Pendaftaran Mahasiswa Baru (PMB)",
            DIAGRAMS_DIR / "sequence-pmb.mmd",
            "Menggambarkan alur registrasi calon mahasiswa, verifikasi pembayaran, row locking generasi NIM, "
            "serta alternate flow (alt/else) untuk penanganan duplikasi data dan gagal bayar.",
        ),
        (
            "4. Sequence Diagram — Validasi & Persetujuan KRS",
            DIAGRAMS_DIR / "sequence-krs.mmd",
            "Menggambarkan rantai validasi fail-fast (double enrollment, prasyarat nilai >= C, bentrok jadwal, "
            "maksimal 24 SKS), rollback saat validasi gagal, dan alur review oleh Dosen PA.",
        ),
        (
            "5. Sequence Diagram — Observer Pattern & Transactional Outbox",
            DOCS_DIR / "SEQUENCE_DIAGRAM_OBSERVER.md",
            "Menggambarkan invalidasi KRS terdampak ke status REVISION oleh Actor.SISTEM dan pengiriman "
            "notifikasi paralel (Email, SMS, Push) setelah transaksi database di-commit.",
        ),
    ]

    story = [
        Paragraph("LAPORAN FINAL PERANCANGAN UML DIAGRAM", styles["title"]),
        Paragraph(
            "Sistem Informasi Akademik (Modul PMB, KRS, Penjadwalan, & Penilaian) — SEVIMA-Mini",
            styles["subtitle"],
        ),
        Paragraph("Ringkasan Proses Perancangan & Validasi Output AI", styles["h1"]),
        Paragraph(
            "Perancangan arsitektur sistem dilakukan secara iteratif menggunakan bantuan AI LLM dengan pendekatan "
            "prompt engineering terstruktur, kemudian divalidasi secara manual untuk memastikan kesesuaian prinsip "
            "SOLID, ketepatan kardinalitas relasi, kelengkapan alternate flow pada sequence diagram, serta pencegahan "
            "God Object dan circular dependency.",
            styles["body"],
        ),
    ]

    for idx, (heading, file_path, desc) in enumerate(diagrams_spec):
        if idx > 0:
            story.append(PageBreak())
        story.append(Paragraph(heading, styles["h1"]))
        story.append(Paragraph(desc, styles["body"]))

        code = (
            _extract_mermaid_from_md(file_path)
            if file_path.suffix == ".md"
            else file_path.read_text(encoding="utf-8").strip()
        )
        img = _render_mermaid_image(code, max_w=17.0 * cm, max_h=18.5 * cm)
        if img is not None:
            story.append(Spacer(1, 4))
            story.append(img)
            story.append(Paragraph(f"Gambar {idx + 1}. {heading}", styles["caption"]))
        else:
            story.append(Preformatted(code, styles["code"]))
            story.append(
                Paragraph(
                    f"Spesifikasi Mermaid {idx + 1}. {heading} (file sumber: {file_path.name})",
                    styles["caption"],
                )
            )

    doc.build(story)


if __name__ == "__main__":
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    adr_pdf = DOCS_DIR / "ADR-architecture-decisions.pdf"
    uml_pdf = DOCS_DIR / "Final-UML-diagram.pdf"
    generate_adr_pdf(adr_pdf)
    generate_final_uml_pdf(uml_pdf)
    print(f"Berhasil membuat: {adr_pdf}")
    print(f"Berhasil membuat: {uml_pdf}")