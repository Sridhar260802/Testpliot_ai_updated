# ============================================================
# ADVANCED SECURITY AUDIT SERVICE - V3
# TestPilot-AI
# ------------------------------------------------------------
# Fixes in this version (vs V2):
#   - FIXED: hostname verification used the removed ssl.match_hostname()
#     API (removed in Python 3.12), which silently crashed and made
#     EVERY certificate report "hostname mismatch" as a CRITICAL finding,
#     even for perfectly valid certs. Replaced with a proper RFC 6125
#     style SAN + wildcard matcher that doesn't depend on deprecated APIs.
#   - Certificate report now also lists Subject Alternative Names (SAN).
#
# Cosmetic / report-quality upgrade:
#   - Professional PDF report: cover page, score gauge, color-coded
#     severity badges, wrapped table cells (no more overflow), section
#     dividers, table of contents, page numbers / footer, executive
#     narrative summary.
#
# Optional dependencies (script degrades gracefully if missing):
#   pip install dnspython python-whois requests reportlab
# ============================================================

import os
import re
import ssl
import socket
import json
import fnmatch
import datetime
import uuid
from urllib.parse import urlparse, urljoin

import requests
from bs4 import BeautifulSoup

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
    HRFlowable,
)
from reportlab.graphics.shapes import Drawing, Circle, String, Wedge
from app.models.security_audit import SecurityAudit


# ============================================================
# CONFIGURATION
# ============================================================

REQUEST_TIMEOUT = 20

SENSITIVE_PATHS = [
    ".env", ".git/config", "config.json", "config.php", "debug",
    "actuator", "phpinfo.php", "server-status", "backup.zip",
    "backup.sql", ".DS_Store", "composer.json", "package-lock.json",
    "webpack.config.js", "docker-compose.yml", "database.sql",
    "dump.sql", "admin", "admin/", "debug.log", "error.log",
    "swagger.json", "swagger-ui.html", "graphql", ".htaccess",
    "wp-config.php", ".well-known/security.txt",
    # --- [VAPT] additional recon paths ---
    ".git/HEAD", ".env.local", ".env.production", ".env.backup",
    "credentials.json", "secrets.yml", "secrets.yaml", ".aws/credentials",
    "id_rsa", "id_rsa.pub", ".npmrc", ".idea/workspace.xml",
    ".vscode/settings.json", "web.config", "vendor/composer/installed.json",
    "storage/logs/laravel.log", "wp-content/debug.log",
    ".well-known/openid-configuration", "server.key", "server.pem",
]

# ============================================================
# [ADVANCED] SENSITIVE / INTERNAL LINK EXPOSURE
# ------------------------------------------------------------
# Outbound <a href> links on the public page that point at
# internal infrastructure (localhost, private IPs, staging/dev
# subdomains) or at sensitive admin/config endpoints. These
# should never be reachable from a page the public can view.
# ============================================================

INTERNAL_HOST_PATTERNS = [
    "localhost", "127.0.0.1", "0.0.0.0", "::1",
]

PRIVATE_IP_REGEX = re.compile(
    r"^(10\.\d{1,3}\.\d{1,3}\.\d{1,3}|"
    r"172\.(1[6-9]|2\d|3[0-1])\.\d{1,3}\.\d{1,3}|"
    r"192\.168\.\d{1,3}\.\d{1,3})$"
)

INTERNAL_SUBDOMAIN_KEYWORDS = [
    "staging.", "stage.", "dev.", "test.", "uat.", "qa.",
    "internal.", "preprod.", "sandbox.", "beta-internal.",
]

SENSITIVE_LINK_PATH_KEYWORDS = [
    "/wp-admin", "/phpmyadmin", "/adminer", "/cpanel",
    "/.git", "/.env", "/.svn", "/manager/html",
    "/server-status", "/actuator", "/.aws/credentials",
]

SECURITY_HEADERS = {
    "Strict-Transport-Security": "HSTS",
    "Content-Security-Policy": "Content Security Policy",
    "X-Content-Type-Options": "X-Content-Type-Options",
    "X-Frame-Options": "X-Frame-Options",
    "Referrer-Policy": "Referrer Policy",
    "Permissions-Policy": "Permissions Policy",
}

DNS_RECORD_TYPES = ["A", "AAAA", "MX", "TXT", "NS", "CAA"]

BRAND_NAME = "TestPilot-AI"
BRAND_PRIMARY = "#0B2545"     # deep navy
BRAND_ACCENT = "#2F6FED"      # blue accent
SEVERITY_COLORS = {
    "CRITICAL": "#B00020",
    "HIGH": "#E53935",
    "MEDIUM": "#F9A825",
    "LOW": "#1E88E5",
    "INFO": "#2E7D32",
}


# ============================================================
# HELPERS
# ============================================================

def normalize_url(url: str) -> str:
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url.rstrip("/")


def make_check(check, status, severity="INFO", details="", recommendation=""):
    return {
        "check": check,
        "status": status,
        "severity": severity,
        "details": details,
        "recommendation": recommendation,
    }


def severity_rank(severity):
    ranks = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1, "INFO": 0}
    return ranks.get(str(severity).upper(), 0)


def calculate_overall_status(critical, high, medium, low):
    if critical > 0:
        return "CRITICAL_RISK"
    if high > 0:
        return "HIGH_RISK"
    if medium > 0:
        return "MEDIUM_RISK"
    if low > 0:
        return "LOW_RISK"
    return "SECURE"


def calculate_security_score(passed, failed):
    total = passed + failed
    if total == 0:
        return 0
    return int((passed / total) * 100)


def safe_request(session, method, url, **kwargs):
    try:
        return session.request(method, url, timeout=REQUEST_TIMEOUT, allow_redirects=True, **kwargs)
    except Exception:
        return None


def bucket_check(check, passed_checks, failed_checks):
    """Route a single check dict into passed/failed lists."""
    if check["status"] == "PASS":
        passed_checks.append(check)
    elif check["status"] == "FAIL":
        failed_checks.append(check)
    else:
        # INFO-only advisory checks (e.g. dependency missing) are not
        # counted as failures, but we still want them visible.
        passed_checks.append(check)


# ============================================================
# CERTIFICATE HOSTNAME MATCHING (FIXED)
# ------------------------------------------------------------
# ssl.match_hostname() was deprecated in Python 3.7 and REMOVED
# entirely in Python 3.12. The old script called it unconditionally,
# which raised AttributeError on any modern Python interpreter,
# was swallowed by a broad except, and always reported a false
# "certificate hostname mismatch" CRITICAL finding.
#
# This replacement implements the matching ourselves (RFC 6125
# style): check Subject Alternative Names first (falling back to
# the legacy Common Name only if no SAN is present), and only allow
# a single leftmost wildcard label - e.g. "*.google.com" matches
# "www.google.com" but not "www.evil.google.com" or "google.com".
# ============================================================

def _wildcard_label_match(pattern: str, hostname: str) -> bool:
    pattern = pattern.lower().strip()
    hostname = hostname.lower().strip()

    if pattern == hostname:
        return True

    if pattern.startswith("*."):
        suffix = pattern[1:]  # e.g. ".google.com"
        if hostname.endswith(suffix):
            remainder = hostname[: -len(suffix)]
            # wildcard may only stand in for exactly one, non-empty label
            if remainder and "." not in remainder:
                return True
    return False


def get_certificate_hostnames(cert: dict):
    """Return (san_dns_names, common_names) found in a getpeercert() dict."""
    san_names = [value for key, value in cert.get("subjectAltName", ()) if key == "DNS"]
    common_names = [
        value
        for rdn in cert.get("subject", ())
        for key, value in rdn
        if key == "commonName"
    ]
    return san_names, common_names


def certificate_matches_hostname(cert: dict, hostname: str) -> bool:
    san_names, common_names = get_certificate_hostnames(cert)
    # Per RFC 6125: if SAN is present, CN must be ignored entirely.
    candidates = san_names if san_names else common_names
    return any(_wildcard_label_match(candidate, hostname) for candidate in candidates)


# ============================================================
# SSL / TLS AUDIT (core connection + certificate)
# ============================================================

def ssl_tls_audit(url):
    parsed = urlparse(url)
    hostname = parsed.hostname
    port = parsed.port or 443

    result = {
        "tls_version": None,
        "cipher": None,
        "certificate": {
            "subject": None, "issuer": None, "serial_number": None,
            "not_before": None, "not_after": None, "days_remaining": None,
            "hostname_match": False, "self_signed": False,
            "san": [], "certificate_chain": "UNKNOWN",
        },
        "status": "FAIL",
        "issues": [],
    }

    try:
        context = ssl.create_default_context()
        with socket.create_connection((hostname, port), timeout=REQUEST_TIMEOUT) as sock:
            with context.wrap_socket(sock, server_hostname=hostname) as secure_socket:
                result["tls_version"] = secure_socket.version()
                cipher = secure_socket.cipher()
                if cipher:
                    result["cipher"] = cipher[0]

                cert = secure_socket.getpeercert()

                subject_parts = [f"{k}={v}" for group in cert.get("subject", []) for k, v in group]
                result["certificate"]["subject"] = ", ".join(subject_parts)

                issuer_parts = [f"{k}={v}" for group in cert.get("issuer", []) for k, v in group]
                result["certificate"]["issuer"] = ", ".join(issuer_parts)

                result["certificate"]["serial_number"] = cert.get("serialNumber")

                san_names, _ = get_certificate_hostnames(cert)
                result["certificate"]["san"] = san_names

                not_before = cert.get("notBefore")
                not_after = cert.get("notAfter")
                result["certificate"]["not_before"] = not_before
                result["certificate"]["not_after"] = not_after

                if not_after:
                    expiry = datetime.datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z")
                    now = datetime.datetime.utcnow()
                    result["certificate"]["days_remaining"] = (expiry - now).days

                # --- FIXED hostname verification (no deprecated API) ---
                if certificate_matches_hostname(cert, hostname):
                    result["certificate"]["hostname_match"] = True
                else:
                    result["certificate"]["hostname_match"] = False
                    result["issues"].append(
                        f"Certificate hostname mismatch: '{hostname}' not covered by "
                        f"SAN/CN {san_names or [result['certificate']['subject']]}."
                    )

                subject = result["certificate"]["subject"]
                issuer = result["certificate"]["issuer"]
                if subject and issuer and subject == issuer:
                    result["certificate"]["self_signed"] = True
                    result["issues"].append("Certificate appears to be self-signed.")

                tls_version = result["tls_version"] or ""
                if tls_version not in ["TLSv1.2", "TLSv1.3"]:
                    result["issues"].append(f"Weak TLS version detected: {tls_version}")

                days = result["certificate"]["days_remaining"]
                if days is not None:
                    if days < 0:
                        result["issues"].append("SSL certificate has expired.")
                    elif days <= 7:
                        result["issues"].append("SSL certificate expires within 7 days.")
                    elif days <= 30:
                        result["issues"].append("SSL certificate expires within 30 days.")

                result["status"] = "PASS" if not result["issues"] else "FAIL"

    except Exception as e:
        result["issues"].append(str(e))
        result["status"] = "FAIL"

    return result


