"""
Shared TestPilot report template.

Everything here exists so the Basic / Standard / Premium PDF reports
(plan_pdf_service.py) all come out of the SAME visual template as
TestPilot_Report_Template_With_Logo.pdf - logo + olive brand colors,
same header block, same "Summary Scores" and "Functional Testing
Summary" table layouts - instead of each plan drawing its own
one-off header.

Only the DATA differs per plan; the template stays identical.
"""

import os
import re

from reportlab.platypus import Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib import colors
from reportlab.lib.units import inch, mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT

# ===============================
# Brand palette (sampled from TestPilot_Report_Template_With_Logo.pdf)
# ===============================

OLIVE_DARK = colors.HexColor("#495B16")     # big title / heading text
OLIVE_ACCENT = colors.HexColor("#759123")   # table header bg / accent bars
OLIVE_LIGHT_BG = colors.HexColor("#F0F4E8") # section-title strip background
ROW_ALT_BG = colors.HexColor("#F5F7F0")     # zebra-striped row background
GREY_LABEL_BG = colors.HexColor("#EDEDED")  # label cell background (info table)
BORDER_GREY = colors.HexColor("#D0D5C8")

CONTENT_WIDTH = 450  # points - matches the width already used across plan_pdf_service tables

# Logo lives at app/assets/TestPilot_logo.png
LOGO_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "assets",
    "TestPilot_logo.png",
)


def get_logo_flowable(max_width=1.7 * inch):
    """Returns a reportlab Image flowable for the logo, sized to max_width
    with aspect ratio preserved. Returns None if the logo file is missing
    (so report generation never breaks because of a missing asset)."""

    if not os.path.exists(LOGO_PATH):
        return None

    try:
        from PIL import Image as PILImage
        with PILImage.open(LOGO_PATH) as im:
            w, h = im.size
        ratio = h / float(w)
        return Image(LOGO_PATH, width=max_width, height=max_width * ratio)
    except Exception:
        return None


def report_title_style():
    return ParagraphStyle(
        "TestPilotReportTitle",
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        textColor=OLIVE_DARK,
        alignment=TA_LEFT,
    )


def report_subtitle_style():
    return ParagraphStyle(
        "TestPilotReportSubtitle",
        fontName="Helvetica",
        fontSize=10.5,
        leading=14,
        textColor=colors.HexColor("#555555"),
        alignment=TA_LEFT,
    )


def section_heading_style():
    return ParagraphStyle(
        "TestPilotSectionHeading",
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=16,
        textColor=OLIVE_DARK,
    )


# ===============================
# Header block: logo + title + info table
# ===============================

def build_report_header(subtitle_text, url, generated_str, plan_level):
    """
    Builds the top-of-report block used by every plan:

        WEBSITE HEALTH REPORT                     [logo]
        <subtitle_text>

        Website URL      | <url>
        Generated Date   | <date>   Plan Level | <plan>

    Matches TestPilot_Report_Template_With_Logo.pdf section 0/1.
    Returns a list of flowables ready to extend() onto the story.
    """

    story = []

    title_block = [
        Paragraph("WEBSITE HEALTH REPORT", report_title_style()),
        Paragraph(subtitle_text, report_subtitle_style()),
    ]

    logo = get_logo_flowable()

    if logo is not None:
        head_table = Table(
            [[title_block, logo]],
            colWidths=[CONTENT_WIDTH - 130, 130],
        )
        head_table.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                    ("LINEBELOW", (0, 0), (-1, -1), 1.2, OLIVE_ACCENT),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ]
            )
        )
        story.append(head_table)
    else:
        story.append(Paragraph("WEBSITE HEALTH REPORT", report_title_style()))
        story.append(Paragraph(subtitle_text, report_subtitle_style()))

    story.append(Spacer(1, 0.18 * inch))

    label_style = ParagraphStyle(
        "InfoLabel", fontName="Helvetica-Bold", fontSize=9.5, textColor=colors.HexColor("#333333")
    )
    value_style = ParagraphStyle(
        "InfoValue", fontName="Helvetica", fontSize=9.5, textColor=colors.HexColor("#333333")
    )

    info_table = Table(
        [
            [
                Paragraph("Website URL", label_style),
                Paragraph(url or "N/A", value_style),
                "",
                "",
            ],
            [
                Paragraph("Generated Date", label_style),
                Paragraph(generated_str, value_style),
                Paragraph("Plan Level", label_style),
                Paragraph(plan_level, value_style),
            ],
        ],
        colWidths=[95, 165, 90, 100],
        spaceAfter=6,
    )
    info_table.setStyle(
        TableStyle(
            [
                ("SPAN", (1, 0), (3, 0)),
                ("BACKGROUND", (0, 0), (0, -1), GREY_LABEL_BG),
                ("BACKGROUND", (2, 1), (2, 1), GREY_LABEL_BG),
                ("GRID", (0, 0), (-1, -1), 0.5, BORDER_GREY),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    story.append(info_table)
    story.append(Spacer(1, 0.22 * inch))

    return story


# ===============================
# Section heading with the olive accent strip (matches template's
# "1. Summary Scores" / "2. Functional Testing Summary" bars)
# ===============================

def section_heading(text):
    t = Table([[Paragraph(f"<b>{text}</b>", section_heading_style())]], colWidths=[CONTENT_WIDTH])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), OLIVE_LIGHT_BG),
                ("LINEBEFORE", (0, 0), (0, -1), 4, OLIVE_ACCENT),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )
    return t


