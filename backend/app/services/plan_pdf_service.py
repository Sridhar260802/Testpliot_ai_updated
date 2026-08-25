"""
PDF report generators used by the plan-tier endpoints (app/routers/plans.py).

Kept separate from app/services/pdf_service.py (which powers the legacy
/website/report and /report endpoints) so that Basic/Standard reports only
ever show the checks that actually ran for that tier - no "0 broken links /
100 security score" sections implying a check happened when it didn't.
"""

from datetime import datetime
from xml.sax.saxutils import escape as _xml_escape

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.units import inch, mm
from reportlab.lib.styles import ParagraphStyle

from app.services.pdf_service import create_styles, get_grade, add_page_number
from app.services.security_testing import SEVERITY_COLORS, severity_rank
from app.services.report_template import (
    build_report_header,
    section_heading,
    summary_scores_table,
    functional_summary_bar,
    module_status_table,
    stat_grid_table,
    param_value_table,
    footer_note,
    OLIVE_ACCENT,
    OLIVE_LIGHT_BG,
    ROW_ALT_BG,
    BORDER_GREY,
)
from app.services.website_ai_findings_service import (
    collect_standard_issues,
    collect_premium_issues,
    ai_findings,
    remediation_priority,
)


def _safe(value):
    """
    Escapes dynamic text before it goes inside a Paragraph().

    ReportLab's Paragraph treats its string as a small XML dialect - any
    stray '<', '>', or bare '&' in real-world data (a URL query string
    like '...&w=135&output=webp', a finding title copied from a scan
    result, an LLM-authored fix_recommendation, etc.) is parsed as a tag
    or entity. An unmatched '<' is exactly what produced:

        ValueError: paraparser: syntax error: parse ended with 1
        unclosed tags

    Every place in this module that interpolates scan/AI-generated text
    into a Paragraph f-string needs to escape that text first - the
    literal "<b>", "</b>", "&bull;", "&nbsp;" etc. we author ourselves
    stay as-is since we still want those tags to render as tags.
    """
    return _xml_escape("" if value is None else str(value))


def _status_line(label, score):
    grade = get_grade(score)
    return f"<b>{label} :</b> {score}/100 (Grade {grade})"


_DETAIL_LIST_KEYS = [
    "details",
    "issues",
    "failed_items",
    "failed_links",
    "failed_buttons",
    "broken_links",
    "broken_image_details",
    "duplicate_details",
    "hidden_image_details",
    "small_image_details",
    "missing_alt_details",
]


def _extract_failure_details(result, limit=10):
    """
    Pull the concrete failing items (e.g. which link/button/image) out of a
    module result, instead of just the one-line summary in "issue". Each
    test module names its detail list differently, so we check every field
    name that's actually used across the functional test modules.
    """

    items = []

    for key in _DETAIL_LIST_KEYS:

        value = result.get(key)

        if not isinstance(value, list) or not value:
            continue

        for entry in value:

            if isinstance(entry, dict):

                target = (
                    entry.get("url")
                    or entry.get("link")
                    or entry.get("src")
                    or entry.get("element")
                    or entry.get("selector")
                )

                reason = (
                    entry.get("status")
                    or entry.get("reason")
                    or entry.get("error")
                )

                if target:
                    text = str(target)
                    if reason:
                        text += f" ({reason})"
                elif entry:
                    text = ", ".join(
                        f"{k}: {v}" for k, v in entry.items()
                    )
                else:
                    continue

            else:
                text = str(entry)

            items.append(text)

    seen = set()
    unique_items = []

    for item in items:
        if item not in seen:
            seen.add(item)
            unique_items.append(item)

    return unique_items[:limit], len(unique_items)


def _issues_block(title, issues, normal_style):
    story = [Paragraph(f"<b>{_safe(title)}</b>", normal_style)]

    if not issues:
        story.append(Paragraph("No issues detected.", normal_style))
    else:
        for issue in issues:
            story.append(Paragraph(f"&bull; {_safe(issue)}", normal_style))

    story.append(Spacer(1, 0.15 * inch))
    return story


def _p_cell(text, style):
    """Escape and wrap arbitrary text safely in a Paragraph for table cells."""
    if text is None:
        text = ""
    text = str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return Paragraph(text, style)


def _severity_badge_cell(severity, style):
    color = SEVERITY_COLORS.get(str(severity).upper(), "#546E7A")
    return Paragraph(f'<font color="{color}"><b>{severity}</b></font>', style)


