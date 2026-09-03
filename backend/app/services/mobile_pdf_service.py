"""
Mobile App Security PDF report generator.

Uses the SAME shared TestPilot report template as the website reports
(app/services/report_template.py, plan_pdf_service.py) - logo, olive
brand colors, the same header block and section-heading style, the same
grid/zebra-stripe table language - instead of its own one-off dark-grey
layout. Only the DATA differs; a mobile report now reads as a sibling of
the Basic/Standard/Premium website reports rather than a different
product.

Section coverage mirrors the full mobile_app_testing_engine.py output
shape (Executive Summary through Final Score), plus two additions wired
in alongside the certificate/leakage checks added to the engine:

    - Signing Certificate / Provisioning Profile: renders cert_info
      (Android) or provisioning_profile (iOS) including days_until_expiry,
      so an expired/soon-to-expire signing identity is visible in the
      report body, not just buried in the Findings list.
    - Data Leakage Risk: renders the engine's consolidated
      data_leakage_summary (risk_level + signal list), pulled together
      from secrets/URLs/storage/crypto scans that already ran, so a
      reviewer gets a single "is this app likely leaking data" verdict
      instead of piecing it together from five separate sections.

Every section below is conditional on the corresponding key actually
being present in `analysis`, so a Basic-depth scan still renders a short
report, a Standard-depth scan picks up the mid-tier sections, and a
Premium-depth scan renders the full report end to end. Sections that
require a dynamic/instrumented run (Dynamic Test Results, Crash/ANR,
Screenshots & Evidence) render an honest "not performed" note when no
dynamic_run data was supplied to the engine, instead of being silently
skipped - the plan is paying for the section to exist and say why it's
empty.
"""

import os
import time
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch, mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

from app.services.pdf_service import add_page_number
from app.services.report_template import (
    build_report_header,
    section_heading,
    score_severity_table,
    key_value_table,
    findings_table,
    footer_note,
    CONTENT_WIDTH,
    OLIVE_ACCENT,
    ROW_ALT_BG,
    BORDER_GREY,
)

REPORTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "reports")
os.makedirs(REPORTS_DIR, exist_ok=True)

# Data Leakage Risk badge colors, same visual language as score_severity_table.
_RISK_COLORS = {
    "High": colors.HexColor("#B3261E"),
    "Medium": colors.HexColor("#B36B00"),
    "Low": colors.HexColor("#2E7D32"),
}


def _normal_style():
    return ParagraphStyle(
        "MobileNormal", fontName="Helvetica", fontSize=9.5, leading=13,
        textColor=colors.HexColor("#333333"),
    )


def _bold_label_style():
    return ParagraphStyle(
        "MobileBoldLabel", fontName="Helvetica-Bold", fontSize=9.5, leading=13,
        textColor=colors.HexColor("#333333"),
    )


def _bullets(story, normal_style, items):
    for item in items:
        story.append(Paragraph(f"&bull; {item}", normal_style))


def _generic_table(headers, rows, col_widths):
    """N-column table in the same visual language as _exported_components_table
    below - shared by several of the newer sections (SDK advisories, AI
    findings, remediation priority) that need more than 2 columns."""
    cell_style = ParagraphStyle("GenCell", fontName="Helvetica", fontSize=8.5, leading=11)
    header_cell = ParagraphStyle("GenHeader", parent=cell_style, fontName="Helvetica-Bold", textColor=colors.white)

    data = [[Paragraph(h, header_cell) for h in headers]]
    for row in rows:
        data.append([Paragraph(str(c), cell_style) for c in row])

    t = Table(data, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), OLIVE_ACCENT),
        ("GRID", (0, 0), (-1, -1), 0.4, BORDER_GREY),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, ROW_ALT_BG]),
    ]))
    return t


def _exported_components_table(exported):
    """3-column Type | Name | Permission Protected? table - kept as its
    own small builder since key_value_table is 2-column only."""

    rows = []
    for comp_type, items in exported.items():
        for c in items:
            rows.append((comp_type[:-1].title(), c["name"], "Yes" if c["protected_by_permission"] else "No"))

    if not rows:
        return None

    return _generic_table(
        ["Type", "Name", "Permission Protected?"], rows,
        [70, CONTENT_WIDTH - 70 - 120, 120],
    )


