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

def build_report_header(subtitle_text, url, generated_str, plan_level,
                         title_text="WEBSITE HEALTH REPORT", id_label="Website URL"):
    """
    Builds the top-of-report block used by every plan:

        WEBSITE HEALTH REPORT                     [logo]
        <subtitle_text>

        Website URL      | <url>
        Generated Date   | <date>   Plan Level | <plan>

    Matches TestPilot_Report_Template_With_Logo.pdf section 0/1.
    Returns a list of flowables ready to extend() onto the story.

    `title_text` / `id_label` default to the website-report wording so
    every existing call site is unaffected. Non-website reports (e.g.
    the mobile app security report) pass their own, e.g.
    title_text="MOBILE APP SECURITY REPORT", id_label="File Name".
    """

    story = []

    title_block = [
        Paragraph(title_text, report_title_style()),
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
        story.append(Paragraph(title_text, report_title_style()))
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
                Paragraph(id_label, label_style),
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


def param_value_table(rows, header=("Parameter", "Result"), header_bg=None, label_width_mm=55):
    """
    Renders one continuous two-column table - label on the left, value on
    the right - with a bold colored header row and zebra-striped body,
    matching the exact visual style already used for the SSL/TLS
    Certificate Audit and DNS/DNSSEC/WHOIS tables elsewhere in the
    Premium report.

    Using this (instead of stat_grid_table's shorter multi-pair rows)
    for the Security/Content/UX/CRO/Technical audit summaries keeps every
    section built from the same single-table structure - one header row,
    one row per item, one consistent pair of column widths - so the
    report reads as one coherent, professional document rather than a
    mix of different table shapes.

    rows: list of (label, value) pairs, e.g.
        [("Word Count", 2860), ("Headings", 41)]
    header: the two header-cell labels, e.g. ("Parameter", "Result") or
        ("Metric", "Value").
    header_bg: hex color string for the header row background; defaults
        to the report's standard olive accent (OLIVE_ACCENT) so every
        section header row matches unless a section deliberately wants
        a different accent (as SSL/TLS and DNS tables already do).
    """
    header_style = ParagraphStyle(
        "PVHeader", fontName="Helvetica-Bold", fontSize=9.5, textColor=colors.white,
    )
    label_style = ParagraphStyle(
        "PVLabel", fontName="Helvetica-Bold", fontSize=9,
        textColor=colors.HexColor("#333333"),
    )
    value_style = ParagraphStyle(
        "PVValue", fontName="Helvetica", fontSize=9,
        textColor=colors.HexColor("#333333"),
    )

    data = [[Paragraph(str(header[0]), header_style), Paragraph(str(header[1]), header_style)]]
    for label, value in rows:
        data.append([Paragraph(str(label), label_style), Paragraph(str(value), value_style)])

    label_w = label_width_mm * mm
    value_w = CONTENT_WIDTH - label_w

    bg_color = colors.HexColor(header_bg) if header_bg else OLIVE_ACCENT

    t = Table(data, colWidths=[label_w, value_w], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), bg_color),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CFD8DC")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F7FA")]),
    ]))
    return t