def _ai_root_cause_section(issues, depth, normal):
    """Renders the deterministic 'AI Root Cause + Fix Recommendation'
    section - same layout as the mobile app report's AI Root Cause
    section - instead of dropping raw LLM text into the PDF."""
    story = []
    findings = ai_findings(issues, depth=depth)

    if not findings:
        story.append(Paragraph("No issues were found that require a fix recommendation.", normal))
        return story

    for finding in findings:
        story.append(Paragraph(f"<b>[{_safe(finding['severity'])}] {_safe(finding['title'])}</b>", normal))
        if "root_cause" in finding and "fix_recommendation" in finding:
            story.append(Paragraph(f"<b>Root cause:</b> {_safe(finding['root_cause'])}", normal))
            story.append(Paragraph(f"<b>Fix:</b> {_safe(finding['fix_recommendation'])}", normal))
        else:
            story.append(Paragraph(f"<b>Recommendation:</b> {_safe(finding.get('recommendation', ''))}", normal))
        story.append(Spacer(1, 0.1 * inch))

    return story


def _remediation_priority_section(issues, normal):
    """Renders the 'Remediation Priority' table - same layout/columns as
    the mobile app report's Remediation Priority section."""
    story = []
    ranked = remediation_priority(issues)

    if not ranked:
        story.append(Paragraph("No outstanding items to prioritize.", normal))
        return story

    cell_style = ParagraphStyle("RemCell", parent=normal, fontSize=8.2, leading=10.2)
    cell_bold = ParagraphStyle("RemCellBold", parent=cell_style, fontName="Helvetica-Bold")

    table_data = [[
        _p_cell("#", cell_bold), _p_cell("Severity", cell_bold),
        _p_cell("Finding", cell_bold), _p_cell("Recommended Action", cell_bold),
    ]]
    for idx, r in enumerate(ranked, start=1):
        table_data.append([
            _p_cell(idx, cell_style),
            _severity_badge_cell(r["severity"], cell_bold),
            _p_cell(r["title"], cell_style),
            _p_cell(r["recommended_action"], cell_style),
        ])

    t = Table(table_data, colWidths=[18 * mm, 26 * mm, 82 * mm, 44 * mm], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#495B16")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CFD8DC")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F7FA")]),
    ]))
    story.append(t)
    return story