def _cert_expiry_label(days):
    """Human-readable expiry label for the Signing Certificate table -
    used for both Android cert_info entries and the iOS provisioning
    profile, which both now carry a days_until_expiry field."""
    if days is None:
        return "Unknown"
    if days < 0:
        return f"Expired {abs(days)} day(s) ago"
    return f"Valid - {days} day(s) remaining"


def _data_leakage_risk_table(summary):
    """Small Risk Level | Signal table for the Data Leakage Risk section.
    Mirrors score_severity_table's badge-style coloring so it reads as
    part of the same report language."""
    risk_level = summary.get("risk_level", "Low")
    badge_color = _RISK_COLORS.get(risk_level, colors.HexColor("#333333"))

    label_style = ParagraphStyle("DLLabel", fontName="Helvetica-Bold", fontSize=10, textColor=colors.white)
    data = [[Paragraph("Data Leakage Risk", label_style), Paragraph(risk_level, label_style)]]
    t = Table(data, colWidths=[CONTENT_WIDTH - 120, 120])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, 0), OLIVE_ACCENT),
        ("BACKGROUND", (1, 0), (1, 0), badge_color),
        ("ALIGN", (1, 0), (1, 0), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
    ]))
    return t


def _section(story, section_num, title):
    story.append(section_heading(f"{section_num}. {title}"))
    story.append(Spacer(1, 0.1 * inch))
    return section_num + 1