# ============================================================
# ADVANCED: WEAK / LEGACY TLS PROTOCOL DETECTION
# ============================================================

def weak_tls_protocol_audit(hostname, port=443):
    checks = []

    if not hasattr(ssl, "TLSVersion"):
        checks.append(make_check(
            "Weak TLS Protocol Detection", "INFO", "INFO",
            "Python ssl module lacks TLSVersion API (Python < 3.7) - check skipped.", ""
        ))
        return checks

    versions = {
        "TLSv1.0": ssl.TLSVersion.TLSv1,
        "TLSv1.1": ssl.TLSVersion.TLSv1_1,
        "TLSv1.2": ssl.TLSVersion.TLSv1_2,
        "TLSv1.3": ssl.TLSVersion.TLSv1_3,
    }

    for name, version in versions.items():
        try:
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            ctx.minimum_version = version
            ctx.maximum_version = version
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE

            with socket.create_connection((hostname, port), timeout=8) as sock:
                with ctx.wrap_socket(sock, server_hostname=hostname) as ssock:
                    negotiated = ssock.version()

            if name in ("TLSv1.0", "TLSv1.1"):
                checks.append(make_check(
                    f"Legacy Protocol Support - {name}", "FAIL", "HIGH",
                    f"Server accepted a handshake using {negotiated}.",
                    f"Disable {name} on the server; only TLS 1.2+ should be supported."
                ))
            else:
                checks.append(make_check(
                    f"Protocol Support - {name}", "PASS", "INFO",
                    f"Server supports {name}.", ""
                ))

        except Exception:
            if name in ("TLSv1.0", "TLSv1.1"):
                checks.append(make_check(
                    f"Legacy Protocol Support - {name}", "PASS", "INFO",
                    f"Server correctly rejects {name}.", ""
                ))
            else:
                checks.append(make_check(
                    f"Protocol Support - {name}", "INFO", "INFO",
                    f"Could not verify {name} support (handshake failed/blocked).", ""
                ))

    return checks


# ============================================================
# ADVANCED: DNS / DNSSEC / CAA
# ============================================================

def dns_audit(hostname):
    result = {rtype: [] for rtype in DNS_RECORD_TYPES}
    result["issues"] = []

    try:
        import dns.resolver
    except ImportError:
        result["issues"].append("dnspython not installed - DNS audit skipped (pip install dnspython).")
        return result

    resolver = dns.resolver.Resolver()
    resolver.timeout = 5
    resolver.lifetime = 5

    for rtype in DNS_RECORD_TYPES:
        try:
            answers = resolver.resolve(hostname, rtype)
            result[rtype] = [str(r) for r in answers]
        except Exception:
            pass

    if not result["CAA"]:
        result["issues"].append("No CAA record found - any public CA can issue certificates for this domain.")

    return result


def dns_checks_from_result(dns_result):
    checks = []

    if any("dnspython not installed" in i for i in dns_result.get("issues", [])):
        checks.append(make_check("DNS Audit", "INFO", "INFO", dns_result["issues"][0], ""))
        return checks

    if dns_result.get("NS"):
        checks.append(make_check(
            "DNS - Name Servers", "PASS", "INFO",
            f"NS records: {', '.join(dns_result.get('NS', []))}", ""
        ))

    if dns_result.get("CAA"):
        checks.append(make_check(
            "DNS - CAA Record", "PASS", "INFO",
            f"CAA record(s) present: {', '.join(dns_result.get('CAA', []))}", ""
        ))
    else:
        checks.append(make_check(
            "DNS - CAA Record", "FAIL", "MEDIUM",
            "No CAA record found - any public CA can issue certs for this domain.",
            "Add a CAA record restricting which Certificate Authorities may issue certificates."
        ))

    if dns_result.get("TXT"):
        spf_found = any("v=spf1" in txt.lower() for txt in dns_result["TXT"])
        if spf_found:
            checks.append(make_check("DNS - SPF Record", "PASS", "INFO", "SPF record found in TXT records.", ""))
        else:
            checks.append(make_check(
                "DNS - SPF Record", "FAIL", "LOW", "No SPF record found in TXT records.",
                "Publish an SPF record to reduce email spoofing risk."
            ))

    return checks


def dnssec_audit(hostname):
    result = {"enabled": False, "issues": []}
    try:
        import dns.resolver
    except ImportError:
        result["issues"].append("dnspython not installed - DNSSEC check skipped (pip install dnspython).")
        return result

    try:
        resolver = dns.resolver.Resolver()
        resolver.timeout = 5
        resolver.lifetime = 5
        answers = resolver.resolve(hostname, "DNSKEY")
        if answers:
            result["enabled"] = True
    except Exception:
        result["issues"].append("DNSSEC not enabled or DNSKEY record not found.")

    return result


def dnssec_check(dnssec_result):
    if any("not installed" in i for i in dnssec_result.get("issues", [])):
        return make_check("DNSSEC", "INFO", "INFO", dnssec_result["issues"][0], "")
    if dnssec_result.get("enabled"):
        return make_check("DNSSEC", "PASS", "INFO", "DNSSEC is enabled for this domain.", "")
    return make_check(
        "DNSSEC", "FAIL", "LOW",
        "DNSSEC does not appear to be enabled.",
        "Enable DNSSEC at the domain registrar / DNS provider to protect against DNS spoofing."
    )


# ============================================================
# ADVANCED: WHOIS DOMAIN EXPIRY
# ============================================================

def domain_whois_audit(hostname):
    result = {
        "registrar": None, "creation_date": None, "expiration_date": None,
        "days_to_expiry": None, "issues": [],
    }
    try:
        import whois as whois_lib
    except ImportError:
        result["issues"].append("python-whois not installed - WHOIS check skipped (pip install python-whois).")
        return result

    import socket
    import io
    import contextlib

    try:
        # Fail fast instead of hanging, and silence the library's own
        # print() calls when the WHOIS socket can't connect (blocked
        # port 43, DNS failure, etc.) so it doesn't spam the console.
        old_timeout = socket.getdefaulttimeout()
        socket.setdefaulttimeout(5)
        try:
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                w = whois_lib.whois(hostname)
        finally:
            socket.setdefaulttimeout(old_timeout)

        exp = w.expiration_date
        if isinstance(exp, list):
            exp = exp[0]
        result["registrar"] = w.registrar
        result["creation_date"] = str(w.creation_date)
        result["expiration_date"] = str(exp)
        if exp:
            if isinstance(exp, datetime.datetime):
                # FIX: exp may be timezone-aware while datetime.now() is naive,
                # which raised "can't subtract offset-naive and offset-aware
                # datetimes" and silently dropped days_to_expiry. Normalize both
                # to naive UTC before subtracting.
                if exp.tzinfo is not None:
                    exp_naive = exp.astimezone(datetime.timezone.utc).replace(tzinfo=None)
                else:
                    exp_naive = exp
                days = (exp_naive - datetime.datetime.utcnow()).days
                result["days_to_expiry"] = days
    except Exception as e:
        result["issues"].append(f"WHOIS lookup failed: {e}")

    return result


def whois_check(whois_result):
    if any("not installed" in i for i in whois_result.get("issues", [])):
        return make_check("Domain Expiry (WHOIS)", "INFO", "INFO", whois_result["issues"][0], "")
    if whois_result.get("issues"):
        return make_check("Domain Expiry (WHOIS)", "INFO", "INFO", whois_result["issues"][0], "")

    days = whois_result.get("days_to_expiry")
    if days is not None:
        if days < 30:
            return make_check(
                "Domain Expiry (WHOIS)", "FAIL", "HIGH",
                f"Domain expires in {days} days.",
                "Renew the domain registration immediately to avoid service disruption."
            )
        return make_check(
            "Domain Expiry (WHOIS)", "PASS", "INFO",
            f"Domain registered until {whois_result.get('expiration_date')} ({days} days remaining).", ""
        )
    return make_check("Domain Expiry (WHOIS)", "INFO", "INFO", "WHOIS expiration data unavailable.", "")


# ============================================================
# SECURITY HEADER AUDIT
# ============================================================

def security_headers_audit(response):
    checks = []
    for header, display_name in SECURITY_HEADERS.items():
        value = response.headers.get(header)
        if value:
            checks.append(make_check(display_name, "PASS", "INFO", f"Header present: {value}", ""))
        else:
            severity = "HIGH" if header in ("Strict-Transport-Security", "Content-Security-Policy") else "MEDIUM"
            checks.append(make_check(
                display_name, "FAIL", severity, f"{header} header is missing.",
                f"Configure a proper {header} header."
            ))
    return checks


# ============================================================
# ADVANCED: CSP STRENGTH ANALYSIS
# ============================================================

def csp_strength_audit(response):
    csp = response.headers.get("Content-Security-Policy")
    if not csp:
        return make_check("CSP Strength", "FAIL", "MEDIUM", "No Content-Security-Policy header found.",
                           "Implement a restrictive Content-Security-Policy.")
    issues = []
    if "unsafe-inline" in csp:
        issues.append("allows 'unsafe-inline'")
    if "unsafe-eval" in csp:
        issues.append("allows 'unsafe-eval'")
    if re.search(r"(default-src|script-src)[^;]*\*", csp):
        issues.append("uses a wildcard (*) source")
    if issues:
        return make_check("CSP Strength", "FAIL", "MEDIUM", "; ".join(issues),
                           "Tighten CSP directives - avoid unsafe-inline/unsafe-eval and wildcard sources.")
    return make_check("CSP Strength", "PASS", "INFO",
                       "CSP does not use unsafe-inline, unsafe-eval, or an obvious wildcard source.", "")


# ============================================================
# ADVANCED: HSTS PRELOAD / SUBDOMAINS / MAX-AGE STRENGTH
# ============================================================

def hsts_strength_audit(response):
    hsts = response.headers.get("Strict-Transport-Security", "")
    if not hsts:
        return make_check("HSTS Strength", "FAIL", "MEDIUM", "HSTS header missing entirely.",
                           "Add a Strict-Transport-Security header.")

    issues = []
    if "includesubdomains" not in hsts.lower():
        issues.append("missing includeSubDomains")
    if "preload" not in hsts.lower():
        issues.append("missing preload directive")

    try:
        max_age = int(hsts.lower().split("max-age=")[1].split(";")[0])
    except Exception:
        max_age = 0

    if max_age < 31536000:
        issues.append(f"max-age too low ({max_age}s, recommended >= 31536000s / 1 year)")

    if issues:
        return make_check("HSTS Strength", "FAIL", "LOW", "; ".join(issues),
                           "Strengthen HSTS: max-age >= 31536000; includeSubDomains; preload.")
    return make_check("HSTS Strength", "PASS", "INFO",
                       "HSTS configured with sufficient max-age, includeSubDomains and preload.", "")


# ============================================================
# ADVANCED: CLICKJACKING PROTECTION
# ============================================================