def _full_security_section(security, heading, normal):
    """
    Builds the FULL detailed security audit section (SSL/TLS, DNS/DNSSEC/
    WHOIS, all failing issues, all passed checks, sensitive path
    enumeration, cookie security) - the same level of detail as the
    standalone security_testing.generate_security_pdf report - so it can
    be embedded directly into the Premium combined report.
    """
    story = []

    cell_style = ParagraphStyle("PremSecCell", parent=normal, fontSize=7.6, leading=9.6)
    cell_bold = ParagraphStyle("PremSecCellBold", parent=cell_style, fontName="Helvetica-Bold")

    status = security.get("status", "N/A")
    summary = security.get("summary", {})

    story.append(Paragraph("Security Audit", heading))
    story.append(
        param_value_table(
            [
                ("Status", status),
                ("Total Checks", summary.get("total_checks", 0)),
                ("Passed", summary.get("passed_checks", 0)),
                ("Failed", summary.get("failed_checks", 0)),
                ("Critical", summary.get("critical", 0)),
                ("High", summary.get("high", 0)),
                ("Medium", summary.get("medium", 0)),
                ("Low", summary.get("low", 0)),
            ],
            header=("Parameter", "Result"),
        )
    )
    story.append(Spacer(1, 0.12 * inch))
    story.append(
        Paragraph(
            "Covers: SSL/TLS audit, SSL certificate validation, TLS cipher "
            "analysis, security headers, cookie security, CORS, HTTP/HTTPS "
            "audit, HTTP methods, sensitive paths, mixed content, "
            "cache-control and information disclosure.",
            normal,
        )
    )
    story.append(Spacer(1, 0.15 * inch))

    # ---- SSL / TLS ----
    ssl_data = security.get("ssl_tls", {})
    certificate = ssl_data.get("certificate", {})
    san = certificate.get("san") or []
    if ssl_data:
        story.append(Paragraph("SSL / TLS &amp; Certificate Audit", heading))
        ssl_table_data = [
            [_p_cell("Parameter", cell_bold), _p_cell("Result", cell_bold)],
            [_p_cell("TLS Version", cell_style), _p_cell(ssl_data.get("tls_version", "N/A"), cell_style)],
            [_p_cell("Cipher Suite", cell_style), _p_cell(ssl_data.get("cipher", "N/A"), cell_style)],
            [_p_cell("Hostname Verification", cell_style),
             _severity_badge_cell("PASS", cell_bold) if certificate.get("hostname_match") else _severity_badge_cell("FAIL", cell_bold)],
            [_p_cell("Self-Signed", cell_style), _p_cell("YES" if certificate.get("self_signed") else "NO", cell_style)],
            [_p_cell("Valid From", cell_style), _p_cell(certificate.get("not_before", "N/A"), cell_style)],
            [_p_cell("Valid Until", cell_style), _p_cell(certificate.get("not_after", "N/A"), cell_style)],
            [_p_cell("Days Remaining", cell_style), _p_cell(certificate.get("days_remaining", "N/A"), cell_style)],
            [_p_cell("Issuer", cell_style), _p_cell(certificate.get("issuer", "N/A"), cell_style)],
            [_p_cell("Subject", cell_style), _p_cell(certificate.get("subject", "N/A"), cell_style)],
            [_p_cell("Subject Alt. Names (SAN)", cell_style), _p_cell(", ".join(san) or "N/A", cell_style)],
        ]
        t = Table(ssl_table_data, colWidths=[45 * mm, 125 * mm], repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#759123")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CFD8DC")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F7FA")]),
        ]))
        story.append(t)
        story.append(Spacer(1, 0.15 * inch))

    # ---- DNS / DNSSEC / WHOIS ----
    dns_data = security.get("dns", {})
    dnssec_data = security.get("dnssec", {})
    whois_data = security.get("whois", {})
    if dns_data or dnssec_data or whois_data:
        story.append(Paragraph("DNS, DNSSEC &amp; Domain Audit", heading))
        dns_table_data = [
            [_p_cell("Parameter", cell_bold), _p_cell("Result", cell_bold)],
            [_p_cell("A Records", cell_style), _p_cell(", ".join(dns_data.get("A", [])) or "N/A", cell_style)],
            [_p_cell("AAAA Records", cell_style), _p_cell(", ".join(dns_data.get("AAAA", [])) or "N/A", cell_style)],
            [_p_cell("MX Records", cell_style), _p_cell(", ".join(dns_data.get("MX", [])) or "N/A", cell_style)],
            [_p_cell("NS Records", cell_style), _p_cell(", ".join(dns_data.get("NS", [])) or "N/A", cell_style)],
            [_p_cell("CAA Records", cell_style), _p_cell(", ".join(dns_data.get("CAA", [])) or "None (finding)", cell_style)],
            [_p_cell("DNSSEC Enabled", cell_style), _p_cell("YES" if dnssec_data.get("enabled") else "NO", cell_style)],
            [_p_cell("WHOIS Registrar", cell_style), _p_cell(whois_data.get("registrar", "N/A"), cell_style)],
            [_p_cell("Domain Expiration", cell_style), _p_cell(whois_data.get("expiration_date", "N/A"), cell_style)],
            [_p_cell("Days To Expiry", cell_style), _p_cell(whois_data.get("days_to_expiry", "N/A"), cell_style)],
        ]
        t = Table(dns_table_data, colWidths=[45 * mm, 125 * mm], repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#8D6E63")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CFD8DC")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F7FA")]),
        ]))
        story.append(t)
        story.append(Spacer(1, 0.15 * inch))

    # ---- ALL FAILING ISSUES (no cap) ----
    issues_sorted = sorted(security.get("issues", []), key=lambda i: -severity_rank(i.get("severity")))
    story.append(Paragraph("Security Issues &amp; Recommendations", heading))
    if issues_sorted:
        failed_data = [[_p_cell("Severity", cell_bold), _p_cell("Check", cell_bold),
                         _p_cell("Details", cell_bold), _p_cell("Recommendation", cell_bold)]]
        for i in issues_sorted:
            failed_data.append([
                _severity_badge_cell(i.get("severity", ""), cell_bold),
                _p_cell(i.get("title", ""), cell_style),
                _p_cell(i.get("details", ""), cell_style),
                _p_cell(i.get("recommendation", ""), cell_style),
            ])
        t = Table(failed_data, colWidths=[18 * mm, 38 * mm, 62 * mm, 52 * mm], repeatRows=1)
        style_cmds = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(SEVERITY_COLORS["CRITICAL"])),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CFD8DC")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]
        for idx, i in enumerate(issues_sorted, start=1):
            if severity_rank(i.get("severity")) >= 3:
                style_cmds.append(("BACKGROUND", (0, idx), (-1, idx), colors.HexColor("#FDEDEE")))
        t.setStyle(TableStyle(style_cmds))
        story.append(t)
    else:
        story.append(Paragraph("No failing checks were identified.", normal))
    story.append(Spacer(1, 0.15 * inch))

    # ---- ALL PASSED CHECKS ----
    passed = security.get("passed_checks", [])
    story.append(Paragraph("Successful Security Checks", heading))
    if passed:
        success_data = [[_p_cell("Check", cell_bold), _p_cell("Severity", cell_bold), _p_cell("Details", cell_bold)]]
        for c in passed:
            success_data.append([
                _p_cell(c.get("check", ""), cell_style),
                _severity_badge_cell(c.get("severity", ""), cell_bold),
                _p_cell(c.get("details", ""), cell_style),
            ])
        t = Table(success_data, colWidths=[48 * mm, 20 * mm, 102 * mm], repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(SEVERITY_COLORS["INFO"])),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CFD8DC")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F7FA")]),
        ]))
        story.append(t)
    else:
        story.append(Paragraph("No checks passed during this scan.", normal))
    story.append(Spacer(1, 0.15 * inch))

    # ---- SENSITIVE PATHS ----
    sensitive_paths = security.get("sensitive_paths", [])
    story.append(Paragraph("Sensitive Path Enumeration", heading))
    if sensitive_paths:
        path_data = [[_p_cell("Path", cell_bold), _p_cell("HTTP Status", cell_bold),
                      _p_cell("Risk", cell_bold), _p_cell("Exposed", cell_bold)]]
        for item in sensitive_paths:
            path_data.append([
                _p_cell(item.get("path", ""), cell_style),
                _p_cell(item.get("status", ""), cell_style),
                _p_cell(item.get("risk", ""), cell_style),
                _severity_badge_cell("YES" if item.get("exposed") else "NO",
                                      cell_bold if item.get("exposed") else cell_style),
            ])
        t = Table(path_data, colWidths=[70 * mm, 35 * mm, 30 * mm, 35 * mm], repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#495B16")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CFD8DC")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F7FA")]),
        ]))
        story.append(t)
    else:
        story.append(Paragraph("No sensitive paths were tested during this scan.", normal))
    story.append(Spacer(1, 0.15 * inch))

    # ---- COOKIES ----
    cookies = security.get("cookies", [])
    story.append(Paragraph("Cookie Security", heading))
    if cookies:
        cookie_data = [[_p_cell("Cookie", cell_bold), _p_cell("Secure", cell_bold),
                         _p_cell("HttpOnly", cell_bold), _p_cell("SameSite", cell_bold)]]
        for c in cookies:
            cookie_data.append([
                _p_cell(c.get("name", ""), cell_style),
                _p_cell(str(c.get("secure", False)), cell_style),
                _p_cell(str(c.get("http_only", False)), cell_style),
                _p_cell(str(c.get("same_site", "")), cell_style),
            ])
        t = Table(cookie_data, colWidths=[60 * mm, 35 * mm, 35 * mm, 40 * mm], repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#495B16")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CFD8DC")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F7FA")]),
        ]))
        story.append(t)
    else:
        story.append(Paragraph(
            "No cookies were observed during this scan - the initial response did not include any "
            "<b>Set-Cookie</b> headers, so there is nothing to assess here.",
            normal
        ))

    return story