def _status_for_score(score):
    try:
        score = float(score)
    except (TypeError, ValueError):
        return "N/A"

    if score >= 80:
        return "Good"
    elif score >= 60:
        return "Fair"
    elif score >= 40:
        return "Needs Improvement"
    else:
        return "Critical"


def _status_color_hex(status):
    return {
        "Good": "#2E7D32",
        "Fair": "#8D6E63",
        "Needs Improvement": "#EF6C00",
        "Critical": "#C62828",
    }.get(status, "#555555")


# ===============================
# Summary Scores table (matches template's Metric | Score/Grade | Status)
# ===============================

def summary_scores_table(rows):
    """
    rows: list of (label, score, grade) tuples. grade may be None for
    scores that aren't letter-graded (e.g. plain Website Health).
    """

    cell_style = ParagraphStyle("ScoreCell", fontName="Helvetica", fontSize=9.5, leading=12)
    cell_bold = ParagraphStyle("ScoreCellBold", parent=cell_style, fontName="Helvetica-Bold")

    data = [[
        Paragraph("Metric", cell_bold),
        Paragraph("Score / Grade", cell_bold),
        Paragraph("Status", cell_bold),
    ]]

    style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), OLIVE_ACCENT),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, BORDER_GREY),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, ROW_ALT_BG]),
    ]

    for i, (label, score, grade) in enumerate(rows, start=1):
        status = _status_for_score(score)
        score_text = f"{score}/100" + (f" (Grade {grade})" if grade else "")
        status_para = Paragraph(
            f'<font color="{_status_color_hex(status)}"><b>{status}</b></font>',
            cell_bold,
        )
        data.append([
            Paragraph(label, cell_style),
            Paragraph(score_text, cell_style),
            status_para,
        ])

    t = Table(data, colWidths=[190, 130, 130], repeatRows=1)
    t.setStyle(TableStyle(style_cmds))
    return t


# ===============================
# Functional Testing Summary - top-line stat table (matches template)
# ===============================

def functional_summary_bar(executed, total, passed, failed, partial, skipped):
    cell_style = ParagraphStyle("FuncStat", fontName="Helvetica", fontSize=9.5)
    cell_bold = ParagraphStyle("FuncStatBold", parent=cell_style, fontName="Helvetica-Bold")

    data = [
        [
            Paragraph("Modules Executed", cell_bold),
            Paragraph(f"{executed} / {total}", cell_style),
            Paragraph("Passed", cell_bold),
            Paragraph(str(passed), cell_style),
        ],
        [
            Paragraph("Failed", cell_bold),
            Paragraph(str(failed), cell_style),
            Paragraph("Partial / Skipped", cell_bold),
            Paragraph(f"{partial} / {skipped}", cell_style),
        ],
    ]
    t = Table(data, colWidths=[110, 115, 110, 115])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), GREY_LABEL_BG),
                ("BACKGROUND", (2, 0), (2, -1), GREY_LABEL_BG),
                ("GRID", (0, 0), (-1, -1), 0.5, BORDER_GREY),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return t


def module_status_table(module_rows):
    """
    module_rows: list of (module_name, status, note) - the compact
    Test Module | Result | Notes table from the template. Detailed
    failure breakdowns (broken link URLs etc.) still get printed as
    bullet lists right after this table, so no data is lost - this
    table is just the at-a-glance summary the template shows.
    """

    cell_style = ParagraphStyle("ModCell", fontName="Helvetica", fontSize=9, leading=11.5)
    cell_bold = ParagraphStyle("ModCellBold", parent=cell_style, fontName="Helvetica-Bold")

    data = [[
        Paragraph("Test Module", cell_bold),
        Paragraph("Result", cell_bold),
        Paragraph("Notes / Details", cell_bold),
    ]]

    style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), OLIVE_ACCENT),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, BORDER_GREY),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, ROW_ALT_BG]),
    ]

    result_colors = {
        "PASS": colors.HexColor("#2E7D32"),
        "FAIL": colors.HexColor("#C62828"),
        "PARTIAL": colors.HexColor("#EF6C00"),
        "SKIPPED": colors.HexColor("#757575"),
    }

    for name, status, note in module_rows:
        color = result_colors.get(str(status).upper(), colors.HexColor("#333333"))
        status_para = Paragraph(f'<font color="{color}"><b>{status}</b></font>', cell_bold)
        data.append([
            Paragraph(str(name), cell_style),
            status_para,
            Paragraph(str(note) if note else "", cell_style),
        ])

    t = Table(data, colWidths=[150, 60, 240], repeatRows=1)
    t.setStyle(TableStyle(style_cmds))
    return t