def clickjacking_audit(response):
    xfo = response.headers.get("X-Frame-Options")
    csp = response.headers.get("Content-Security-Policy", "")
    frame_ancestors = "frame-ancestors" in csp.lower()

    if xfo or frame_ancestors:
        return make_check("Clickjacking Protection", "PASS", "INFO",
                           "Framing is restricted via X-Frame-Options and/or CSP frame-ancestors.", "")
    return make_check("Clickjacking Protection", "FAIL", "MEDIUM",
                       "No X-Frame-Options or CSP frame-ancestors directive found - page can be framed.",
                       "Add X-Frame-Options: DENY/SAMEORIGIN or a CSP frame-ancestors directive.")


# ============================================================
# ADVANCED: SUBRESOURCE INTEGRITY (SRI)
# ============================================================

def sri_audit(response):
    try:
        own_host = urlparse(response.url).netloc
        tags = re.findall(r"<script[^>]*>", response.text, re.IGNORECASE)
        missing = []

        for tag in tags:
            src_match = re.search(r'src=["\']([^"\']+)["\']', tag, re.IGNORECASE)
            if not src_match:
                continue
            src = src_match.group(1)
            if not src.startswith("http"):
                continue
            if urlparse(src).netloc == own_host:
                continue
            if "integrity=" not in tag.lower():
                missing.append(src)

        if missing:
            sample = "; ".join(missing[:5])
            return make_check(
                "Subresource Integrity (SRI)", "FAIL", "MEDIUM",
                f"{len(missing)} external script(s) loaded without an integrity attribute, e.g.: {sample}",
                "Add integrity and crossorigin attributes to externally-hosted <script> tags."
            )
        return make_check("Subresource Integrity (SRI)", "PASS", "INFO",
                           "No external scripts missing SRI (or none detected).", "")
    except Exception as e:
        return make_check("Subresource Integrity (SRI)", "FAIL", "LOW", str(e), "Review page scripts manually.")


# ============================================================
# ADVANCED: SECURITY.TXT (RFC 9116)
# ============================================================

def security_txt_audit(base_url):
    for path in [".well-known/security.txt", "security.txt"]:
        target = urljoin(base_url.rstrip("/") + "/", path)
        try:
            r = requests.get(target, timeout=REQUEST_TIMEOUT)
            if r.status_code == 200 and "contact" in r.text.lower():
                return make_check("Security.txt (RFC 9116)", "PASS", "INFO",
                                   f"security.txt found at {target}", "")
        except Exception:
            continue
    return make_check("Security.txt (RFC 9116)", "FAIL", "LOW", "No security.txt file found.",
                       "Publish a /.well-known/security.txt file (RFC 9116) for responsible disclosure contacts.")


# ============================================================
# ADVANCED: ROBOTS.TXT SENSITIVE PATH DISCLOSURE
# ============================================================

def robots_txt_audit(base_url):
    robots_url = urljoin(base_url.rstrip("/") + "/", "robots.txt")
    try:
        r = requests.get(robots_url, timeout=REQUEST_TIMEOUT)
        if r.status_code != 200:
            return make_check("Robots.txt", "PASS", "INFO", "No robots.txt found (nothing to disclose).", "")

        sensitive_lines = [
            line.strip() for line in r.text.splitlines()
            if line.lower().strip().startswith("disallow")
            and any(k in line.lower() for k in ["admin", "backup", "config", "private", ".git", "wp-admin"])
        ]
        if sensitive_lines:
            return make_check(
                "Robots.txt Disclosure", "FAIL", "LOW",
                f"robots.txt references potentially sensitive paths: {'; '.join(sensitive_lines[:5])}",
                "Avoid listing sensitive paths in robots.txt; enforce access control server-side instead."
            )
        return make_check("Robots.txt", "PASS", "INFO",
                           "robots.txt present with no obviously sensitive path disclosure.", "")
    except Exception as e:
        return make_check("Robots.txt", "FAIL", "LOW", str(e), "Verify robots.txt manually.")


# ============================================================
# ADVANCED: HTTP PROTOCOL VERSION / ALT-SVC (HTTP/2, HTTP/3)
# ============================================================

def http_version_audit(response):
    alt_svc = response.headers.get("Alt-Svc")
    raw_version = getattr(response.raw, "version", None)
    version_map = {9: "HTTP/0.9", 10: "HTTP/1.0", 11: "HTTP/1.1", 20: "HTTP/2"}
    negotiated = version_map.get(raw_version, "Unknown")

    details = f"Negotiated protocol (via requests/urllib3): {negotiated}."
    if alt_svc:
        details += f" Server advertises Alt-Svc: {alt_svc} (h3/h2 support)."

    if negotiated == "HTTP/1.0":
        return make_check("HTTP Protocol Version", "FAIL", "LOW", details,
                           "Upgrade the server to support HTTP/1.1 or higher.")
    return make_check("HTTP Protocol Version", "PASS", "INFO", details, "")


# ============================================================
# ADVANCED: CERTIFICATE TRANSPARENCY LOG LOOKUP
# ============================================================

def certificate_transparency_audit(hostname):
    try:
        r = requests.get(f"https://crt.sh/?q={hostname}&output=json", timeout=REQUEST_TIMEOUT)
        if r.status_code == 200:
            data = r.json()
            count = len(data)
            return make_check("Certificate Transparency Logs", "PASS", "INFO",
                               f"{count} certificate entr(y/ies) found in public CT logs for this domain.", "")
    except Exception:
        pass
    return make_check("Certificate Transparency Logs", "INFO", "INFO",
                       "Could not retrieve CT log data (crt.sh unavailable or rate-limited).", "")


# ============================================================
# COOKIE SECURITY
# ============================================================

def cookie_security_audit(response):
    checks = []
    cookies = []

    for cookie in response.cookies:
        same_site = cookie.get_nonstandard_attr("SameSite")
        cookies.append({
            "name": cookie.name,
            "secure": bool(cookie.secure),
            "http_only": bool(cookie.has_nonstandard_attr("HttpOnly")),
            "same_site": same_site,
        })

    if not cookies:
        checks.append(make_check("Cookie Security", "PASS", "INFO",
                                  "No cookies were set during the initial response.", ""))
        return checks, cookies

    for cookie in cookies:
        name = cookie["name"]
        if not cookie["secure"]:
            checks.append(make_check(f"Cookie Secure Flag - {name}", "FAIL", "MEDIUM",
                                      f"Cookie {name} does not use Secure flag.",
                                      "Set Secure attribute for sensitive cookies."))
        if not cookie["http_only"]:
            checks.append(make_check(f"Cookie HttpOnly Flag - {name}", "FAIL", "MEDIUM",
                                      f"Cookie {name} does not use HttpOnly.",
                                      "Use HttpOnly for authentication/session cookies."))
        if not cookie["same_site"]:
            checks.append(make_check(f"Cookie SameSite - {name}", "FAIL", "LOW",
                                      f"Cookie {name} does not define SameSite.",
                                      "Configure SameSite=Lax or SameSite=Strict where appropriate."))

    if not checks:
        checks.append(make_check("Cookie Security", "PASS", "INFO",
                                  "All detected cookies passed basic security attribute checks.", ""))

    return checks, cookies


# ============================================================
# CORS AUDIT
# ============================================================

def cors_audit(response):
    value = response.headers.get("Access-Control-Allow-Origin")
    if value == "*":
        return make_check("CORS Wildcard", "FAIL", "MEDIUM",
                           "CORS allows requests from any origin.",
                           "Restrict CORS to trusted application origins.")
    return make_check("CORS Configuration", "PASS", "INFO",
                       "No permissive CORS wildcard detected.", "")


# ============================================================
# HTTP -> HTTPS
# ============================================================

def https_redirect_audit(url):
    parsed = urlparse(url)
    if parsed.scheme != "https":
        return make_check("HTTP to HTTPS Redirect", "INFO", "MEDIUM",
                           "Original URL is not HTTPS.", "Use HTTPS for the production website.")

    http_url = "http://" + parsed.netloc + parsed.path
    try:
        response = requests.get(http_url, timeout=REQUEST_TIMEOUT, allow_redirects=False)
        location = response.headers.get("Location", "")
        if response.status_code in (301, 302, 307, 308) and location.startswith("https://"):
            return make_check("HTTP to HTTPS Redirect", "PASS", "INFO",
                               f"HTTP correctly redirects to HTTPS: {location}", "")
        return make_check("HTTP to HTTPS Redirect", "FAIL", "HIGH",
                           "HTTP does not correctly redirect to HTTPS.",
                           "Configure a permanent HTTP to HTTPS redirect.")
    except Exception as e:
        return make_check("HTTP to HTTPS Redirect", "FAIL", "MEDIUM", str(e),
                           "Verify HTTP to HTTPS redirect configuration.")


# ============================================================
# HTTP METHODS
# ============================================================

def http_methods_audit(response):
    allow = response.headers.get("Allow")
    if allow:
        return make_check("HTTP Methods", "FAIL", "LOW",
                           f"Allow header exposes methods: {allow}",
                           "Disable unnecessary HTTP methods.")
    return make_check("HTTP Methods", "PASS", "INFO",
                       "No explicit Allow header exposing methods.", "")


# ============================================================
# SENSITIVE PATH AUDIT
# ============================================================

def sensitive_paths_audit(base_url):
    results = []
    for path in SENSITIVE_PATHS:
        target = urljoin(base_url.rstrip("/") + "/", path)
        try:
            response = requests.get(target, timeout=REQUEST_TIMEOUT, allow_redirects=False)
            status = response.status_code
            if status == 200:
                results.append({"path": path, "status": status, "risk": "HIGH", "exposed": True})
            else:
                results.append({"path": path, "status": status, "risk": "INFO", "exposed": False})
        except Exception as e:
            results.append({"path": path, "status": None, "risk": "INFO", "exposed": False, "error": str(e)})
    return results


# ============================================================
# [ADVANCED] SENSITIVE / INTERNAL LINK EXPOSURE
# ============================================================