def generate_basic_pdf_report(data, filename="Basic_Website_Report.pdf"):
    """
    data keys expected: url, website (test_website result), seo, performance,
    accessibility, content_validation, image_validation
    """

    doc = SimpleDocTemplate(filename)
    styles = create_styles()
    title, heading, normal = styles["title"], styles["heading"], styles["normal"]

    story = []

    website = data.get("website", {})
    seo = data.get("seo", {})
    performance = data.get("performance", {})
    accessibility = data.get("accessibility", {})
    content = data.get("content_validation", {})
    image = data.get("image_validation", {})

    story.extend(
        build_report_header(
            subtitle_text="Professional Website Audit &amp; Analysis - Basic Plan",
            url=data.get("url", ""),
            generated_str=datetime.now().strftime("%d-%m-%Y %H:%M:%S"),
            plan_level="Basic",
        )
    )

    story.append(section_heading("1. Summary Scores"))
    story.append(Spacer(1, 0.12 * inch))
    availability_score = 100 if str(website.get("test_status", "")).upper() == "PASS" else 0
    story.append(
        summary_scores_table(
            [
                ("Availability (HTTP " + str(website.get("status_code", "N/A")) + ")", availability_score, None),
                ("SEO Score", seo.get("seo_score", 0), get_grade(seo.get("seo_score", 0))),
                ("Performance Score", performance.get("performance_score", 0), get_grade(performance.get("performance_score", 0))),
                ("Accessibility Score", accessibility.get("accessibility_score", 0), get_grade(accessibility.get("accessibility_score", 0))),
                ("Content Score", content.get("content_score", 0), get_grade(content.get("content_score", 0))),
                ("Image Score", image.get("image_score", 0), get_grade(image.get("image_score", 0))),
            ]
        )
    )
    story.append(Spacer(1, 0.25 * inch))

    story.append(section_heading("2. Basic SEO Findings"))
    story.append(Spacer(1, 0.1 * inch))
    story.extend(_issues_block("SEO Issues", seo.get("issues", []), normal))

    story.append(section_heading("3. Basic Accessibility Findings"))
    story.append(Spacer(1, 0.1 * inch))
    story.extend(
        _issues_block("Accessibility Issues", accessibility.get("issues", []), normal)
    )

    story.append(section_heading("4. Basic Performance Findings"))
    story.append(Spacer(1, 0.1 * inch))
    story.extend(
        _issues_block("Performance Issues", performance.get("issues", []), normal)
    )

    story.append(section_heading("5. Basic Content Validation"))
    story.append(Spacer(1, 0.1 * inch))
    story.extend(_issues_block("Content Issues", content.get("issues", []), normal))

    story.append(section_heading("6. Basic Image Validation"))
    story.append(Spacer(1, 0.1 * inch))
    story.extend(_issues_block("Image Issues", image.get("issues", []), normal))

    story.append(Spacer(1, 0.15 * inch))
    story.append(
        footer_note(
            "Upgrade to the Standard plan for functional testing, advanced SEO, "
            "advanced accessibility, API validation and AI-powered recommendations. "
            "Upgrade to Premium for a full security audit.",
            normal,
        )
    )

    doc.build(story, onFirstPage=add_page_number, onLaterPages=add_page_number)

    return filename


