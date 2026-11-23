from __future__ import annotations

import io
from datetime import date
from typing import Any

from reportlab.graphics.shapes import Circle, Drawing, String as DrawingString
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


def _create_university_logo() -> Drawing:
    """Membuat emblem resmi universitas berbasis vektor untuk kop transkrip."""
    d = Drawing(46, 46)
    d.add(Circle(23, 23, 21, fillColor=colors.HexColor("#1e3a8a"), strokeColor=colors.HexColor("#d97706"), strokeWidth=2))
    d.add(Circle(23, 23, 16, fillColor=colors.HexColor("#1e40af"), strokeColor=colors.white, strokeWidth=0.8))
    d.add(
        DrawingString(
            23,
            19,
            "UNIV",
            fontName="Helvetica-Bold",
            fontSize=9,
            fillColor=colors.white,
            textAnchor="middle",
        )
    )
    return d


def generate_transcript_pdf(transcript_data: dict[str, Any]) -> bytes:
    """Menghasilkan file PDF Transkrip Akademik resmi dari dictionary hasil get_transcript()."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=1.8 * cm,
        rightMargin=1.8 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
        title=f"Transkrip Akademik - {transcript_data['biodata']['nim']}",
    )

    base = getSampleStyleSheet()
    univ_style = ParagraphStyle(
        "UnivHeader",
        parent=base["Title"],
        fontSize=13,
        leading=16,
        textColor=colors.HexColor("#0f172a"),
        alignment=TA_LEFT,
        spaceAfter=2,
    )
    sub_univ_style = ParagraphStyle(
        "SubUnivHeader",
        parent=base["Normal"],
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#475569"),
        alignment=TA_LEFT,
    )
    doc_title_style = ParagraphStyle(
        "DocTitle",
        parent=base["Title"],
        fontSize=14,
        leading=18,
        textColor=colors.HexColor("#1e3a8a"),
        alignment=TA_CENTER,
        spaceBefore=8,
        spaceAfter=10,
    )
    smt_heading_style = ParagraphStyle(
        "SmtHeading",
        parent=base["Heading2"],
        fontSize=10,
        leading=13,
        textColor=colors.HexColor("#0f172a"),
        spaceBefore=8,
        spaceAfter=4,
    )
    normal_style = ParagraphStyle(
        "CustomNormal",
        parent=base["Normal"],
        fontSize=9.2,
        leading=12.5,
        textColor=colors.HexColor("#1e293b"),
    )
    sign_style = ParagraphStyle(
        "SignStyle",
        parent=base["Normal"],
        fontSize=9.2,
        leading=13,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#0f172a"),
    )

    biodata = transcript_data["biodata"]
    semesters = transcript_data["semesters"]
    summary = transcript_data["summary"]

    story = []

    # 1. Header Universitas + Logo
    header_table = Table(
        [
            [
                _create_university_logo(),
                Paragraph(
                    "<b>UNIVERSITAS TEKNOLOGI NUSANTARA</b><br/>"
                    f"<font size='9' color='#334155'>{biodata['fakultas'].upper()}</font><br/>"
                    "<font size='8' color='#64748b'>Jl. Pendidikan Raya No. 10, Depok — Website: www.utn.ac.id</font>",
                    univ_style,
                ),
            ]
        ],
        colWidths=[1.9 * cm, 15.5 * cm],
    )
    header_table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    story.append(header_table)
    story.append(Spacer(1, 4))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#1e3a8a")))
    story.append(Spacer(1, 2))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#d97706")))

    story.append(Paragraph("TRANSKRIP AKADEMIK", doc_title_style))

    # 2. Biodata Mahasiswa
    bio_table = Table(
        [
            [
                Paragraph("<b>NIM</b>", normal_style),
                Paragraph(f": {biodata['nim']}", normal_style),
                Paragraph("<b>Program Studi</b>", normal_style),
                Paragraph(f": {biodata['program_studi']}", normal_style),
            ],
            [
                Paragraph("<b>Nama Lengkap</b>", normal_style),
                Paragraph(f": {biodata['nama']}", normal_style),
                Paragraph("<b>Angkatan</b>", normal_style),
                Paragraph(f": {biodata['angkatan']}", normal_style),
            ],
        ],
        colWidths=[2.7 * cm, 6.0 * cm, 2.8 * cm, 5.9 * cm],
    )
    bio_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
                ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#cbd5e1")),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(bio_table)
    story.append(Spacer(1, 8))

    # 3. Tabel Nilai Per Semester
    if not semesters:
        story.append(
            Paragraph(
                "<i>Belum terdapat rekaman nilai akademik untuk mahasiswa ini.</i>",
                normal_style,
            )
        )
    else:
        for smt_data in semesters:
            story.append(
                Paragraph(
                    f"Semester: <b>{smt_data['semester']}</b> (IPS: <b>{smt_data['ips']:.2f}</b>)",
                    smt_heading_style,
                )
            )
            table_rows = [["Kode MK", "Nama Mata Kuliah", "SKS", "Nilai", "Mutu"]]
            for c in smt_data["courses"]:
                table_rows.append(
                    [
                        c["kode_mk"],
                        c["nama_mk"],
                        str(c["sks"]),
                        c["nilai_huruf"],
                        f"{c['mutu']:.2f}",
                    ]
                )
            table_rows.append(
                [
                    "",
                    "Subtotal Semester",
                    str(smt_data["total_sks"]),
                    f"IPS: {smt_data['ips']:.2f}",
                    f"{smt_data['total_mutu']:.2f}",
                ]
            )

            course_table = Table(
                table_rows,
                colWidths=[2.5 * cm, 8.9 * cm, 1.8 * cm, 2.1 * cm, 2.1 * cm],
            )
            course_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e3a8a")),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, -1), 8.6),
                        ("ALIGN", (0, 0), (0, -1), "CENTER"),
                        ("ALIGN", (2, 0), (-1, -1), "CENTER"),
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#eff6ff")),
                        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                        ("TOPPADDING", (0, 0), (-1, -1), 4),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ]
                )
            )
            story.append(course_table)
            story.append(Spacer(1, 6))

    # 4. Ringkasan Kumulatif & Tanda Tangan Dekan
    story.append(Spacer(1, 8))
    summary_table = Table(
        [
            [
                Paragraph("<b>Total SKS Lulus</b>", normal_style),
                Paragraph(f": <b>{summary['total_sks']} SKS</b>", normal_style),
            ],
            [
                Paragraph("<b>Total Angka Mutu</b>", normal_style),
                Paragraph(f": <b>{summary['total_mutu']:.2f}</b>", normal_style),
            ],
            [
                Paragraph("<b>Indeks Prestasi Kumulatif (IPK)</b>", normal_style),
                Paragraph(f": <b>{summary['ipk']:.2f}</b>", normal_style),
            ],
            [
                Paragraph("<b>Predikat Kelulusan</b>", normal_style),
                Paragraph(f": <b>{summary['predikat']}</b>", normal_style),
            ],
        ],
        colWidths=[5.8 * cm, 11.6 * cm],
    )
    summary_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
                ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#1e3a8a")),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    story.append(summary_table)
    story.append(Spacer(1, 18))

    today_str = date.today().strftime("%d %B %Y")
    ttd_table = Table(
        [
            [
                "",
                Paragraph(
                    f"Depok, {today_str}<br/>"
                    f"Dekan {biodata['fakultas']},<br/><br/><br/><br/>"
                    "<b><u>Prof. Dr. Ir. Hendra Wijaya, M.Kom.</u></b><br/>"
                    "NIP. 197504122001121003",
                    sign_style,
                ),
            ]
        ],
        colWidths=[10.2 * cm, 7.2 * cm],
    )
    story.append(ttd_table)

    doc.build(story)
    return buf.getvalue()