def internal_link_exposure_audit(response):
    """
    Scans the page's own outbound <a href> links for anything that
    points at internal infrastructure or a sensitive admin/config
    endpoint - things a public-facing page should never link to.
    Returns a list of make_check() results (one per distinct finding).
    """
    checks = []
    findings = []

    try:
        soup = BeautifulSoup(response.text, "html.parser")
        seen = set()

        for tag in soup.find_all("a", href=True):
            href = tag["href"].strip()

            if not href or href.startswith("#") or href.startswith("mailto:") or href.startswith("tel:"):
                continue

            if href in seen:
                continue
            seen.add(href)

            parsed = urlparse(href)
            hostname = (parsed.hostname or "").lower()
            lowered = href.lower()

            reason = None

            if hostname in INTERNAL_HOST_PATTERNS or PRIVATE_IP_REGEX.match(hostname or ""):
                reason = ("HIGH", f"Links to an internal/loopback host ({hostname}).")

            elif any(keyword in hostname for keyword in INTERNAL_SUBDOMAIN_KEYWORDS):
                reason = ("MEDIUM", f"Links to what looks like a staging/dev environment ({hostname}).")

            elif any(keyword in lowered for keyword in SENSITIVE_LINK_PATH_KEYWORDS):
                reason = ("HIGH", "Links directly to a sensitive admin/config endpoint.")

            if reason:
                findings.append({"href": href, "severity": reason[0], "reason": reason[1]})

    except Exception as e:
        return [make_check(
            "Sensitive / Internal Link Exposure", "FAIL", "LOW",
            f"Could not scan page links ({e}).",
            "Retry the scan once the page has finished loading."
        )]

    if not findings:
        return [make_check(
            "Sensitive / Internal Link Exposure", "PASS", "INFO",
            "No internal, staging or admin/config links were found in the page's outbound links.",
            ""
        )]

    for item in findings[:20]:
        checks.append(make_check(
            f"Sensitive / Internal Link Exposure - {item['href']}",
            "FAIL", item["severity"],
            item["reason"],
            "Remove this link from public-facing pages, or move the target behind authentication "
            "so it isn't publicly reachable/discoverable."
        ))

    return checks


# ============================================================
# MIXED CONTENT AUDIT
# ============================================================

def mixed_content_audit(response):
    try:
        content = response.text.lower()
        http_references = []

        for prefix in ["http://", "http:\\/\\/"]:
            start = 0
            while True:
                index = content.find(prefix, start)
                if index == -1:
                    break
                end = content.find('"', index)
                if end == -1:
                    end = min(index + 200, len(content))
                http_references.append(content[index:end])
                start = index + len(prefix)

        http_references = list(dict.fromkeys(http_references))
        filtered = [
            item for item in http_references
            if not any(ignore in item for ignore in
                       ["http://www.w3.org", "http://schema.org", "http://xmlns.com"])
        ]

        if filtered:
            return (make_check("Mixed Content", "FAIL", "MEDIUM",
                                "HTTP resource references detected.",
                                "Serve all resources over HTTPS."), filtered)
        return (make_check("Mixed Content", "PASS", "INFO",
                            "No obvious HTTP resource references detected.", ""), [])
    except Exception as e:
        return (make_check("Mixed Content", "FAIL", "LOW", str(e),
                            "Review page resources manually."), [])


# ============================================================
# CACHE CONTROL
# ============================================================

def cache_control_audit(response):
    value = response.headers.get("Cache-Control")
    if value:
        return make_check("Cache-Control", "PASS", "INFO", f"Cache-Control: {value}", "")
    return make_check("Cache-Control", "FAIL", "LOW", "Cache-Control header is missing.",
                       "Configure appropriate Cache-Control policies.")


# ============================================================
# INFORMATION DISCLOSURE
# ============================================================

def information_disclosure_audit(response):
    checks = []
    server = response.headers.get("Server")
    powered = response.headers.get("X-Powered-By")

    if server:
        checks.append(make_check("Information Disclosure - server", "FAIL", "LOW",
                                  f"Server technology information exposed: {server}",
                                  "Remove unnecessary technology/version information from HTTP headers."))
    if powered:
        checks.append(make_check("Information Disclosure - X-Powered-By", "FAIL", "LOW",
                                  f"Technology information exposed: {powered}",
                                  "Remove X-Powered-By header."))
    if not checks:
        checks.append(make_check("Information Disclosure", "PASS", "INFO",
                                  "No obvious server technology disclosure detected.", ""))
    return checks


# ============================================================
# [VAPT] EXTENDED SECURITY / CROSS-ORIGIN ISOLATION HEADERS
# ------------------------------------------------------------
# Part of the Vulnerability Assessment & Penetration Testing
# (VAPT) service line - passive, non-intrusive header checks
# that go beyond the core header set (COOP/COEP/CORP are used
# by modern browsers to isolate a site from cross-origin attacks
# such as Spectre-style side channels and window.opener abuse).
# ============================================================

EXTENDED_SECURITY_HEADERS = {
    "Cross-Origin-Opener-Policy": "Cross-Origin-Opener-Policy",
    "Cross-Origin-Resource-Policy": "Cross-Origin-Resource-Policy",
    "Cross-Origin-Embedder-Policy": "Cross-Origin-Embedder-Policy",
    "X-Permitted-Cross-Domain-Policies": "X-Permitted-Cross-Domain-Policies",
}


def extended_security_headers_audit(response):
    checks = []
    for header, display_name in EXTENDED_SECURITY_HEADERS.items():
        value = response.headers.get(header)
        if value:
            checks.append(make_check(display_name, "PASS", "INFO", f"Header present: {value}", ""))
        else:
            checks.append(make_check(
                display_name, "FAIL", "LOW", f"{header} header is missing.",
                f"Configure a {header} header to reduce cross-origin attack surface."
            ))
    return checks


# ============================================================
# [VAPT] VERSION / BANNER DISCLOSURE RISK
# ------------------------------------------------------------
# Flags response headers that leak a specific software version
# number (as opposed to just a bare product name). A disclosed
# version lets an attacker map the target to known CVEs, so this
# is scored higher than the generic "Information Disclosure"
# check above.
# ============================================================

VERSION_NUMBER_PATTERN = re.compile(r"\d+\.\d+(\.\d+)?")
BANNER_HEADERS = ("Server", "X-Powered-By", "X-AspNet-Version", "X-AspNetMvc-Version", "X-Generator", "X-Drupal-Cache")


def version_disclosure_audit(response):
    checks = []
    for header in BANNER_HEADERS:
        value = response.headers.get(header)
        if value and VERSION_NUMBER_PATTERN.search(value):
            checks.append(make_check(
                f"Version Disclosure - {header}", "FAIL", "MEDIUM",
                f"{header} header discloses a specific software version: {value}",
                f"Suppress version numbers in the {header} header - disclosed versions let an "
                "attacker map the stack to known CVEs before ever touching the application."
            ))
    if not checks:
        checks.append(make_check("Version Disclosure", "PASS", "INFO",
                                  "No specific software version numbers were disclosed in response headers.", ""))
    return checks


# ============================================================
# [VAPT] HTTP TRACE METHOD (CROSS-SITE TRACING)
# ------------------------------------------------------------
# A passive probe: sends a single TRACE request and checks
# whether the server echoes it back. No payload/exploitation -
# just confirms whether the XST attack surface exists.
# ============================================================

def http_trace_method_audit(base_url):
    try:
        response = requests.request("TRACE", base_url, timeout=REQUEST_TIMEOUT)
        if response.status_code == 200:
            return make_check(
                "HTTP TRACE Method", "FAIL", "MEDIUM",
                f"Server responded to a TRACE request with HTTP {response.status_code}.",
                "Disable the HTTP TRACE method on the web server/proxy to prevent "
                "Cross-Site Tracing (XST) attacks."
            )
        return make_check("HTTP TRACE Method", "PASS", "INFO",
                           f"Server does not permit TRACE requests (HTTP {response.status_code}).", "")
    except Exception as e:
        return make_check("HTTP TRACE Method", "INFO", "INFO", f"Could not test TRACE method: {e}", "")


# ============================================================
# [VAPT] DIRECTORY LISTING EXPOSURE
# ------------------------------------------------------------
# Requests a handful of commonly-present directory paths and
# checks whether the server returns an autoindex-style listing
# page instead of a 403/404. Purely observational - no traversal,
# no fuzzing beyond a short static wordlist.
# ============================================================

DIRECTORY_LISTING_PROBE_PATHS = ["images/", "uploads/", "assets/", "static/", "files/", "backup/", "media/"]


def directory_listing_audit(base_url):
    exposed = []
    for path in DIRECTORY_LISTING_PROBE_PATHS:
        target = urljoin(base_url.rstrip("/") + "/", path)
        try:
            response = requests.get(target, timeout=REQUEST_TIMEOUT)
            if response.status_code == 200 and re.search(r"index of /", response.text, re.IGNORECASE):
                exposed.append(target)
        except Exception:
            continue
    if exposed:
        return make_check(
            "Directory Listing", "FAIL", "MEDIUM",
            f"Directory listing enabled at: {', '.join(exposed)}",
            "Disable directory listing/autoindex on the web server for these paths."
        )
    return make_check("Directory Listing", "PASS", "INFO",
                       "No directory listing detected on commonly probed paths.", "")


# ============================================================
# [VAPT] OPEN REDIRECT INDICATOR
# ------------------------------------------------------------
# Appends a well-known, harmless external URL (example.com) to a
# handful of common redirect-style query parameters and checks
# whether the server issues a redirect straight to it. This only
# ever points at example.com - it never probes attacker-style
# payloads (javascript:, data:, //evil, etc.) since this is a
# detection check, not an exploitation attempt.
# ============================================================

OPEN_REDIRECT_PARAMS = ["redirect", "url", "next", "return", "returnUrl", "continue", "dest"]
OPEN_REDIRECT_TEST_TARGET = "https://example.com/"


def open_redirect_audit(base_url):
    findings = []
    for param in OPEN_REDIRECT_PARAMS:
        test_url = f"{base_url.rstrip('/')}/?{param}={OPEN_REDIRECT_TEST_TARGET}"
        try:
            response = requests.get(test_url, timeout=REQUEST_TIMEOUT, allow_redirects=False)
            location = response.headers.get("Location", "")
            if response.status_code in (301, 302, 303, 307, 308) and "example.com" in location:
                findings.append(f"{param} -> {location}")
        except Exception:
            continue
    if findings:
        return make_check(
            "Open Redirect", "FAIL", "MEDIUM",
            f"Unvalidated redirect parameter(s) detected: {'; '.join(findings)}",
            "Validate and allow-list redirect targets server-side; never redirect to a URL "
            "taken directly from a user-controlled query parameter."
        )
    return make_check("Open Redirect", "PASS", "INFO",
                       "No open redirect behavior detected on commonly probed parameters.", "")


# ============================================================
# [VAPT] PASSWORD FIELD AUTOCOMPLETE
# ------------------------------------------------------------
# Static scan of the returned HTML for <input type="password">
# fields that don't restrict autocomplete. No form is submitted.
# ============================================================

def autocomplete_password_audit(response):
    try:
        password_inputs = re.findall(r"<input[^>]*type=[\"']password[\"'][^>]*>", response.text, re.IGNORECASE)
        if not password_inputs:
            return make_check("Password Field Autocomplete", "PASS", "INFO",
                               "No password input fields detected on this page.", "")
        risky = [
            tag for tag in password_inputs
            if "new-password" not in tag.lower()
            and 'autocomplete="off"' not in tag.lower().replace("'", '"')
        ]
        if risky:
            return make_check(
                "Password Field Autocomplete", "FAIL", "LOW",
                f"{len(risky)} password input field(s) found without autocomplete=\"off\"/\"new-password\".",
                "Set autocomplete=\"new-password\" (or \"off\") on password fields to reduce "
                "credential caching risk on shared/public machines."
            )
        return make_check("Password Field Autocomplete", "PASS", "INFO",
                           "All detected password fields restrict autocomplete.", "")
    except Exception as e:
        return make_check("Password Field Autocomplete", "INFO", "INFO", str(e), "")