def generate_premium_pdf_report(data, filename="Premium_Website_Report.pdf"):
    """
    Premium report = everything in the Standard report (functional testing,
    advanced SEO, advanced accessibility, performance, AI recommendations)
    PLUS a full website audit: Security, Content, UX, CRO and Technical
    sections, in a single combined PDF.

    data keys expected: url, website, seo (advanced), accessibility, performance,
    functional, ai_suggestions, security (security_testing.security_audit result),
    content (content_audit_service.content_audit result),
    ux (ux_audit_service.ux_audit result), cro (cro_audit_service.cro_audit result),
    technical (technical_audit_service.technical_audit result)
    """

    doc = SimpleDocTemplate(filename)
    styles = create_styles()
    title, heading, normal = styles["title"], styles["heading"], styles["normal"]

    story = []

    website = data.get("website", {})
    seo = data.get("seo", {})
    performance = data.get("performance", {})
    accessibility = data.get("accessibility", {})
    functional = data.get("functional", {})
    ai_suggestions = data.get("ai_suggestions", "")
    security = data.get("security", {})
    content_audit_data = data.get("content", {})
    ux_audit_data = data.get("ux", {})
    cro_audit_data = data.get("cro", {})
    technical_audit_data = data.get("technical", {})

    story.extend(
        build_report_header(
            subtitle_text="Professional Website Audit &amp; Analysis - Premium Plan",
            url=data.get("url", ""),
            generated_str=datetime.now().strftime("%d-%m-%Y %H:%M:%S"),
            plan_level="Premium",
        )
    )

    story.append(section_heading("1. Summary Scores"))
    story.append(Spacer(1, 0.12 * inch))
    story.append(
        summary_scores_table(
            [
                ("Website Health", website.get("health_score", 0), None),
                ("Advanced SEO Score", seo.get("seo_score", 0), get_grade(seo.get("seo_score", 0))),
                ("Accessibility Score", accessibility.get("accessibility_score", 0), get_grade(accessibility.get("accessibility_score", 0))),
                ("Performance Score", performance.get("performance_score", 0), get_grade(performance.get("performance_score", 0))),
                ("Functional Score", functional.get("functional_score", 0), get_grade(functional.get("functional_score", 0))),
                ("Security Score", security.get("security_score", 0), get_grade(security.get("security_score", 0))),
                ("Content Score", content_audit_data.get("content_score", 0), get_grade(content_audit_data.get("content_score", 0))),
                ("UX Score", ux_audit_data.get("ux_score", 0), get_grade(ux_audit_data.get("ux_score", 0))),
                ("CRO Score", cro_audit_data.get("cro_score", 0), get_grade(cro_audit_data.get("cro_score", 0))),
                ("Technical Score", technical_audit_data.get("technical_score", 0), get_grade(technical_audit_data.get("technical_score", 0))),
            ]
        )
    )
    story.append(Spacer(1, 0.25 * inch))

    # ---------------- STANDARD SECTION: FUNCTIONAL TESTING ----------------
    tested_modules = functional.get(
        "tested_modules",
        functional.get("passed", 0) + functional.get("failed", 0),
    )

    story.append(section_heading("2. Functional Testing Summary"))
    story.append(Spacer(1, 0.12 * inch))
    story.append(
        functional_summary_bar(
            tested_modules,
            functional.get("total_modules", 0),
            functional.get("passed", 0),
            functional.get("failed", 0),
            functional.get("partial", 0),
            functional.get("skipped", 0),
        )
    )
    story.append(Spacer(1, 0.1 * inch))
    story.append(
        Paragraph(
            "Covers: navigation &amp; link testing, forms &amp; validation, "
            "authentication testing, responsive testing, browser compatibility, "
            "broken resource testing, console error detection and API validation.",
            normal,
        )
    )
    story.append(Spacer(1, 0.15 * inch))

    module_rows = [
        (
            m.get("module", "Module"),
            m.get("status", "N/A"),
            m.get("issue", "") if m.get("status") == "FAIL" else "",
        )
        for m in functional.get("results", [])
    ]
    if module_rows:
        story.append(module_status_table(module_rows))
        story.append(Spacer(1, 0.15 * inch))

    for module_result in functional.get("results", []):
        module_name = module_result.get("module", "Module")
        status = module_result.get("status", "N/A")

        if status == "FAIL":

            detail_items, total_found = _extract_failure_details(module_result)

            if detail_items:
                story.append(
                    Paragraph(f"<b>{_safe(module_name)} - failing items</b>", normal)
                )

            for item in detail_items:
                story.append(
                    Paragraph(f"&nbsp;&nbsp;&nbsp;&nbsp;- {_safe(item)}", normal)
                )

            if total_found > len(detail_items):
                remaining = total_found - len(detail_items)
                story.append(
                    Paragraph(
                        f"&nbsp;&nbsp;&nbsp;&nbsp;...and {remaining} more.",
                        normal,
                    )
                )

    story.append(Spacer(1, 0.25 * inch))

    # ---------------- PREMIUM SECTION: SECURITY AUDIT (full detail) ----------------
    story.append(section_heading("3. Security &amp; Infrastructure Audit"))
    story.append(Spacer(1, 0.12 * inch))
    story.extend(_full_security_section(security, heading, normal))
    story.append(Spacer(1, 0.25 * inch))

    # ---------------- PREMIUM SECTION: CONTENT AUDIT ----------------
    story.append(section_heading("4. Content Audit"))
    story.append(Spacer(1, 0.12 * inch))
    story.append(
        param_value_table(
            [
                ("Word Count", content_audit_data.get("word_count", 0)),
                ("Headings", content_audit_data.get("heading_count", 0)),
                (
                    "Readability",
                    f"{content_audit_data.get('readability_score', 0)} "
                    f"({content_audit_data.get('readability_label', 'N/A')})",
                ),
                ("Duplicate Paragraphs", content_audit_data.get("duplicate_paragraph_count", 0)),
            ],
            header=("Metric", "Value"),
        )
    )
    story.append(Spacer(1, 0.12 * inch))
    story.append(
        Paragraph(
            "Covers: thin/duplicate content, content quality &amp; relevance, "
            "grammar &amp; readability, and content opportunities.",
            normal,
        )
    )
    for issue in content_audit_data.get("issues", []):
        story.append(Paragraph(f"&bull; {_safe(issue)}", normal))
    story.append(Spacer(1, 0.25 * inch))

    # ---------------- PREMIUM SECTION: UX AUDIT ----------------
    story.append(section_heading("5. User Experience (UX) Audit"))
    story.append(Spacer(1, 0.12 * inch))
    story.append(
        param_value_table(
            [
                ("Navigation Present", ux_audit_data.get("has_navigation", False)),
                ("Footer Present", ux_audit_data.get("has_footer", False)),
                ("Clear CTA Found", ux_audit_data.get("has_cta", False)),
                ("Mobile Horizontal Overflow", ux_audit_data.get("mobile_horizontal_overflow", "N/A")),
                ("Mobile Nav Visible", ux_audit_data.get("mobile_navigation_visible", "N/A")),
            ],
            header=("Metric", "Value"),
        )
    )
    story.append(Spacer(1, 0.12 * inch))
    story.append(
        Paragraph(
            "Covers: navigation &amp; menu structure, mobile responsiveness, "
            "readability, accessibility, CTAs and overall usability.",
            normal,
        )
    )
    for issue in ux_audit_data.get("issues", []):
        story.append(Paragraph(f"&bull; {_safe(issue)}", normal))
    story.append(Spacer(1, 0.25 * inch))

    # ---------------- PREMIUM SECTION: CRO AUDIT ----------------
    story.append(section_heading("6. Conversion Rate Optimization (CRO) Audit"))
    story.append(Spacer(1, 0.12 * inch))
    story.append(
        param_value_table(
            [
                ("CTA Above the Fold", cro_audit_data.get("cta_above_fold", False)),
                (
                    "Forms Found",
                    f"{cro_audit_data.get('form_count', 0)} "
                    f"(Poorly Labeled: {cro_audit_data.get('poorly_labeled_form_count', 0)})",
                ),
                ("Looks Like E-commerce", cro_audit_data.get("looks_like_ecommerce", False)),
                (
                    "Analytics Detected",
                    ", ".join(cro_audit_data.get("analytics_detected", [])) or "None",
                ),
            ],
            header=("Metric", "Value"),
        )
    )
    story.append(Spacer(1, 0.12 * inch))
    story.append(
        Paragraph(
            "Covers: landing page effectiveness, form usability, checkout "
            "process, CTA placement and analytics/conversion tracking.",
            normal,
        )
    )
    for issue in cro_audit_data.get("issues", []):
        story.append(Paragraph(f"&bull; {_safe(issue)}", normal))
    story.append(Spacer(1, 0.25 * inch))

    # ---------------- PREMIUM SECTION: TECHNICAL AUDIT ----------------
    story.append(section_heading("7. Technical Audit"))
    story.append(Spacer(1, 0.12 * inch))
    crawl = technical_audit_data.get("crawl", {})
    caching = technical_audit_data.get("caching_and_compression", {})
    vitals = technical_audit_data.get("core_web_vitals", {})
    story.append(
        param_value_table(
            [
                ("Internal Links Checked", crawl.get("links_checked", 0)),
                ("Broken Links", len(crawl.get("broken_links", []))),
                ("Redirected Links", len(crawl.get("redirect_links", []))),
                ("Cache-Control Set", caching.get("has_cache_control", False)),
                ("Compressed", caching.get("is_compressed", False)),
                ("Largest Contentful Paint", f"{vitals.get('largest_contentful_paint_ms', 'N/A')} ms"),
                ("Cumulative Layout Shift", vitals.get("cumulative_layout_shift", "N/A")),
            ],
            header=("Metric", "Value"),
        )
    )
    story.append(Spacer(1, 0.12 * inch))
    story.append(
        Paragraph(
            "Covers: HTTPS implementation, redirects, structured data, "
            "canonical tags, crawlability, caching/compression and Core Web Vitals.",
            normal,
        )
    )
    for issue in technical_audit_data.get("issues", []):
        story.append(Paragraph(f"&bull; {_safe(issue)}", normal))
    story.append(Spacer(1, 0.25 * inch))

    # ---------------- AI ROOT CAUSE + FIX RECOMMENDATION ----------------
    premium_issues = collect_premium_issues(data)
    story.append(section_heading("8. AI Root Cause + Fix Recommendation"))
    story.append(Spacer(1, 0.12 * inch))
    story.extend(_ai_root_cause_section(premium_issues, depth="premium", normal=normal))
    story.append(Spacer(1, 0.12 * inch))

    # ---------------- REMEDIATION PRIORITY ----------------
    story.append(section_heading("9. Remediation Priority"))
    story.append(Spacer(1, 0.12 * inch))
    story.extend(_remediation_priority_section(premium_issues, normal))
    story.append(Spacer(1, 0.22 * inch))

    doc.build(story, onFirstPage=add_page_number, onLaterPages=add_page_number)

    return filename