# ===============================
# AI Recommendations formatter
# ===============================
#
# The Groq/LLM call returns free-form markdown - "**1. Overall Website
# Quality Summary:** ... **2. Top Functional Issues to Fix First:** - **X:**
# ... **High Priority:** 1. **Y:** ..." - all on one line, no real
# paragraph breaks. reportlab's Paragraph does not understand markdown or
# bare "\n", so dropping that string straight into a Paragraph renders the
# literal "**" characters as one unbroken wall of text (this is the bug
# seen in the Premium report's section 8). This parses that markdown into
# real headings / bold / bullet flowables instead.

_AI_MARKDOWN_PATTERN = re.compile(
    r"(?P<top>\*\*(?P<topnum>\d+)\.\s*(?P<toptitle>[^*]+?)\*\*)"
    r"|(?P<priority>\*\*(?P<priolabel>(?:High|Medium|Low)\s+Priority)\s*:?\*\*)"
    r"|(?P<dash>-\s*\*\*(?P<dashlabel>[^*]+?)\*\*)"
    r"|(?P<numitem>(?<!\*)(?P<itemnum>\d+)\.\s+\*\*(?P<itemlabel>[^*]+?)\*\*)"
)


def format_ai_recommendations(text, normal_style):
    """Returns a list of flowables rendering the AI recommendations text
    as proper numbered sections / sub-headings / bullets instead of one
    raw markdown blob."""

    if not text or not str(text).strip():
        return [Paragraph("No AI suggestions generated.", normal_style)]

    # Escape XML-special chars first - safe to do before the markdown scan
    # since none of the patterns above involve &, < or >.
    raw = (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
    raw = re.sub(r"\s+", " ", raw).strip()

    matches = list(_AI_MARKDOWN_PATTERN.finditer(raw))

    if not matches:
        # No recognizable structure - still render any stray **bold** and
        # move on, rather than showing literal asterisks.
        cleaned = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", raw)
        return [Paragraph(cleaned, normal_style)]

    top_heading_style = ParagraphStyle(
        "AITopHeading", parent=normal_style, fontName="Helvetica-Bold",
        fontSize=11.5, textColor=OLIVE_DARK, spaceBefore=10, spaceAfter=4,
    )
    sub_heading_style = ParagraphStyle(
        "AISubHeading", parent=normal_style, fontName="Helvetica-Bold",
        fontSize=10, textColor=OLIVE_DARK, spaceBefore=8, spaceAfter=3,
    )
    bullet_style = ParagraphStyle(
        "AIBullet", parent=normal_style, leftIndent=14, spaceAfter=4,
    )

    story = []

    intro = raw[: matches[0].start()].strip()
    if intro:
        story.append(Paragraph(re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", intro), normal_style))

    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(raw)
        body = raw[m.end():end].strip()
        body = body.lstrip("-").strip()
        body = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", body)

        if m.group("top"):
            label = f"{m.group('topnum')}. {m.group('toptitle').strip().rstrip(':')}"
            story.append(Paragraph(label, top_heading_style))
            if body:
                story.append(Paragraph(body, normal_style))

        elif m.group("priority"):
            story.append(Paragraph(m.group("priolabel").strip(), sub_heading_style))
            if body:
                story.append(Paragraph(body, bullet_style))

        elif m.group("dash"):
            label = m.group("dashlabel").strip().rstrip(":")
            content = f"&bull; <b>{label}:</b> {body}" if body else f"&bull; <b>{label}</b>"
            story.append(Paragraph(content, bullet_style))

        elif m.group("numitem"):
            label = m.group("itemlabel").strip().rstrip(":")
            num = m.group("itemnum")
            content = f"{num}. <b>{label}:</b> {body}" if body else f"{num}. <b>{label}</b>"
            story.append(Paragraph(content, bullet_style))

    return story


def footer_note(text, normal_style):
    """Light footer/upsell note styled with the olive accent, used at the
    bottom of Basic/Standard reports."""

    t = Table([[Paragraph(text, normal_style)]], colWidths=[CONTENT_WIDTH])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), OLIVE_LIGHT_BG),
                ("LINEBEFORE", (0, 0), (0, -1), 4, OLIVE_ACCENT),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )
    return t