# ============================================================
# [VAPT] EXPOSED SECRETS / CREDENTIALS IN PAGE SOURCE
# ------------------------------------------------------------
# Regex scan of the rendered HTML for patterns that commonly
# indicate a hardcoded credential or key was shipped to the
# client (AWS access keys, generic api_key=/secret_key= strings,
# PEM private-key blocks). Detection only - values are never
# printed or persisted, only the pattern label that matched.
# ============================================================

SECRET_PATTERNS = {
    "AWS Access Key": re.compile(r"AKIA[0-9A-Z]{16}"),
    "Generic API Key Assignment": re.compile(r"(?i)(api[_-]?key)[\"'\s:=]{1,5}[A-Za-z0-9_\-]{16,}"),
    "Generic Client Secret Assignment": re.compile(r"(?i)(client[_-]?secret|secret[_-]?key)[\"'\s:=]{1,5}[A-Za-z0-9_\-]{16,}"),
    "PEM Private Key Block": re.compile(r"-----BEGIN (RSA|EC|DSA|OPENSSH|)? ?PRIVATE KEY-----"),
}


def exposed_secrets_scan(response):
    findings = []
    try:
        content = response.text
        for label, pattern in SECRET_PATTERNS.items():
            if pattern.search(content):
                findings.append(label)
    except Exception:
        pass
    if findings:
        return make_check(
            "Exposed Secrets in Page Source", "FAIL", "HIGH",
            f"Pattern(s) resembling credentials/keys found in page source: {', '.join(findings)}",
            "Remove hardcoded credentials/keys from client-side code and rotate any exposed "
            "secret immediately; secrets belong server-side only."
        )
    return make_check("Exposed Secrets in Page Source", "PASS", "INFO",
                       "No obvious credential/key patterns detected in page source.", "")


# ============================================================
# [PREMIUM] MALWARE DETECTION
# ------------------------------------------------------------
# Passive, signature/heuristic based malware scan of the page
# response - no third-party scanning API required. Flags the
# indicators most commonly left behind by a compromised or
# infected website:
#   - script tags loaded from known malware / cryptomining hosts
#   - obfuscated JavaScript (eval+unescape/atob, long
#     String.fromCharCode chains) typically used to hide a payload
#   - hidden / zero-size iframes, a classic drive-by-download and
#     malvertising injection technique
#   - silent meta-refresh redirects to a different domain
# This complements (does not replace) a full engine-based malware
# scan, and degrades gracefully - a parse failure is reported as
# an informational check rather than crashing the whole audit.
# ============================================================

MALWARE_SCRIPT_DOMAINS = [
    "coinhive.com", "coin-hive.com", "cryptoloot.pro", "crypto-loot.com",
    "authedmine.com", "webminepool.com", "minero.cc", "jsecoin.com",
    "coinimp.com", "webmine.pro", "moneropay.win", "deepminer.info",
    "coinerra.com", "minemytraffic.com", "projectpoi.com",
]

MALWARE_JS_PATTERNS = {
    "Obfuscated eval(unescape/atob(...))": re.compile(r"eval\s*\(\s*(unescape|atob)\s*\("),
    "Obfuscated document.write(unescape(...))": re.compile(r"document\.write\s*\(\s*unescape\s*\("),
    "Long String.fromCharCode obfuscation chain": re.compile(
        r"(String\.fromCharCode\s*\([^)]*\)\s*[+,]\s*){8,}"
    ),
    "Hidden iframe (display:none/visibility:hidden)": re.compile(
        r"<iframe[^>]*style=[\"'][^\"']*(display\s*:\s*none|visibility\s*:\s*hidden)[^\"']*[\"']",
        re.IGNORECASE,
    ),
    "Zero-size iframe (width=0/height=0)": re.compile(
        r'<iframe(?=[^>]*\bwidth=["\']?0["\']?)(?=[^>]*\bheight=["\']?0["\']?)[^>]*>',
        re.IGNORECASE,
    ),
}


def malware_detection_audit(response, base_url):
    """
    Runs the passive malware heuristics above against a fetched page and
    returns a list of `make_check(...)` results, ready for `bucket_check`.
    """

    try:
        content = response.text
    except Exception as e:
        return [make_check("Malware Detection", "INFO", "INFO",
                            f"Could not read page content for malware scan: {e}", "")]

    checks = []

    # ---- known malicious / cryptomining script sources ----
    try:
        soup = BeautifulSoup(content, "html.parser")
        script_srcs = [tag.get("src") for tag in soup.find_all("script") if tag.get("src")]
    except Exception:
        script_srcs = re.findall(r'<script[^>]+src=["\']([^"\']+)["\']', content, re.IGNORECASE)

    malicious_scripts = [
        src for src in script_srcs
        if any(domain in src.lower() for domain in MALWARE_SCRIPT_DOMAINS)
    ]
    if malicious_scripts:
        checks.append(make_check(
            "Cryptomining / Known Malicious Script Source", "FAIL", "CRITICAL",
            f"Script(s) loaded from known malicious/cryptomining domains: {', '.join(malicious_scripts[:5])}",
            "Remove the malicious script tag(s) immediately, audit the site's files/CMS plugins for "
            "compromise, and rotate any admin/API credentials that may have been exposed."
        ))
    else:
        checks.append(make_check("Cryptomining / Known Malicious Script Source", "PASS", "INFO",
                                  "No script tags referencing known malicious/cryptomining domains were found.", ""))

    # ---- obfuscated script / hidden iframe patterns ----
    obf_findings = [label for label, pattern in MALWARE_JS_PATTERNS.items() if pattern.search(content)]
    if obf_findings:
        checks.append(make_check(
            "Obfuscated Script / Hidden Iframe Patterns", "FAIL", "HIGH",
            f"Pattern(s) commonly associated with malware injection found in page source: {', '.join(obf_findings)}",
            "Manually inspect the flagged script blocks and iframes. Obfuscated eval/unescape/atob or "
            "fromCharCode chains and hidden zero-size iframes are common indicators of a website "
            "compromise, malicious ad injection, or a drive-by-download attempt."
        ))
    else:
        checks.append(make_check("Obfuscated Script / Hidden Iframe Patterns", "PASS", "INFO",
                                  "No obfuscated script or hidden-iframe patterns detected in page source.", ""))

    # ---- silent cross-domain meta-refresh redirect ----
    meta_redirect = re.search(
        r'<meta[^>]+http-equiv=["\']refresh["\'][^>]+content=["\'][^"\']*url=([^"\'>]+)',
        content, re.IGNORECASE,
    )
    if meta_redirect:
        target = meta_redirect.group(1).strip()
        target_host = urlparse(target).hostname if "://" in target else urlparse(base_url).hostname
        source_host = urlparse(base_url).hostname
        if target_host and source_host and target_host != source_host:
            checks.append(make_check(
                "Unsolicited Cross-Domain Redirect", "FAIL", "MEDIUM",
                f"A meta-refresh tag silently redirects visitors to a different domain ({target_host}).",
                "Remove the unexpected redirect or confirm it is intentional. Unannounced cross-domain "
                "redirects are a common symptom of a hijacked or infected site being used to funnel "
                "traffic elsewhere."
            ))
        else:
            checks.append(make_check("Unsolicited Cross-Domain Redirect", "PASS", "INFO",
                                      "No cross-domain meta-refresh redirect detected.", ""))
    else:
        checks.append(make_check("Unsolicited Cross-Domain Redirect", "PASS", "INFO",
                                  "No meta-refresh redirect detected.", ""))

    return checks


# ============================================================
# MAIN SECURITY AUDIT
# ============================================================