def generate_mobile_pdf(analysis: dict, file_name: str) -> str:
    """Builds a PDF summarizing a single mobile app scan and returns the
    path it was written to."""

    normal_style = _normal_style()
    bold_label = _bold_label_style()

    timestamp = int(time.time() * 1000)
    safe_name = "".join(c for c in file_name if c.isalnum() or c in ("_", "-", "."))[:60]
    pdf_path = os.path.join(REPORTS_DIR, f"mobile_{safe_name}_{timestamp}.pdf")

    doc = SimpleDocTemplate(pdf_path, pagesize=A4, topMargin=18 * mm, bottomMargin=18 * mm)
    story = []

    platform = analysis.get("platform", "").capitalize()
    scan_depth = analysis.get("scan_depth", "basic").capitalize()
    overview = analysis.get("overview", {})
    is_android = analysis.get("platform") == "android"

    # -------------------- Header (shared template) --------------------
    story.extend(
        build_report_header(
            title_text=f"MOBILE APP SECURITY REPORT ({platform})",
            subtitle_text=f"Static Security Analysis - {scan_depth} Plan",
            url=file_name,
            id_label="File Name",
            generated_str=datetime.now().strftime("%d-%m-%Y %H:%M:%S"),
            plan_level=scan_depth,
        )
    )

    section_num = 1

    # -------------------- 1. Executive Summary (standard+) --------------------
    exec_summary = analysis.get("executive_summary")
    if exec_summary:
        section_num = _section(story, section_num, "Executive Summary")
        story.append(Paragraph(exec_summary, normal_style))
        story.append(Spacer(1, 0.22 * inch))

    # -------------------- 2. Security Score --------------------
    section_num = _section(story, section_num, "Security Score")
    story.append(score_severity_table(analysis.get("security_score", 0), analysis.get("severity", "Low")))
    story.append(Spacer(1, 0.25 * inch))

    # -------------------- 3. Data Leakage Risk (premium) --------------------
    # Placed right after the headline score so it's one of the first
    # things a reviewer sees, ahead of the section-by-section detail that
    # backs it up (Secrets, Exposed URLs, Storage Security, Cryptography).
    data_leakage = analysis.get("data_leakage_summary")
    if data_leakage:
        section_num = _section(story, section_num, "Data Leakage Risk")
        story.append(_data_leakage_risk_table(data_leakage))
        story.append(Spacer(1, 0.12 * inch))
        signals = data_leakage.get("signals") or []
        if signals:
            story.append(Paragraph("Contributing signals:", bold_label))
            story.append(Spacer(1, 0.05 * inch))
            _bullets(story, normal_style, signals)
        else:
            story.append(Paragraph("No data-leakage indicators found across the secrets, URL, storage, "
                                    "and cryptography scans below.", normal_style))
        story.append(Spacer(1, 0.22 * inch))

    # -------------------- 4. Risk Distribution (standard+) --------------------
    risk_dist = analysis.get("risk_distribution")
    if risk_dist:
        section_num = _section(story, section_num, "Risk Distribution")
        dist_rows = [(sev, str(count)) for sev, count in risk_dist.items() if count]
        if dist_rows:
            story.append(key_value_table(dist_rows, col_widths=[150, CONTENT_WIDTH - 150],
                                          header=["Severity", "Count"]))
        else:
            story.append(Paragraph("No findings at any severity for this scan.", normal_style))
        story.append(Spacer(1, 0.22 * inch))

    # -------------------- App Overview (kept as-is) --------------------
    section_num = _section(story, section_num, "App Overview")
    overview_rows = [(k.replace("_", " ").title(), v) for k, v in overview.items()]
    if overview_rows:
        story.append(key_value_table(overview_rows, col_widths=[150, CONTENT_WIDTH - 150]))
    else:
        story.append(Paragraph("No overview data available.", normal_style))
    story.append(Spacer(1, 0.22 * inch))

    # -------------------- App Architecture (standard+) --------------------
    architecture = analysis.get("app_architecture")
    if architecture:
        section_num = _section(story, section_num, "App Architecture")
        arch_rows = []
        for k, v in architecture.items():
            if isinstance(v, list):
                v = ", ".join(v) if v else "None detected"
            arch_rows.append((k.replace("_", " ").title(), v))
        story.append(key_value_table(arch_rows, col_widths=[180, CONTENT_WIDTH - 180]))
        story.append(Spacer(1, 0.22 * inch))

    # -------------------- Manifest Audit (standard+) --------------------
    manifest_audit = analysis.get("manifest_audit")
    if manifest_audit:
        section_num = _section(story, section_num, "Manifest Audit")
        exported = manifest_audit.get("exported_components")
        scalar_rows = [(k.replace("_", " ").title(), v) for k, v in manifest_audit.items()
                       if k != "exported_components"]
        if scalar_rows:
            story.append(key_value_table(scalar_rows, col_widths=[220, CONTENT_WIDTH - 220]))
            story.append(Spacer(1, 0.12 * inch))
        if exported:
            table = _exported_components_table(exported)
            if table is not None:
                story.append(Paragraph("Exported components:", bold_label))
                story.append(Spacer(1, 0.06 * inch))
                story.append(table)
        story.append(Spacer(1, 0.22 * inch))

    # -------------------- Findings --------------------
    section_num = _section(story, section_num, "Findings")
    issues = analysis.get("issues", [])
    if not issues:
        story.append(Paragraph("No issues flagged at this scan depth.", normal_style))
    else:
        story.append(findings_table(issues))
    story.append(Spacer(1, 0.22 * inch))

    # -------------------- Permission Audit (Android) --------------------
    permissions = analysis.get("permissions")
    if permissions and permissions.get("dangerous"):
        section_num = _section(story, section_num, "Permission Audit")
        has_tier = any("risk_tier" in p for p in permissions["dangerous"])
        if has_tier:
            perm_rows = [(p["permission"], p["description"], p.get("risk_tier", "Low"))
                         for p in permissions["dangerous"]]
            story.append(_generic_table(
                ["Permission", "Access", "Privacy Risk"], perm_rows,
                [200, CONTENT_WIDTH - 200 - 90, 90],
            ))
        else:
            perm_rows = [(p["permission"], p["description"]) for p in permissions["dangerous"]]
            story.append(key_value_table(
                perm_rows, col_widths=[220, CONTENT_WIDTH - 220], header=["Permission", "Access"]
            ))
        story.append(Spacer(1, 0.22 * inch))

    # -------------------- Secrets (premium) --------------------
    secret_scan = analysis.get("secret_scan")
    if secret_scan is not None:
        section_num = _section(story, section_num, "Secrets")
        if secret_scan:
            _bullets(story, normal_style,
                     [f"{label}: {'; '.join(hits)}" for label, hits in secret_scan.items()])
        else:
            story.append(Paragraph("No hardcoded secret patterns detected.", normal_style))
        story.append(Spacer(1, 0.22 * inch))

    # -------------------- Cryptography (premium) --------------------
    crypto_scan = analysis.get("weak_crypto_scan")
    if crypto_scan is not None:
        section_num = _section(story, section_num, "Cryptography")
        if crypto_scan:
            _bullets(story, normal_style,
                     [f"{label}: {'; '.join(hits)}" for label, hits in crypto_scan.items()])
        else:
            story.append(Paragraph("No weak/legacy cryptographic primitives detected.", normal_style))
        story.append(Spacer(1, 0.22 * inch))

    # -------------------- Signing Certificate / Provisioning Profile --------------------
    # Android: analysis["certificates"] (premium) is a list of cert dicts,
    # each now carrying days_until_expiry from the engine's cert-validity
    # check. iOS: analysis["provisioning_profile"] (standard+) carries the
    # same days_until_expiry for the embedded provisioning profile.
    certificates = analysis.get("certificates")
    provisioning_profile = analysis.get("provisioning_profile")
    if certificates or provisioning_profile:
        section_num = _section(story, section_num, "Signing Certificate" if is_android else "Provisioning Profile")
        if is_android and certificates:
            cert_rows = [
                (c.get("subject", "-"), c.get("issuer", "-"), c.get("not_valid_after", "-"),
                 _cert_expiry_label(c.get("days_until_expiry")))
                for c in certificates
            ]
            story.append(_generic_table(
                ["Subject", "Issuer", "Valid Until", "Status"], cert_rows,
                [CONTENT_WIDTH - 260, 90, 80, 90],
            ))
        elif provisioning_profile:
            pp_rows = [
                ("Name", provisioning_profile.get("name")),
                ("Team", provisioning_profile.get("team_name")),
                ("Expiration Date", provisioning_profile.get("expiration_date")),
                ("Status", _cert_expiry_label(provisioning_profile.get("days_until_expiry"))),
                ("get-task-allow", provisioning_profile.get("get_task_allow")),
                ("Provisions All Devices", provisioning_profile.get("provisions_all_devices")),
            ]
            story.append(key_value_table(pp_rows, col_widths=[180, CONTENT_WIDTH - 180]))
        story.append(Spacer(1, 0.22 * inch))

    # -------------------- Network Security --------------------
    network_security = analysis.get("network_security")
    ats = analysis.get("app_transport_security") or {}
    ssl_scan = analysis.get("ssl_tls_scan")
    if network_security or ats or ssl_scan:
        section_num = _section(story, section_num, "Network Security")
        if network_security:
            ns_rows = [(k.replace("_", " ").title(), v) for k, v in network_security.items()]
            story.append(key_value_table(ns_rows, col_widths=[220, CONTENT_WIDTH - 220]))
            story.append(Spacer(1, 0.1 * inch))
        if ats:
            exception_domains = ats.get("exception_domains") or []
            story.append(Paragraph(
                f"Allows Arbitrary Loads: {ats.get('allows_arbitrary_loads')}", normal_style))
            if exception_domains:
                story.append(Paragraph(
                    "ATS exception domains: " + ", ".join(exception_domains), normal_style))
            story.append(Spacer(1, 0.1 * inch))
        if ssl_scan:
            story.append(Paragraph(f"Certificate pinning detected: {ssl_scan.get('pinning_detected')}", normal_style))
            trust_bypass = ssl_scan.get("trust_bypass_indicators")
            if trust_bypass:
                story.append(Paragraph("Trust-validation bypass indicators:", bold_label))
                _bullets(story, normal_style,
                         [f"{label}: {'; '.join(hits)}" for label, hits in trust_bypass.items()])
        story.append(Spacer(1, 0.22 * inch))

    # -------------------- WebView (premium, Android) --------------------
    webview_scan = analysis.get("webview_scan")
    if webview_scan is not None:
        section_num = _section(story, section_num, "WebView")
        if webview_scan:
            _bullets(story, normal_style,
                     [f"{label}: {'; '.join(hits)}" for label, hits in webview_scan.items()])
        else:
            story.append(Paragraph("No risky WebView API usage detected.", normal_style))
        story.append(Spacer(1, 0.22 * inch))

    # -------------------- Deep Links --------------------
    deep_links = analysis.get("deep_links")
    if deep_links:
        section_num = _section(story, section_num, "Deep Links")
        schemes = deep_links.get("schemes")
        if isinstance(schemes, list) and schemes and isinstance(schemes[0], dict):
            # Premium full audit shape: list of dicts.
            dl_rows = [(d.get("scheme", ""), d.get("activity") or d.get("host", ""),
                        "Yes" if not d.get("protected_by_permission") and d.get("exported") else "No")
                       for d in schemes]
            story.append(_generic_table(
                ["Scheme", "Activity / Host", "Unprotected?"], dl_rows,
                [120, CONTENT_WIDTH - 120 - 100, 100],
            ))
        elif schemes:
            story.append(Paragraph("Custom URL scheme(s): " + ", ".join(schemes), normal_style))
        else:
            story.append(Paragraph("No custom URL schemes registered.", normal_style))
        unprotected_count = deep_links.get("unprotected_count")
        if unprotected_count:
            story.append(Spacer(1, 0.08 * inch))
            story.append(Paragraph(f"Unprotected/exposed schemes: {unprotected_count}", normal_style))
        story.append(Spacer(1, 0.22 * inch))

    # -------------------- Exposed URLs --------------------
    exposed_urls = analysis.get("exposed_urls")
    if exposed_urls:
        section_num = _section(story, section_num, "Exposed URLs")
        story.append(Paragraph(
            f"Total URLs found: {exposed_urls.get('total_found', 0)}  |  "
            f"Plain HTTP: {exposed_urls.get('insecure_http_count', 0)}  |  "
            f"Internal/staging/debug: {exposed_urls.get('internal_or_debug_count', 0)}",
            normal_style,
        ))
        story.append(Spacer(1, 0.1 * inch))
        url_list = exposed_urls.get("urls") or []
        if url_list:
            flagged = [u for u in url_list if u.get("insecure_http") or u.get("looks_internal_or_debug")]
            display_urls = flagged if flagged else url_list
            url_rows = [
                (u["url"][:90], "Yes" if u.get("insecure_http") else "No",
                 "Yes" if u.get("looks_internal_or_debug") else "No")
                for u in display_urls[:40]
            ]
            story.append(_generic_table(
                ["URL", "Plain HTTP?", "Internal/Debug?"], url_rows,
                [CONTENT_WIDTH - 160, 80, 80],
            ))
            if len(display_urls) < len(url_list):
                story.append(Spacer(1, 0.06 * inch))
                story.append(Paragraph(
                    f"Showing flagged URLs only ({len(display_urls)} of {len(url_list)} total found).",
                    normal_style))
        else:
            story.append(Paragraph("No URLs found packaged inside the app.", normal_style))
        story.append(Spacer(1, 0.22 * inch))

    # -------------------- Storage Security --------------------
    storage = analysis.get("storage_security")
    if storage:
        section_num = _section(story, section_num, "Storage Security")
        story.append(Paragraph(f"Audit depth: {storage.get('depth', 'basic').title()}", normal_style))
        evidence_key = "encrypted_storage_evidence" if is_android else "keychain_usage_detected"
        if evidence_key in storage:
            label = "Encrypted local storage evidence found" if is_android else "Keychain usage detected"
            story.append(Paragraph(f"{label}: {storage.get(evidence_key)}", normal_style))
        indicators = storage.get("indicators")
        if indicators:
            story.append(Spacer(1, 0.06 * inch))
            story.append(Paragraph("Indicators found:", bold_label))
            _bullets(story, normal_style,
                     [f"{label}: {'; '.join(hits)}" for label, hits in indicators.items()])
        story.append(Spacer(1, 0.22 * inch))

    # -------------------- SDK / Dependency CVEs --------------------
    third_party = analysis.get("third_party_sdks")
    if third_party:
        section_num = _section(story, section_num, "SDK / Dependency CVEs")
        detected = third_party.get("detected") if isinstance(third_party, dict) else third_party
        if detected:
            story.append(Paragraph("Detected third-party SDKs: " + ", ".join(detected), normal_style))
        else:
            story.append(Paragraph("No known third-party SDKs fingerprinted.", normal_style))
        advisories = third_party.get("advisories") if isinstance(third_party, dict) else None
        if advisories:
            story.append(Spacer(1, 0.1 * inch))
            adv_rows = []
            for sdk, entries in advisories.items():
                for e in entries:
                    adv_rows.append((sdk, e.get("advisory", ""), e.get("affected", ""), e.get("note", "")))
            story.append(_generic_table(
                ["SDK", "Advisory", "Affected Versions", "Note"], adv_rows,
                [70, 90, 90, CONTENT_WIDTH - 70 - 90 - 90],
            ))
        story.append(Spacer(1, 0.22 * inch))

    # -------------------- Authentication --------------------
    authentication = analysis.get("authentication")
    if authentication:
        section_num = _section(story, section_num, "Authentication")
        story.append(Paragraph(f"Audit depth: {authentication.get('depth', 'basic').title()}", normal_style))
        story.append(Paragraph(f"Biometric API detected: {authentication.get('biometric_api_detected')}", normal_style))
        if "hardcoded_credential_pattern_found" in authentication:
            story.append(Paragraph(
                f"Hardcoded credential pattern found: {authentication.get('hardcoded_credential_pattern_found')}",
                normal_style))
        indicators = authentication.get("indicators")
        if indicators:
            story.append(Spacer(1, 0.06 * inch))
            story.append(Paragraph("Indicators found:", bold_label))
            _bullets(story, normal_style,
                     [f"{label}: {'; '.join(hits)}" for label, hits in indicators.items()])
        story.append(Spacer(1, 0.22 * inch))

    # -------------------- Accessibility --------------------
    accessibility = analysis.get("accessibility")
    if accessibility:
        section_num = _section(story, section_num, "Accessibility")
        for key in ("content_description_usage_detected", "accessibility_service_reference_detected"):
            if key in accessibility:
                story.append(Paragraph(f"{key.replace('_', ' ').title()}: {accessibility[key]}", normal_style))
        if accessibility.get("note"):
            story.append(Paragraph(accessibility["note"], normal_style))
        story.append(Spacer(1, 0.22 * inch))

    # -------------------- Performance --------------------
    performance = analysis.get("performance")
    if performance:
        section_num = _section(story, section_num, "Performance")
        perf_rows = [(k.replace("_", " ").title(), v) for k, v in performance.items() if k != "note"]
        if perf_rows:
            story.append(key_value_table(perf_rows, col_widths=[200, CONTENT_WIDTH - 200]))
        if performance.get("note"):
            story.append(Spacer(1, 0.08 * inch))
            story.append(Paragraph(performance["note"], normal_style))
        story.append(Spacer(1, 0.22 * inch))

    # -------------------- Dynamic Test Results (premium) --------------------
    dynamic_results = analysis.get("dynamic_test_results")
    if dynamic_results is not None:
        section_num = _section(story, section_num, "Dynamic Test Results")
        if dynamic_results.get("performed"):
            dr_rows = [(k.replace("_", " ").title(), v) for k, v in dynamic_results.items() if k != "performed"]
            story.append(key_value_table(dr_rows, col_widths=[200, CONTENT_WIDTH - 200]))
        else:
            story.append(Paragraph(
                dynamic_results.get("reason", "Dynamic testing was not performed for this scan."),
                normal_style))
        story.append(Spacer(1, 0.22 * inch))

    # -------------------- Crash / ANR (premium) --------------------
    crash_anr = analysis.get("crash_anr")
    if crash_anr is not None:
        section_num = _section(story, section_num, "Crash / ANR")
        if crash_anr.get("performed"):
            cr_rows = [(k.replace("_", " ").title(), v) for k, v in crash_anr.items() if k != "performed"]
            story.append(key_value_table(cr_rows, col_widths=[200, CONTENT_WIDTH - 200]))
        else:
            story.append(Paragraph(
                crash_anr.get("reason", "Crash/ANR monitoring requires a dynamic run and was not performed."),
                normal_style))
        story.append(Spacer(1, 0.22 * inch))

    # -------------------- Screenshots & Evidence (premium) --------------------
    screenshots = analysis.get("screenshots_evidence")
    if screenshots is not None:
        section_num = _section(story, section_num, "Screenshots & Evidence")
        if screenshots.get("performed") and screenshots.get("evidence"):
            _bullets(story, normal_style, [str(e) for e in screenshots["evidence"]])
        else:
            story.append(Paragraph(
                screenshots.get("reason", "No screenshot evidence was captured for this scan."),
                normal_style))
        story.append(Spacer(1, 0.22 * inch))

    # -------------------- AI Root Cause + Fix Recommendation (premium) --------------------
    ai_findings = analysis.get("ai_findings")
    if ai_findings:
        section_num = _section(story, section_num, "AI Root Cause + Fix Recommendation")
        for finding in ai_findings:
            story.append(Paragraph(f"<b>[{finding['severity']}] {finding['title']}</b>", normal_style))
            if "root_cause" in finding and "fix_recommendation" in finding:
                # Premium depth: full deterministic KB write-up
                # (see _ai_findings(depth="premium") in the engine).
                story.append(Paragraph(f"<b>Root cause:</b> {finding['root_cause']}", normal_style))
                story.append(Paragraph(f"<b>Fix:</b> {finding['fix_recommendation']}", normal_style))
            else:
                # Standard depth: lighter severity-driven guidance only,
                # no KB lookup (see _ai_findings(depth="standard")).
                story.append(Paragraph(
                    f"<b>Recommendation:</b> {finding.get('recommendation', '')}", normal_style))
            story.append(Spacer(1, 0.1 * inch))
        story.append(Spacer(1, 0.12 * inch))

    # -------------------- Remediation Priority (premium) --------------------
    remediation = analysis.get("remediation_priority")
    if remediation:
        section_num = _section(story, section_num, "Remediation Priority")
        rem_rows = [(i + 1, r["severity"], r["title"], r["recommended_action"])
                    for i, r in enumerate(remediation)]
        story.append(_generic_table(
            ["#", "Severity", "Finding", "Recommended Action"], rem_rows,
            [25, 60, CONTENT_WIDTH - 25 - 60 - 130, 130],
        ))
        story.append(Spacer(1, 0.22 * inch))

    # -------------------- Final Score (premium) --------------------
    final_score = analysis.get("final_score")
    if final_score:
        section_num = _section(story, section_num, "Final Score")
        fs_rows = [
            ("Base Security Score", final_score.get("base_security_score")),
            ("Bonus Points", final_score.get("bonus_points")),
            ("Final Score", final_score.get("final_score")),
        ]
        story.append(key_value_table(fs_rows, col_widths=[200, CONTENT_WIDTH - 200]))
        bonus_notes = final_score.get("bonus_notes")
        if bonus_notes:
            story.append(Spacer(1, 0.08 * inch))
            _bullets(story, normal_style, bonus_notes)
        story.append(Spacer(1, 0.22 * inch))

    # -------------------- Footer --------------------
    story.append(
        footer_note(
            "This is a static analysis report - findings are based on files packaged inside the "
            "app, not runtime/dynamic behaviour. Review Critical and High severity items first.",
            normal_style,
        )
    )

    doc.build(story, onFirstPage=add_page_number, onLaterPages=add_page_number)
    return pdf_path