def generate_standard_pdf_report(data, filename="Standard_Website_Report.pdf"):
    """
    data keys expected: url, website, seo (advanced), accessibility, performance,
    functional (functional_testing_service.functional_testing result),
    ai_suggestions
    """

    doc = SimpleDocTemplate(filename)
    styles = create_styles()
    title, heading, normal = styles["title"], styles["heading"], styles["normal"]

    story = []

    website = data.get("website", {})
    seo = data.get("seo", {})
    performance = data.get("performance", {})
    accessibility = data.get("accessibility", {})
    functional = data.get("functional", {})
    ai_suggestions = data.get("ai_suggestions", "")

    story.extend(
        build_report_header(
            subtitle_text="Professional Website Audit &amp; Analysis - Standard Plan",
            url=data.get("url", ""),
            generated_str=datetime.now().strftime("%d-%m-%Y %H:%M:%S"),
            plan_level="Standard",
        )
    )

    story.append(section_heading("1. Summary Scores"))
    story.append(Spacer(1, 0.12 * inch))
    story.append(
        summary_scores_table(
            [
                ("Website Health", website.get("health_score", 0), None),
                ("Advanced SEO Score", seo.get("seo_score", 0), get_grade(seo.get("seo_score", 0))),
                ("Accessibility Score", accessibility.get("accessibility_score", 0), get_grade(accessibility.get("accessibility_score", 0))),
                ("Performance Score", performance.get("performance_score", 0), get_grade(performance.get("performance_score", 0))),
                ("Functional Score", functional.get("functional_score", 0), get_grade(functional.get("functional_score", 0))),
            ]
        )
    )
    story.append(Spacer(1, 0.25 * inch))

    tested_modules = functional.get(
        "tested_modules",
        functional.get("passed", 0) + functional.get("failed", 0),
    )

    story.append(section_heading("2. Functional Testing Summary"))
    story.append(Spacer(1, 0.12 * inch))
    story.append(
        functional_summary_bar(
            tested_modules,
            functional.get("total_modules", 0),
            functional.get("passed", 0),
            functional.get("failed", 0),
            functional.get("partial", 0),
            functional.get("skipped", 0),
        )
    )
    story.append(Spacer(1, 0.1 * inch))
    story.append(
        Paragraph(
            "Covers: navigation &amp; link testing, forms &amp; validation, "
            "authentication testing, responsive testing, browser compatibility, "
            "broken resource testing, console error detection and API validation.",
            normal,
        )
    )
    story.append(Spacer(1, 0.15 * inch))

    module_rows = [
        (
            m.get("module", "Module"),
            m.get("status", "N/A"),
            m.get("issue", "") if m.get("status") == "FAIL" else "",
        )
        for m in functional.get("results", [])
    ]
    if module_rows:
        story.append(module_status_table(module_rows))
        story.append(Spacer(1, 0.15 * inch))

    for module_result in functional.get("results", []):
        module_name = module_result.get("module", "Module")
        status = module_result.get("status", "N/A")

        if status == "FAIL":

            detail_items, total_found = _extract_failure_details(module_result)

            if detail_items:
                story.append(
                    Paragraph(f"<b>{_safe(module_name)} - failing items</b>", normal)
                )

            for item in detail_items:
                story.append(
                    Paragraph(f"&nbsp;&nbsp;&nbsp;&nbsp;- {_safe(item)}", normal)
                )

            if total_found > len(detail_items):
                remaining = total_found - len(detail_items)
                story.append(
                    Paragraph(
                        f"&nbsp;&nbsp;&nbsp;&nbsp;...and {remaining} more.",
                        normal,
                    )
                )

    story.append(Spacer(1, 0.25 * inch))
    standard_issues = collect_standard_issues(data)
    story.append(section_heading("3. AI Root Cause + Fix Recommendation"))
    story.append(Spacer(1, 0.1 * inch))
    story.extend(_ai_root_cause_section(standard_issues, depth="standard", normal=normal))

    story.append(Spacer(1, 0.15 * inch))
    story.append(section_heading("4. Remediation Priority"))
    story.append(Spacer(1, 0.1 * inch))
    story.extend(_remediation_priority_section(standard_issues, normal))

    story.append(Spacer(1, 0.15 * inch))
    story.append(
        footer_note(
            "Upgrade to Premium for a full security audit (SSL/TLS, headers, "
            "cookies, CORS, sensitive paths and more) delivered as JSON and PDF.",
            normal,
        )
    )

    doc.build(story, onFirstPage=add_page_number, onLaterPages=add_page_number)

    return filename