def security_audit(url,db,user_id):
    url = normalize_url(url)
    print("\n========== ADVANCED SECURITY AUDIT (V3) ==========\n")

    session = requests.Session()
    timestamp = datetime.datetime.now().isoformat()

    passed_checks, failed_checks, issues = [], [], []
    sensitive_paths, cookies, mixed_content = [], [], []

    # ---------------- WEBSITE REQUEST ----------------
    print("[0] WEBSITE REQUEST")
    response = safe_request(session, "GET", url)

    if response is None:
        return {
            "module": "Security Audit", "url": url, "timestamp": timestamp,
            "status": "UNAVAILABLE", "security_score": 0,
            "passed_checks": [], "failed_checks": [],
            "issues": [{
                "category": "Website Availability", "title": "Website unavailable",
                "severity": "CRITICAL", "details": "Website request failed.",
                "recommendation": "Verify website availability.",
            }],
            "summary": {"total_checks": 1, "passed_checks": 0, "failed_checks": 1,
                        "critical": 1, "high": 0, "medium": 0, "low": 0},
        }

    print(f"Final URL : {response.url}")
    print(f"Status    : {response.status_code}")

    if 200 <= response.status_code < 400:
        passed_checks.append(make_check("Website Availability", "PASS", "INFO",
                                         f"Website returned HTTP {response.status_code}.", ""))
    else:
        failed_checks.append(make_check("Website Availability", "FAIL", "CRITICAL",
                                         f"Website returned HTTP {response.status_code}.",
                                         "Verify website availability and server configuration."))

    hostname = urlparse(response.url).hostname

    # ---------------- SSL / TLS ----------------
    print("[1] SSL / TLS AUDIT")
    ssl_result = ssl_tls_audit(url)
    certificate = ssl_result["certificate"]

    if ssl_result.get("status") == "PASS":
        passed_checks.extend([
            make_check("TLS Version", "PASS", "INFO", f"Secure TLS version detected: {ssl_result.get('tls_version')}", ""),
            make_check("SSL Certificate", "PASS", "INFO", "Valid TLS certificate was successfully retrieved.", ""),
            make_check("TLS Cipher", "PASS", "INFO", f"Negotiated cipher: {ssl_result.get('cipher')}", ""),
            make_check("Certificate Hostname Match", "PASS", "INFO",
                       "Certificate hostname matches the requested domain (SAN/CN verified).", ""),
        ])
    else:
        failed_checks.append(make_check("SSL/TLS Audit", "FAIL", "HIGH",
                                         "; ".join(ssl_result.get("issues", [])),
                                         "Review TLS configuration and certificate validity."))

    # ---------------- [ADVANCED] WEAK TLS PROTOCOL DETECTION ----------------
    print("[1b] LEGACY TLS PROTOCOL DETECTION")
    for check in weak_tls_protocol_audit(hostname):
        bucket_check(check, passed_checks, failed_checks)

    # ---------------- SECURITY HEADERS ----------------
    print("[2] SECURITY HEADERS")
    for check in security_headers_audit(response):
        bucket_check(check, passed_checks, failed_checks)

    # ---------------- [ADVANCED] CSP STRENGTH ----------------
    print("[2b] CSP STRENGTH ANALYSIS")
    bucket_check(csp_strength_audit(response), passed_checks, failed_checks)

    # ---------------- [ADVANCED] HSTS STRENGTH ----------------
    print("[2c] HSTS STRENGTH ANALYSIS")
    bucket_check(hsts_strength_audit(response), passed_checks, failed_checks)

    # ---------------- [ADVANCED] CLICKJACKING ----------------
    print("[2d] CLICKJACKING PROTECTION")
    bucket_check(clickjacking_audit(response), passed_checks, failed_checks)

    # ---------------- INFORMATION DISCLOSURE ----------------
    print("[3] INFORMATION DISCLOSURE")
    for check in information_disclosure_audit(response):
        bucket_check(check, passed_checks, failed_checks)

    # ---------------- CORS ----------------
    print("[4] CORS AUDIT")
    bucket_check(cors_audit(response), passed_checks, failed_checks)

    # ---------------- COOKIES ----------------
    print("[5] COOKIE SECURITY")
    cookie_checks, cookies = cookie_security_audit(response)
    for check in cookie_checks:
        bucket_check(check, passed_checks, failed_checks)

    # ---------------- HTTPS REDIRECT ----------------
    print("[6] HTTP -> HTTPS REDIRECT")
    bucket_check(https_redirect_audit(url), passed_checks, failed_checks)

    # ---------------- HTTP METHODS ----------------
    print("[7] HTTP METHODS")
    bucket_check(http_methods_audit(response), passed_checks, failed_checks)

    # ---------------- SENSITIVE PATHS ----------------
    print("[8] SENSITIVE PATH AUDIT")
    sensitive_paths = sensitive_paths_audit(response.url)
    exposed_paths = [item for item in sensitive_paths if item.get("exposed")]
    if exposed_paths:
        for item in exposed_paths:
            failed_checks.append(make_check(
                f"Sensitive Path Exposure - {item['path']}", "FAIL", "HIGH",
                f"{urljoin(response.url, item['path'])} returned HTTP {item['status']}.",
                "Remove or restrict access to sensitive files and endpoints."))
    else:
        passed_checks.append(make_check("Sensitive Path Exposure", "PASS", "INFO",
                                         "No tested sensitive paths returned HTTP 200.", ""))

    # ---------------- [ADVANCED] SENSITIVE / INTERNAL LINK EXPOSURE ----------------
    print("[8b] SENSITIVE / INTERNAL LINK EXPOSURE AUDIT")
    for check in internal_link_exposure_audit(response):
        bucket_check(check, passed_checks, failed_checks)

    # ---------------- MIXED CONTENT ----------------
    print("[9] MIXED CONTENT AUDIT")
    mixed_check, mixed_content = mixed_content_audit(response)
    bucket_check(mixed_check, passed_checks, failed_checks)

    # ---------------- CACHE CONTROL ----------------
    print("[10] CACHE CONTROL")
    bucket_check(cache_control_audit(response), passed_checks, failed_checks)

    # ---------------- [ADVANCED] SRI ----------------
    print("[10b] SUBRESOURCE INTEGRITY (SRI) AUDIT")
    bucket_check(sri_audit(response), passed_checks, failed_checks)

    # ---------------- [ADVANCED] SECURITY.TXT ----------------
    print("[10c] SECURITY.TXT AUDIT")
    bucket_check(security_txt_audit(response.url), passed_checks, failed_checks)

    # ---------------- [ADVANCED] ROBOTS.TXT ----------------
    print("[10d] ROBOTS.TXT DISCLOSURE AUDIT")
    bucket_check(robots_txt_audit(response.url), passed_checks, failed_checks)

    # ---------------- [ADVANCED] HTTP VERSION ----------------
    print("[10e] HTTP PROTOCOL VERSION AUDIT")
    bucket_check(http_version_audit(response), passed_checks, failed_checks)

    # ---------------- [ADVANCED] DNS / DNSSEC ----------------
    print("[11] DNS AUDIT")
    dns_result = dns_audit(hostname)
    for check in dns_checks_from_result(dns_result):
        bucket_check(check, passed_checks, failed_checks)

    print("[11b] DNSSEC AUDIT")
    dnssec_result = dnssec_audit(hostname)
    bucket_check(dnssec_check(dnssec_result), passed_checks, failed_checks)

    # ---------------- [ADVANCED] WHOIS ----------------
    print("[12] WHOIS DOMAIN EXPIRY AUDIT")
    whois_result = domain_whois_audit(hostname)
    bucket_check(whois_check(whois_result), passed_checks, failed_checks)

    # ---------------- [ADVANCED] CERTIFICATE TRANSPARENCY ----------------
    print("[13] CERTIFICATE TRANSPARENCY LOG AUDIT")
    bucket_check(certificate_transparency_audit(hostname), passed_checks, failed_checks)

    # ================================================================
    # [VAPT] VULNERABILITY ASSESSMENT & PENETRATION TESTING - EXTENDED
    # PASSIVE CHECK SUITE
    # ================================================================

    # ---------------- [VAPT] EXTENDED CROSS-ORIGIN HEADERS ----------------
    print("[14] EXTENDED SECURITY HEADERS (COOP/COEP/CORP)")
    for check in extended_security_headers_audit(response):
        bucket_check(check, passed_checks, failed_checks)

    # ---------------- [VAPT] VERSION / BANNER DISCLOSURE ----------------
    print("[15] VERSION / BANNER DISCLOSURE AUDIT")
    for check in version_disclosure_audit(response):
        bucket_check(check, passed_checks, failed_checks)

    # ---------------- [VAPT] HTTP TRACE METHOD ----------------
    print("[16] HTTP TRACE METHOD (XST) AUDIT")
    bucket_check(http_trace_method_audit(response.url), passed_checks, failed_checks)

    # ---------------- [VAPT] DIRECTORY LISTING ----------------
    print("[17] DIRECTORY LISTING AUDIT")
    bucket_check(directory_listing_audit(response.url), passed_checks, failed_checks)

    # ---------------- [VAPT] OPEN REDIRECT ----------------
    print("[18] OPEN REDIRECT AUDIT")
    bucket_check(open_redirect_audit(response.url), passed_checks, failed_checks)

    # ---------------- [VAPT] PASSWORD AUTOCOMPLETE ----------------
    print("[19] PASSWORD FIELD AUTOCOMPLETE AUDIT")
    bucket_check(autocomplete_password_audit(response), passed_checks, failed_checks)

    # ---------------- [VAPT] EXPOSED SECRETS ----------------
    print("[20] EXPOSED SECRETS IN PAGE SOURCE AUDIT")
    bucket_check(exposed_secrets_scan(response), passed_checks, failed_checks)

    # ---------------- [PREMIUM] MALWARE DETECTION ----------------
    print("[21] MALWARE DETECTION")
    malware_checks = malware_detection_audit(response, response.url)
    for check in malware_checks:
        bucket_check(check, passed_checks, failed_checks)

    # ---------------- CERTIFICATE DETAILED CHECKS ----------------
    certificate_checks = []
    days_remaining = certificate.get("days_remaining")

    if not certificate.get("self_signed"):
        certificate_checks.append(make_check("Self Signed Certificate", "PASS", "INFO",
                                              "Certificate is not self-signed.", ""))
    else:
        certificate_checks.append(make_check("Self Signed Certificate", "FAIL", "HIGH",
                                              "Certificate appears to be self-signed.",
                                              "Use a certificate issued by a trusted Certificate Authority."))

    if days_remaining is not None:
        if days_remaining > 30:
            certificate_checks.append(make_check("Certificate Expiry", "PASS", "INFO",
                                                   f"Certificate has {days_remaining} days remaining.", ""))
        elif days_remaining > 7:
            certificate_checks.append(make_check("Certificate Expiry", "FAIL", "MEDIUM",
                                                   f"Certificate expires in {days_remaining} days.",
                                                   "Renew the SSL/TLS certificate before expiration."))
        else:
            certificate_checks.append(make_check("Certificate Expiry", "FAIL", "HIGH",
                                                   f"Certificate expires in {days_remaining} days.",
                                                   "Renew the SSL/TLS certificate immediately."))

    for check in certificate_checks:
        bucket_check(check, passed_checks, failed_checks)

    # ---------------- BUILD ISSUES ----------------
    for check in failed_checks:
        issues.append({
            "category": "Security Audit", "title": check["check"], "severity": check["severity"],
            "details": check["details"], "recommendation": check["recommendation"],
        })

    # ---------------- SEVERITY SUMMARY ----------------
    critical = high = medium = low = 0
    for issue in issues:
        sev = issue.get("severity", "LOW").upper()
        if sev == "CRITICAL":
            critical += 1
        elif sev == "HIGH":
            high += 1
        elif sev == "MEDIUM":
            medium += 1
        elif sev == "LOW":
            low += 1

    passed_count = len(passed_checks)
    failed_count = len(failed_checks)
    security_score = calculate_security_score(passed_count, failed_count)
    overall_status = calculate_overall_status(critical, high, medium, low)

    recommendations = list(dict.fromkeys(
        [issue["recommendation"] for issue in issues if issue.get("recommendation")]
    ))

    success_audit = [{
        "check": c["check"], "status": "PASS", "severity": c["severity"],
        "details": c["details"], "recommendation": "",
    } for c in passed_checks]

    result = {
        "module": "Security Audit",
        "url": url,
        "timestamp": timestamp,
        "status": overall_status,
        "security_score": security_score,
        "website": {"final_url": response.url, "http_status": response.status_code},
        "ssl_tls": ssl_result,
        "security_headers": {
            header: {"present": bool(response.headers.get(header)), "value": response.headers.get(header)}
            for header in SECURITY_HEADERS
        },
        "cookies": cookies,
        "cors": {"allow_origin": response.headers.get("Access-Control-Allow-Origin")},
        "http_https_redirect": https_redirect_audit(url),
        "http_methods": {"allow_header": response.headers.get("Allow")},
        "sensitive_paths": sensitive_paths,
        "mixed_content": mixed_content,
        "cache_control": response.headers.get("Cache-Control"),
        "malware_detection": {
            "checks": malware_checks,
            "status": "CLEAN" if all(c["status"] == "PASS" for c in malware_checks) else "FLAGGED",
        },
        "dns": dns_result,
        "dnssec": dnssec_result,
        "whois": whois_result,
        "success_audit": success_audit,
        "passed_checks": passed_checks,
        "failed_checks": failed_checks,
        "issues": issues,
        "recommendations": recommendations,
        "severity_summary": {"CRITICAL": critical, "HIGH": high, "MEDIUM": medium, "LOW": low},
        "summary": {
            "total_checks": passed_count + failed_count,
            "passed_checks": passed_count, "failed_checks": failed_count,
            "critical": critical, "high": high, "medium": medium, "low": low,
        },
    }

    # ---------------- PRINT SUMMARY ----------------
    print("\n========== SECURITY AUDIT RESULT ==========\n")
    print(f"Security Score : {security_score}%")
    print(f"Status         : {overall_status}")
    print(f"Passed Checks  : {passed_count}")
    print(f"Failed Checks  : {failed_count}")
    print(f"Critical/High/Medium/Low : {critical}/{high}/{medium}/{low}")

    print("\n========== SECURITY ISSUES ==========")
    for index, issue in enumerate(issues, start=1):
        print(f"\n{index}. [{issue['severity']}] {issue['title']}")
        print(f"   Details : {issue['details']}")
        print(f"   Fix     : {issue['recommendation']}")
    print("\n===========================================\n")

    # ---------------- SAVE JSON ----------------
    # Unique per-audit filename - previously this was a fixed name that
    # every audit (from every user) overwrote, so old reports vanished.
    report_id = f"{user_id}_{uuid.uuid4().hex}"
    os.makedirs("security_reports", exist_ok=True)
    json_path = os.path.join("security_reports", f"security_audit_report_{report_id}.json")
    with open(json_path, "w", encoding="utf-8") as file:
        json.dump(result, file, indent=4, ensure_ascii=False, default=str)
    print(f"JSON report saved : {json_path}")

    # ---------------- GENERATE PDF ----------------
    pdf_path = generate_security_pdf(result, client_name="Client", report_id=report_id)
    result["pdf_report"] = pdf_path
    # ---------------- SAVE SECURITY AUDIT TO DATABASE ----------------
    try:
        audit = SecurityAudit(
        user_id=user_id,
        url=result.get("url", url),
        status=result.get("status", "FAIL"),
        security_score=result.get("security_score", 0),
        issue=str(result.get("issues", "")),
        possible_reason=result.get("possible_reason"),
        recommendation=str(result.get("recommendations", "")),
        developer_action=result.get("developer_action")
    )

        db.add(audit)
        db.commit()
        db.refresh(audit)
        print("✅ Security Audit data stored in database")

    except Exception as e:
        db.rollback()
        print(f"❌ Security Audit DB Error: {e}")

    return result