def stat_grid_table(rows, label_ratio=None):
    """
    Renders label/value stat rows (e.g. "Word Count : 2860", "Passed : 14")
    as a grid of bordered, grey-labelled cells - the same visual language
    already used by build_report_header's info table and
    functional_summary_bar - instead of packing "<b>Label :</b> value
    &nbsp;&nbsp;" into one Paragraph with manual <br/> line breaks.

    That manual-spacing approach is what caused the misalignment in the
    Security / Content / UX / Technical sections of the Premium report:
    &nbsp; padding doesn't produce fixed-width columns, so rows drift out
    of line as soon as label or value text length varies. A real Table
    with explicit column widths keeps every row's labels and values
    lined up regardless of content length.

    rows: list of rows; each row is a list of (label, value) pairs, e.g.
        [
            [("Word Count", 2860), ("Headings", 41)],
            [("Readability", "0 (Difficult to read)"),
             ("Duplicate Paragraphs", 0)],
        ]
    A row may have 1, 2, 3 or 4 pairs.

    Each label column is sized to its OWN text width (not a width shared
    across every pair in the row) - a row mixing a long label with short
    ones (e.g. "Internal Links Checked" / "Broken Links" / "Redirected
    Links") previously forced the long label into a column sized off the
    row average, wrapping it mid-word ("Internal Links" / "Checked" on
    two lines). If the labels in a row are collectively too wide to leave
    every value column at least MIN_VALUE_W, label widths are scaled down
    proportionally rather than let one label starve the row.

    Returns a list of Table flowables ready to extend() onto the story.
    """

    from reportlab.pdfbase.pdfmetrics import stringWidth

    label_style = ParagraphStyle(
        "StatGridLabel", fontName="Helvetica-Bold", fontSize=9.5,
        textColor=colors.HexColor("#333333"),
    )
    value_style = ParagraphStyle(
        "StatGridValue", fontName="Helvetica", fontSize=9.5,
        textColor=colors.HexColor("#333333"),
    )

    LABEL_PADDING = 20  # left+right cell padding plus a little breathing room
    MIN_LABEL_W = 46
    MIN_VALUE_W = 40

    flowables = []

    for row in rows:
        n = len(row)
        if n == 0:
            continue

        if label_ratio is not None:
            chunk_w = CONTENT_WIDTH / n
            label_widths = [chunk_w * label_ratio for _ in row]
        else:
            # Size each label to its own text, not the row's widest label.
            label_widths = [
                max(stringWidth(str(label), "Helvetica-Bold", 9.5) + LABEL_PADDING, MIN_LABEL_W)
                for label, _ in row
            ]

        total_label_w = sum(label_widths)
        remaining_for_values = CONTENT_WIDTH - total_label_w

        if remaining_for_values < n * MIN_VALUE_W:
            # Labels collectively too wide for this row - scale them all
            # down proportionally so every value still gets MIN_VALUE_W,
            # instead of one long label pushing the row over budget.
            available_for_labels = CONTENT_WIDTH - n * MIN_VALUE_W
            if available_for_labels > 0 and total_label_w > 0:
                scale = available_for_labels / total_label_w
                label_widths = [w * scale for w in label_widths]
            else:
                label_widths = [CONTENT_WIDTH / (2 * n)] * n
            value_w_each = MIN_VALUE_W
        else:
            value_w_each = remaining_for_values / n

        cells = []
        col_widths = []
        for (label, value), label_w in zip(row, label_widths):
            cells.append(Paragraph(str(label), label_style))
            cells.append(Paragraph(str(value), value_style))
            col_widths.extend([label_w, value_w_each])

        t = Table([cells], colWidths=col_widths)
        style_cmds = [
            ("GRID", (0, 0), (-1, -1), 0.5, BORDER_GREY),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ]
        for i in range(n):
            style_cmds.append(("BACKGROUND", (2 * i, 0), (2 * i, 0), GREY_LABEL_BG))
        t.setStyle(TableStyle(style_cmds))
        flowables.append(t)

    return flowables


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

    # Strip any <think>...</think> reasoning block a reasoning-capable LLM
    # may have prepended - left in place this rendered verbatim as a wall
    # of raw reasoning text ahead of the actual recommendations.
    from app.services.website_ai_findings_service import strip_think_blocks
    text = strip_think_blocks(text)
    if not text.strip():
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


# ===============================
# Generic helpers for non-website reports (e.g. mobile app scans) that
# still want to look like a TestPilot report - same olive brand, same
# grid/zebra-stripe language as the tables above - without forcing them
# through the website-specific summary_scores_table (which derives its
# "Status" purely from a score band, e.g. 80+ = "Good"). A mobile scan's
# severity comes from its worst individual finding, not a score band, so
# it needs its own value shown as-is instead of recomputed.
# ===============================

SEVERITY_STATUS_COLOR = {
    "Critical": "#B00020",
    "High": "#E65100",
    "Medium": "#F9A825",
    "Low": "#2E7D32",
    "Info": "#1565C0",
}


def score_severity_table(score, severity, score_label="Security Score", severity_label="Severity"):
    """Two-column Score / Severity header, olive-branded - same visual
    weight as the website report's score tables, but shows the severity
    value exactly as passed in (not recomputed from the score)."""

    label_style = ParagraphStyle(
        "ScoreSevLabel", fontName="Helvetica-Bold", fontSize=10, textColor=colors.white,
    )
    value_style = ParagraphStyle(
        "ScoreSevValue", fontName="Helvetica-Bold", fontSize=13, alignment=1,
    )
    color = SEVERITY_STATUS_COLOR.get(severity, "#333333")

    data = [
        [Paragraph(score_label, label_style), Paragraph(severity_label, label_style)],
        [
            Paragraph(f"{score}/100", value_style),
            Paragraph(f'<font color="{color}">{severity}</font>', value_style),
        ],
    ]
    t = Table(data, colWidths=[CONTENT_WIDTH / 2, CONTENT_WIDTH / 2])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), OLIVE_ACCENT),
                ("BACKGROUND", (0, 1), (-1, 1), colors.whitesmoke),
                ("GRID", (0, 0), (-1, -1), 0.5, BORDER_GREY),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return t