# ============================================================
# PDF REPORT  (professional layout)
# ============================================================

from app.services.groq_service import generate_ai_suggestions


def _p(text, style):
    """Wrap arbitrary text safely in a Paragraph so table cells wrap."""
    if text is None:
        text = ""
    text = str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return Paragraph(text, style)


def _severity_badge(severity, style):
    color = SEVERITY_COLORS.get(str(severity).upper(), "#546E7A")
    return Paragraph(
        f'<font color="{color}"><b>{severity}</b></font>', style
    )


def _score_gauge(score: int, status: str):
    """Draw a simple donut gauge showing the security score."""
    size = 46 * mm
    d = Drawing(size, size)
    cx, cy, r = size / 2, size / 2, size / 2 - 4 * mm

    if score >= 80:
        ring_color = colors.HexColor("#2E7D32")
    elif score >= 60:
        ring_color = colors.HexColor("#F9A825")
    else:
        ring_color = colors.HexColor("#B00020")

    d.add(Circle(cx, cy, r, fillColor=colors.HexColor("#ECEFF1"), strokeColor=None))
    d.add(Wedge(cx, cy, r, 90, 90 - (360 * score / 100), fillColor=ring_color, strokeColor=None))
    d.add(Circle(cx, cy, r * 0.62, fillColor=colors.white, strokeColor=None))
    d.add(String(cx, cy + 2, f"{score}%", fontSize=15, fillColor=colors.HexColor(BRAND_PRIMARY),
                  textAnchor="middle", fontName="Helvetica-Bold"))
    d.add(String(cx, cy - 10, "SCORE", fontSize=6.5, fillColor=colors.HexColor("#607D8B"),
                  textAnchor="middle", fontName="Helvetica"))
    return d


def _header_footer(canvas_obj, doc, report):
    canvas_obj.saveState()
    width, height = A4

    # Footer
    canvas_obj.setStrokeColor(colors.HexColor("#CFD8DC"))
    canvas_obj.setLineWidth(0.5)
    canvas_obj.line(15 * mm, 14 * mm, width - 15 * mm, 14 * mm)

    canvas_obj.setFont("Helvetica", 7.5)
    canvas_obj.setFillColor(colors.HexColor("#607D8B"))
    canvas_obj.drawString(15 * mm, 10 * mm, f"{BRAND_NAME} - Confidential Security Assessment")
    canvas_obj.drawRightString(width - 15 * mm, 10 * mm, f"Page {doc.page}")
    canvas_obj.drawCentredString(width / 2, 10 * mm, report.get("url", ""))

    # Header (skip on cover page)
    if doc.page > 1:
        canvas_obj.setFillColor(colors.HexColor(BRAND_PRIMARY))
        canvas_obj.rect(0, height - 12 * mm, width, 12 * mm, fill=1, stroke=0)
        canvas_obj.setFillColor(colors.white)
        canvas_obj.setFont("Helvetica-Bold", 10)
        canvas_obj.drawString(15 * mm, height - 8.3 * mm, f"{BRAND_NAME}  |  Security Audit")
        canvas_obj.setFont("Helvetica", 8.5)
        canvas_obj.drawRightString(width - 15 * mm, height - 8.3 * mm,
                                    datetime.datetime.fromisoformat(report["timestamp"]).strftime("%d %b %Y"))

    canvas_obj.restoreState()


def _generate_security_ai_suggestions(report: dict) -> str:
    """
    Builds an overall AI-written review of the security audit: what the
    biggest risks are, why they matter, and what to fix first. Falls back
    to a plain-text summary if the AI call fails (no key, network issue,
    etc.) so the report still generates.
    """
    summary = report.get("summary", {})
    issues = sorted(
        report.get("issues", []),
        key=lambda i: -severity_rank(i.get("severity"))
    )
    top_issues = issues[:12]

    issues_text = "\n".join(
        f"- [{i.get('severity','')}] {i.get('title','')}: {i.get('details','')}"
        for i in top_issues
    ) or "No failing checks."

    prompt = f"""
    You are a security analyst summarizing an automated web security audit for a client.

    Target: {report.get("url", "")}
    Overall Security Score: {report.get("security_score", 0)}%
    Risk Status: {report.get("status", "N/A")}
    Total Checks: {summary.get("total_checks", 0)} | Passed: {summary.get("passed_checks", 0)} | Failed: {summary.get("failed_checks", 0)}
    Critical: {summary.get("critical", 0)} | High: {summary.get("high", 0)} | Medium: {summary.get("medium", 0)} | Low: {summary.get("low", 0)}

    Failing checks (highest severity first):
    {issues_text}

    Write a concise overall review covering:
    1. Overall security posture in plain language.
    2. The most business-critical risks and why they matter.
    3. A prioritized remediation order (what to fix first, next, later).
    4. Any quick wins that are low effort but high impact.

    Keep it to a few short paragraphs, no markdown headers, no bullet symbols other than plain text.
    """

    try:
        return generate_ai_suggestions(prompt)
    except Exception as e:
        return (
            "AI-generated overall review is unavailable right now "
            f"({str(e)}). Based on the automated findings above, prioritize "
            "the Critical and High severity issues first, then work through "
            "Medium and Low severity items."
        )


def generate_security_pdf(report, client_name="Client", report_id=None):
    os.makedirs("security_reports", exist_ok=True)
    suffix = report_id or uuid.uuid4().hex
    pdf_path = os.path.join("security_reports", f"advanced_security_audit_report_{suffix}.pdf")

    document = SimpleDocTemplate(
        pdf_path, pagesize=A4,
        rightMargin=15 * mm, leftMargin=15 * mm,
        topMargin=20 * mm, bottomMargin=20 * mm,
        title=f"{BRAND_NAME} Security Audit - {report.get('url','')}",
        author=BRAND_NAME,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("CoverTitle", parent=styles["Title"], alignment=TA_CENTER,
                                  fontSize=26, textColor=colors.HexColor(BRAND_PRIMARY), spaceAfter=6)
    subtitle_style = ParagraphStyle("CoverSubtitle", parent=styles["Title"], alignment=TA_CENTER,
                                     fontSize=13, textColor=colors.HexColor(BRAND_ACCENT), spaceAfter=4,
                                     fontName="Helvetica")
    heading_style = ParagraphStyle("SecHeading", parent=styles["Heading2"], fontSize=13.5,
                                    textColor=colors.HexColor(BRAND_PRIMARY), spaceBefore=14, spaceAfter=8)
    normal_style = ParagraphStyle("SecNormal", parent=styles["BodyText"], fontSize=9.3, leading=13)
    cell_style = ParagraphStyle("Cell", parent=styles["BodyText"], fontSize=7.6, leading=9.6)
    cell_bold = ParagraphStyle("CellBold", parent=cell_style, fontName="Helvetica-Bold")
    small_style = ParagraphStyle("Small", parent=styles["BodyText"], fontSize=7.8,
                                  textColor=colors.HexColor("#607D8B"))

    story = []

    # =========================== HEADER / SUMMARY (page 1, no separate cover page) ===========================
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph(BRAND_NAME, subtitle_style))
    story.append(Spacer(1, 4))
    story.append(Paragraph(" Security Audit Report", title_style))
    story.append(Paragraph("Web Application &amp; Infrastructure Assessment", subtitle_style))
    story.append(Spacer(1, 6 * mm))

    status = report.get("status", "N/A")
    status_color = {
        "CRITICAL_RISK": "#B00020", "HIGH_RISK": "#E53935", "MEDIUM_RISK": "#F9A825",
        "LOW_RISK": "#1E88E5", "SECURE": "#2E7D32",
    }.get(status, "#546E7A")

    def _esc(text):
        return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    gauge = _score_gauge(report.get("security_score", 0), status)
    cover_table = Table(
        [[gauge, Paragraph(
            f'<b>Target:</b> {_esc(report.get("url",""))}<br/>'
            f'<b>Prepared for:</b> {_esc(client_name)}<br/>'
            f'<b>Scan Date:</b> {datetime.datetime.fromisoformat(report["timestamp"]).strftime("%d %B %Y, %H:%M")}<br/>'
            f'<b>Overall Risk Status:</b> <font color="{status_color}"><b>{status.replace("_"," ")}</b></font>',
            normal_style
        )]],
        colWidths=[52 * mm, 110 * mm],
    )
    cover_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (0, 0), "CENTER"),
    ]))
    story.append(cover_table)
    story.append(Spacer(1, 16 * mm))

    summary = report.get("summary", {})
    kpi_data = [
        ["Total Checks", "Passed", "Failed", "Critical", "High", "Medium", "Low"],
        [summary.get("total_checks", 0), summary.get("passed_checks", 0), summary.get("failed_checks", 0),
         summary.get("critical", 0), summary.get("high", 0), summary.get("medium", 0), summary.get("low", 0)],
    ]
    kpi_table = Table(kpi_data, colWidths=[23 * mm] * 7)
    kpi_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(BRAND_PRIMARY)),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CFD8DC")),
        ("TEXTCOLOR", (3, 1), (3, 1), colors.HexColor(SEVERITY_COLORS["CRITICAL"])),
        ("TEXTCOLOR", (4, 1), (4, 1), colors.HexColor(SEVERITY_COLORS["HIGH"])),
        ("TEXTCOLOR", (5, 1), (5, 1), colors.HexColor(SEVERITY_COLORS["MEDIUM"])),
        ("TEXTCOLOR", (6, 1), (6, 1), colors.HexColor(SEVERITY_COLORS["LOW"])),
        ("ROWBACKGROUNDS", (0, 1), (-1, 1), [colors.HexColor("#F5F7FA")]),
    ]))
    story.append(kpi_table)
    story.append(Spacer(1, 6 * mm))
    story.append(HRFlowable(width="100%", thickness=0.6, color=colors.HexColor("#CFD8DC")))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        "This report is confidential and intended solely for the addressed client. "
        "It summarizes automated findings from an external, black-box security scan and should be "
        "supplemented with manual penetration testing for a complete risk assessment.",
        small_style
    ))
    story.append(Spacer(1, 6 * mm))

    # =========================== EXECUTIVE SUMMARY ===========================
    story.append(Paragraph("1. Executive Summary", heading_style))
    critical_n = summary.get("critical", 0)
    high_n = summary.get("high", 0)
    narrative = (
        f'The assessment identified <b>{summary.get("failed_checks",0)}</b> issue(s) out of '
        f'<b>{summary.get("total_checks",0)}</b> checks performed, resulting in a security score of '
        f'<b>{report.get("security_score",0)}%</b> and an overall risk rating of '
        f'<font color="{status_color}"><b>{status.replace("_"," ")}</b></font>. '
    )
    if critical_n or high_n:
        narrative += (
            f'There {"are" if (critical_n+high_n) != 1 else "is"} <b>{critical_n} critical</b> and '
            f'<b>{high_n} high</b> severity finding(s) that should be prioritized for remediation.'
        )
    else:
        narrative += "No critical or high severity findings were identified in this scan."
    story.append(Paragraph(narrative, normal_style))
    story.append(Spacer(1, 6))

    # =========================== SSL/TLS ===========================
    story.append(Paragraph("2. SSL / TLS &amp; Certificate Audit", heading_style))
    ssl_data = report.get("ssl_tls", {})
    certificate = ssl_data.get("certificate", {})
    san = certificate.get("san") or []
    ssl_table_data = [
        [_p("Parameter", cell_bold), _p("Result", cell_bold)],
        [_p("TLS Version", cell_style), _p(ssl_data.get("tls_version", "N/A"), cell_style)],
        [_p("Cipher Suite", cell_style), _p(ssl_data.get("cipher", "N/A"), cell_style)],
        [_p("Hostname Verification", cell_style),
         _severity_badge("PASS", cell_bold) if certificate.get("hostname_match") else _severity_badge("FAIL", cell_bold)],
        [_p("Self-Signed", cell_style), _p("YES" if certificate.get("self_signed") else "NO", cell_style)],
        [_p("Valid From", cell_style), _p(certificate.get("not_before", "N/A"), cell_style)],
        [_p("Valid Until", cell_style), _p(certificate.get("not_after", "N/A"), cell_style)],
        [_p("Days Remaining", cell_style), _p(certificate.get("days_remaining", "N/A"), cell_style)],
        [_p("Issuer", cell_style), _p(certificate.get("issuer", "N/A"), cell_style)],
        [_p("Subject", cell_style), _p(certificate.get("subject", "N/A"), cell_style)],
        [_p("Subject Alt. Names (SAN)", cell_style), _p(", ".join(san) or "N/A", cell_style)],
    ]
    t = Table(ssl_table_data, colWidths=[45 * mm, 125 * mm], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(BRAND_PRIMARY)),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CFD8DC")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F7FA")]),
    ]))
    story.append(t)
    story.append(Spacer(1, 8))

    # =========================== DNS / DNSSEC / WHOIS ===========================
    story.append(Paragraph("3. DNS, DNSSEC &amp; Domain Audit", heading_style))
    dns_data = report.get("dns", {})
    dnssec_data = report.get("dnssec", {})
    whois_data = report.get("whois", {})
    dns_table_data = [
        [_p("Parameter", cell_bold), _p("Result", cell_bold)],
        [_p("A Records", cell_style), _p(", ".join(dns_data.get("A", [])) or "N/A", cell_style)],
        [_p("AAAA Records", cell_style), _p(", ".join(dns_data.get("AAAA", [])) or "N/A", cell_style)],
        [_p("MX Records", cell_style), _p(", ".join(dns_data.get("MX", [])) or "N/A", cell_style)],
        [_p("NS Records", cell_style), _p(", ".join(dns_data.get("NS", [])) or "N/A", cell_style)],
        [_p("CAA Records", cell_style), _p(", ".join(dns_data.get("CAA", [])) or "None (finding)", cell_style)],
        [_p("DNSSEC Enabled", cell_style), _p("YES" if dnssec_data.get("enabled") else "NO", cell_style)],
        [_p("WHOIS Registrar", cell_style), _p(whois_data.get("registrar", "N/A"), cell_style)],
        [_p("Domain Expiration", cell_style), _p(whois_data.get("expiration_date", "N/A"), cell_style)],
        [_p("Days To Expiry", cell_style), _p(whois_data.get("days_to_expiry", "N/A"), cell_style)],
    ]
    t = Table(dns_table_data, colWidths=[45 * mm, 125 * mm], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4527A0")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CFD8DC")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F7FA")]),
    ]))
    story.append(t)
    story.append(PageBreak())

    # =========================== FAILED CHECKS ===========================
    story.append(Paragraph("4. Security Issues &amp; Recommendations", heading_style))
    issues_sorted = sorted(report.get("issues", []), key=lambda i: -severity_rank(i.get("severity")))
    if issues_sorted:
        failed_data = [[_p("Severity", cell_bold), _p("Check", cell_bold),
                         _p("Details", cell_bold), _p("Recommendation", cell_bold)]]
        for i in issues_sorted:
            failed_data.append([
                _severity_badge(i.get("severity", ""), cell_bold),
                _p(i.get("title", ""), cell_style),
                _p(i.get("details", ""), cell_style),
                _p(i.get("recommendation", ""), cell_style),
            ])
        t = Table(failed_data, colWidths=[18 * mm, 38 * mm, 62 * mm, 52 * mm], repeatRows=1)
        row_colors = []
        for i in issues_sorted:
            row_colors.append(colors.HexColor("#FDEDEE") if severity_rank(i.get("severity")) >= 3
                               else colors.white)
        style_cmds = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(SEVERITY_COLORS["CRITICAL"])),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CFD8DC")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]
        for idx, rc in enumerate(row_colors, start=1):
            style_cmds.append(("BACKGROUND", (0, idx), (-1, idx), rc))
        t.setStyle(TableStyle(style_cmds))
        story.append(t)
    else:
        story.append(Paragraph("No failing checks were identified.", normal_style))
    story.append(PageBreak())

    # =========================== PASSED CHECKS ===========================
    story.append(Paragraph("5. Successful Security Checks", heading_style))
    passed = report.get("passed_checks", [])
    if passed:
        success_data = [[_p("Check", cell_bold), _p("Severity", cell_bold), _p("Details", cell_bold)]]
        for c in passed:
            success_data.append([
                _p(c.get("check", ""), cell_style),
                _severity_badge(c.get("severity", ""), cell_bold),
                _p(c.get("details", ""), cell_style),
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
        story.append(Paragraph("No checks passed during this scan.", normal_style))
    story.append(PageBreak())

    # =========================== SENSITIVE PATHS ===========================
    story.append(Paragraph("6. Sensitive Path Enumeration", heading_style))
    sensitive_paths = report.get("sensitive_paths", [])
    if sensitive_paths:
        path_data = [[_p("Path", cell_bold), _p("HTTP Status", cell_bold),
                      _p("Risk", cell_bold), _p("Exposed", cell_bold)]]
        for item in sensitive_paths:
            path_data.append([
                _p(item.get("path", ""), cell_style),
                _p(item.get("status", ""), cell_style),
                _p(item.get("risk", ""), cell_style),
                _severity_badge("YES" if item.get("exposed") else "NO",
                                 cell_bold if item.get("exposed") else cell_style),
            ])
        t = Table(path_data, colWidths=[70 * mm, 35 * mm, 30 * mm, 35 * mm], repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#455A64")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CFD8DC")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F7FA")]),
        ]))
        story.append(t)
    else:
        story.append(Paragraph("No sensitive paths were tested during this scan.", normal_style))
    story.append(Spacer(1, 8))

    # =========================== COOKIES ===========================
    story.append(Paragraph("7. Cookie Security", heading_style))
    cookies = report.get("cookies", [])
    if cookies:
        cookie_data = [[_p("Cookie", cell_bold), _p("Secure", cell_bold),
                         _p("HttpOnly", cell_bold), _p("SameSite", cell_bold)]]
        for c in cookies:
            cookie_data.append([
                _p(c.get("name", ""), cell_style),
                _p(str(c.get("secure", False)), cell_style),
                _p(str(c.get("http_only", False)), cell_style),
                _p(str(c.get("same_site", "")), cell_style),
            ])
        t = Table(cookie_data, colWidths=[60 * mm, 35 * mm, 35 * mm, 40 * mm], repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#455A64")),
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
            normal_style
        ))
    story.append(PageBreak())

    # =========================== RECOMMENDATIONS ===========================
    story.append(Paragraph("8. Prioritized Recommendations", heading_style))
    recommendations = report.get("recommendations", [])
    if recommendations:
        for idx, recommendation in enumerate(recommendations, start=1):
            story.append(_p(f"{idx}. {recommendation}", normal_style))
            story.append(Spacer(1, 3))
    else:
        story.append(Paragraph("No outstanding recommendations - all checks passed.", normal_style))

    story.append(PageBreak())

    # =========================== AI SUGGESTIONS (OVERALL REVIEW) ===========================
    story.append(Paragraph("9. AI Overall Review &amp; Suggestions", heading_style))

    ai_text = _generate_security_ai_suggestions(report)

    for para in ai_text.split("\n"):
        para = para.strip()
        if not para:
            story.append(Spacer(1, 4))
            continue
        story.append(_p(para, normal_style))

    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=0.6, color=colors.HexColor("#CFD8DC")))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        f"Generated by {BRAND_NAME}  Security Audit  - automated scan results should be "
        "validated by a qualified security professional before remediation sign-off.",
        small_style
    ))

    document.build(
        story,
        onFirstPage=lambda c, d: _header_footer(c, d, report),
        onLaterPages=lambda c, d: _header_footer(c, d, report),
    )
    print(f"PDF report saved : {pdf_path}")
    return pdf_path


# ============================================================
# STANDALONE TEST
# ============================================================

if __name__ == "__main__":
    website_url = input("Enter website URL: ").strip()
    report = security_audit(website_url)
    print("\nJSON report:")
    print(json.dumps(report, indent=4, ensure_ascii=False, default=str))
    print("\nPDF:")
    print(report.get("pdf_report", "PDF generation failed"))