def key_value_table(rows, col_widths=None, header=None):
    """Generic 2-column key/value table (app overview, permissions,
    provisioning-profile details, etc.) in the same olive/zebra-stripe
    style as the rest of the template. Pass `header=[label, value]` to
    get an olive header row instead of a plain grid."""

    cell_style = ParagraphStyle("KVCell", fontName="Helvetica", fontSize=9.5, leading=12)
    cell_bold = ParagraphStyle("KVCellBold", parent=cell_style, fontName="Helvetica-Bold")

    data = []
    style_cmds = [
        ("GRID", (0, 0), (-1, -1), 0.4, BORDER_GREY),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ]

    start_row = 0
    if header:
        header_cell = ParagraphStyle("KVHeader", parent=cell_bold, textColor=colors.white)
        data.append([Paragraph(h, header_cell) for h in header])
        style_cmds += [
            ("BACKGROUND", (0, 0), (-1, 0), OLIVE_ACCENT),
        ]
        start_row = 1

    for label, value in rows:
        data.append([Paragraph(str(label), cell_bold), Paragraph(str(value), cell_style)])

    style_cmds.append(("ROWBACKGROUNDS", (0, start_row), (-1, -1), [colors.white, ROW_ALT_BG]))

    widths = col_widths or [150, CONTENT_WIDTH - 150]
    t = Table(data, colWidths=widths, repeatRows=1 if header else 0)
    t.setStyle(TableStyle(style_cmds))
    return t


def findings_table(issues):
    """Severity | Finding | Detail table, olive-branded - the mobile-scan
    equivalent of the website report's issue lists, kept as a proper
    table (rather than bullet paragraphs) since that's the format the
    mobile report already used and users are used to scanning."""

    cell_style = ParagraphStyle("FindCell", fontName="Helvetica", fontSize=8.5, leading=11)
    cell_bold = ParagraphStyle("FindCellBold", parent=cell_style, fontName="Helvetica-Bold")
    header_cell = ParagraphStyle("FindHeader", parent=cell_bold, textColor=colors.white)

    data = [[
        Paragraph("Severity", header_cell),
        Paragraph("Finding", header_cell),
        Paragraph("Detail", header_cell),
    ]]

    style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), OLIVE_ACCENT),
        ("GRID", (0, 0), (-1, -1), 0.4, BORDER_GREY),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, ROW_ALT_BG]),
    ]

    for issue in issues:
        color = SEVERITY_STATUS_COLOR.get(issue.get("severity"), "#333333")
        sev_para = Paragraph(f'<font color="{color}"><b>{issue.get("severity", "")}</b></font>', cell_bold)
        data.append([
            sev_para,
            Paragraph(issue.get("title", ""), cell_style),
            Paragraph(issue.get("detail", ""), cell_style),
        ])

    t = Table(data, colWidths=[55, 140, CONTENT_WIDTH - 195], repeatRows=1)
    t.setStyle(TableStyle(style_cmds))
    return t


def failing_items_table(module_name, items):
    """
    Renders a module's failing items (broken link URLs, unlabeled
    buttons, hidden images, etc.) as a proper bordered/zebra-striped
    table instead of "&nbsp;&nbsp;-item" bullet paragraphs.

    Two problems this fixes vs. the old bullet-paragraph rendering:
      1. Alignment: a long URL that wraps to a second line used to fall
         back to the page's left margin instead of lining up under the
         first line. Paragraph's bulletText + leftIndent/bulletIndent
         gives every wrapped line a proper hanging indent.
      2. Completeness: `items` is expected to be the FULL de-duplicated
         list for the module (see _extract_failure_details) - every
         failing item is printed, no "...and N more." truncation.
    """

    header_style = ParagraphStyle(
        "FailItemsHeader", fontName="Helvetica-Bold", fontSize=9.5,
        textColor=colors.white, leading=12,
    )
    cell_style = ParagraphStyle(
        "FailItemCell", fontName="Helvetica", fontSize=8.7, leading=12,
        leftIndent=16, bulletIndent=2,
    )

    count_label = f"{len(items)} item{'s' if len(items) != 1 else ''}"
    data = [[
        Paragraph(
            f"{module_name} &mdash; Failing Items ({count_label})",
            header_style,
        )
    ]]

    style_cmds = [
        ("SPAN", (0, 0), (-1, 0)),
        ("BACKGROUND", (0, 0), (-1, 0), OLIVE_ACCENT),
        ("GRID", (0, 0), (-1, -1), 0.4, BORDER_GREY),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
    ]

    for item in items:
        data.append([Paragraph(item, cell_style, bulletText="\u2022")])

    style_cmds.append(("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, ROW_ALT_BG]))

    t = Table(data, colWidths=[CONTENT_WIDTH])
    t.setStyle(TableStyle(style_cmds))
    return t


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