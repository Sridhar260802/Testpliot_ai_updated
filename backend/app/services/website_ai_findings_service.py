"""
Deterministic "AI Root Cause + Fix Recommendation" and "Remediation
Priority" engine for the Standard / Premium WEBSITE reports.

Mirrors the pattern already used for the mobile app report
(app/services/mobile_analysis_service.py: ROOT_CAUSE_FIX_KB /
_ai_findings / _remediation_priority): a same-turn, KB-driven lookup
per finding title instead of dropping a raw LLM completion straight
into the PDF.

Why this exists: the website Standard/Premium report used to render
`ai_suggestions` (a raw Groq/LLM completion, including any leaked
`<think>...</think>` reasoning block) as one unstructured text blob
under "AI Recommendations" - see report_template.format_ai_recommendations.
That is replaced here with the same clean, deterministic layout the
mobile report already uses, plus the "Remediation Priority" table the
mobile report has and the website report was missing.
"""

import re
from typing import Any, Dict, List, Optional


_SEVERITY_EFFORT_HINT = {
    "Critical": "Immediate - block release",
    "High": "Fix before next release",
    "Medium": "Fix in upcoming sprint",
    "Low": "Backlog / best-effort",
    "Info": "Informational - no action required",
}

_SEVERITY_ORDER = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3, "Info": 4}


def _normalize_severity(sev: Any) -> str:
    """security_testing.py / functional results use upper-case severities
    (CRITICAL/HIGH/MEDIUM/LOW/INFO) - normalize to the Title-case form
    used everywhere in this module and in the mobile report."""
    s = str(sev or "Low").strip().upper()
    mapping = {
        "CRITICAL": "Critical", "HIGH": "High", "MEDIUM": "Medium",
        "LOW": "Low", "INFO": "Info", "WARNING": "Medium", "FAIL": "Medium",
    }
    return mapping.get(s, "Low")


# Deterministic root-cause + fix knowledge base, keyed by finding title.
# Covers the standard security-header/infra checks (security_testing.py)
# and the common functional-test module failures. Anything not listed
# here falls back to a generic write-up (same behaviour as the mobile
# report's KB miss path) instead of failing or omitting the finding.
ROOT_CAUSE_FIX_KB = {
    # ---- Security headers / infra (security_testing.py check titles) ----
    "Content Security Policy": {
        "root_cause": "No Content-Security-Policy header is being sent, usually because CSP was never configured at the web server/CDN/app layer.",
        "fix": "Add a restrictive Content-Security-Policy header (start with default-src 'self' and widen only where needed), and test with Report-Only mode before enforcing.",
    },
    "X-Content-Type-Options": {
        "root_cause": "The X-Content-Type-Options header is missing, so browsers may MIME-sniff response bodies instead of trusting the declared Content-Type.",
        "fix": "Add X-Content-Type-Options: nosniff at the web server or CDN edge config for all responses.",
    },
    "X-Frame-Options": {
        "root_cause": "Neither X-Frame-Options nor a CSP frame-ancestors directive is set, so the page can be embedded in a third-party iframe.",
        "fix": "Add X-Frame-Options: DENY or SAMEORIGIN, or a CSP frame-ancestors directive, to prevent clickjacking.",
    },
    "Referrer Policy": {
        "root_cause": "No Referrer-Policy header is configured, so the browser falls back to sending the full referrer URL (including any query-string data) to third-party destinations.",
        "fix": "Add a Referrer-Policy header (e.g. strict-origin-when-cross-origin) at the server/CDN layer.",
    },
    "Permissions Policy": {
        "root_cause": "No Permissions-Policy header is configured, leaving default browser-feature access (camera, geolocation, etc.) unrestricted for embedded/third-party content.",
        "fix": "Add a Permissions-Policy header that explicitly disables features the site doesn't use.",
    },
    "CSP Strength": {
        "root_cause": "No Content-Security-Policy header was found at all, so there is no first line of defense against injected scripts.",
        "fix": "Implement a restrictive Content-Security-Policy and validate it doesn't break existing scripts/styles before enforcing.",
    },
    "Clickjacking Protection": {
        "root_cause": "Neither X-Frame-Options nor a CSP frame-ancestors directive is present, so any site can frame this page.",
        "fix": "Add X-Frame-Options: DENY/SAMEORIGIN or a CSP frame-ancestors directive.",
    },
    "CORS Wildcard": {
        "root_cause": "Access-Control-Allow-Origin is set to '*' (or reflects any Origin), typically added to unblock a frontend during development and never scoped down.",
        "fix": "Restrict CORS to an explicit allow-list of trusted origins, and never combine a wildcard origin with Access-Control-Allow-Credentials.",
    },
    "CORS Configuration": {
        "root_cause": "The CORS policy is broader than the application actually needs, often from copying a permissive example configuration.",
        "fix": "Restrict Access-Control-Allow-Origin to the specific origins that need cross-origin access.",
    },
    "HSTS Strength": {
        "root_cause": "The Strict-Transport-Security header is present but missing includeSubDomains and/or preload, or uses a short max-age, usually left at a framework/CDN default.",
        "fix": "Strengthen HSTS: max-age >= 31536000; includeSubDomains; preload - and submit the domain to the HSTS preload list once subdomains are verified HTTPS-only.",
    },
    "Information Disclosure - server": {
        "root_cause": "The Server (or equivalent) response header exposes the underlying platform/technology, which helps an attacker fingerprint the stack.",
        "fix": "Remove or generic-ize the Server header at the web server/CDN/proxy layer.",
    },
    "Information Disclosure - X-Powered-By": {
        "root_cause": "The X-Powered-By header exposes the backend framework/version by default.",
        "fix": "Disable or strip the X-Powered-By header at the framework/server config layer.",
    },
    "Information Disclosure": {
        "root_cause": "One or more response headers expose implementation details (server, framework, or version) beyond what's operationally necessary.",
        "fix": "Audit response headers and strip anything that reveals stack/version details not needed by legitimate clients.",
    },
    "Security.txt (RFC 9116)": {
        "root_cause": "No /.well-known/security.txt file has been published, so there is no documented channel for responsible vulnerability disclosure.",
        "fix": "Publish a /.well-known/security.txt file (RFC 9116) with a contact and disclosure policy.",
    },
    "DNS - SPF Record": {
        "root_cause": "No SPF TXT record is published for the domain, so mail servers can't verify which senders are authorized to send mail on the domain's behalf.",
        "fix": "Publish an SPF TXT record listing authorized mail senders to reduce email spoofing risk.",
    },
    "DNSSEC": {
        "root_cause": "DNSSEC has not been enabled at the domain's DNS provider/registrar, leaving DNS responses unsigned and open to spoofing/cache-poisoning.",
        "fix": "Enable DNSSEC at the domain registrar / DNS provider to cryptographically sign DNS responses.",
    },
    "Cross-Origin-Opener-Policy": {
        "root_cause": "No Cross-Origin-Opener-Policy header is set, so the page's browsing context can still share a process/window reference with cross-origin popups.",
        "fix": "Add a Cross-Origin-Opener-Policy: same-origin (or same-origin-allow-popups) header to isolate the browsing context.",
    },
    "Cross-Origin-Resource-Policy": {
        "root_cause": "No Cross-Origin-Resource-Policy header is set, so responses can be loaded cross-origin by default.",
        "fix": "Add a Cross-Origin-Resource-Policy header (same-site or same-origin) for resources that don't need to be loaded by other sites.",
    },
    "Cross-Origin-Embedder-Policy": {
        "root_cause": "No Cross-Origin-Embedder-Policy header is set, which is required alongside COOP for full cross-origin isolation.",
        "fix": "Add a Cross-Origin-Embedder-Policy header (require-corp) once all embedded cross-origin resources send compatible CORP/CORS headers.",
    },
    "X-Permitted-Cross-Domain-Policies": {
        "root_cause": "No X-Permitted-Cross-Domain-Policies header is set, leaving the legacy Flash/PDF cross-domain policy surface at its (permissive) default.",
        "fix": "Add X-Permitted-Cross-Domain-Policies: none unless a legacy cross-domain policy file is genuinely required.",
    },
    "Subresource Integrity (SRI)": {
        "root_cause": "One or more externally-hosted scripts are loaded without an integrity attribute, so a compromised third-party host could silently serve modified code.",
        "fix": "Add integrity + crossorigin attributes to externally-hosted <script>/<link> tags, generated from the current file hash.",
    },
    "Mixed Content": {
        "root_cause": "The page (served over HTTPS) references one or more resources over plain HTTP, usually a hardcoded absolute http:// URL left over from before the HTTPS migration.",
        "fix": "Change all hardcoded resource URLs to https:// or protocol-relative, and enforce upgrade-insecure-requests via CSP as a safety net.",
    },
}


def _root_cause_and_fix(title: str) -> Optional[Dict[str, str]]:
    return ROOT_CAUSE_FIX_KB.get(title)


def _generic_kb_entry() -> Dict[str, str]:
    return {
        "root_cause": "See the finding detail above for the specific condition that triggered this check.",
        "fix": "Review the finding detail and apply the relevant web security / QA best practice for this check.",
    }


# ---------------------------------------------------------------------
# Collecting findings from the already-computed audit data
# ---------------------------------------------------------------------

def _collect_functional_issues(functional: Dict[str, Any]) -> List[Dict[str, str]]:
    issues = []
    for m in functional.get("results", []) or []:
        if str(m.get("status", "")).upper() != "FAIL":
            continue
        issues.append({
            "severity": "Medium",
            "title": m.get("module", "Functional Module"),
            "detail": m.get("issue") or "Functional test failure detected - see Functional Testing Summary for detail.",
        })
    return issues


def _collect_string_issues(source: Dict[str, Any], severity: str) -> List[Dict[str, str]]:
    """For sections (SEO/Accessibility/Performance/Content/UX/CRO/Technical)
    whose `issues` are plain human-readable strings rather than structured
    {severity, title} dicts - each string becomes its own finding, using
    the string itself as the title (KB lookups on these will normally
    fall back to the generic entry, same as an unmapped mobile finding)."""
    out = []
    for s in source.get("issues", []) or []:
        text = str(s).strip()
        if not text:
            continue
        out.append({"severity": severity, "title": text, "detail": text})
    return out


def _collect_security_issues(security: Dict[str, Any]) -> List[Dict[str, str]]:
    issues = []
    for i in security.get("issues", []) or []:
        issues.append({
            "severity": _normalize_severity(i.get("severity")),
            "title": i.get("title", "Security Finding"),
            "detail": i.get("details", ""),
            "recommendation": i.get("recommendation", ""),
        })
    return issues


def collect_standard_issues(data: Dict[str, Any]) -> List[Dict[str, str]]:
    """Findings available at the Standard tier: functional test failures
    plus the advanced SEO / accessibility / performance issue lists.
    No security section exists at this tier."""
    issues = []
    issues += _collect_functional_issues(data.get("functional", {}) or {})
    issues += _collect_string_issues(data.get("seo", {}) or {}, "Medium")
    issues += _collect_string_issues(data.get("accessibility", {}) or {}, "Medium")
    issues += _collect_string_issues(data.get("performance", {}) or {}, "Low")
    return issues


def collect_premium_issues(data: Dict[str, Any]) -> List[Dict[str, str]]:
    """Findings available at the Premium tier: everything Standard has,
    plus the full security audit and the Content/UX/CRO/Technical audits."""
    issues = collect_standard_issues(data)
    issues += _collect_security_issues(data.get("security", {}) or {})
    issues += _collect_string_issues(data.get("content", {}) or {}, "Low")
    issues += _collect_string_issues(data.get("ux", {}) or {}, "Low")
    issues += _collect_string_issues(data.get("cro", {}) or {}, "Low")
    issues += _collect_string_issues(data.get("technical", {}) or {}, "Medium")
    return issues


# ---------------------------------------------------------------------
# AI Root Cause + Fix Recommendation / Remediation Priority
# ---------------------------------------------------------------------

def ai_findings(issues: List[Dict[str, str]], depth: str = "premium") -> List[Dict[str, str]]:
    """depth='premium': full root-cause + fix write-up per finding (KB
    lookup, generic fallback if the title isn't in the KB).
    depth='standard': lighter severity-driven guidance only, no KB
    write-up - mirrors the mobile report's standard-depth behaviour."""
    findings = []

    if depth == "standard":
        for i in issues:
            findings.append({
                "title": i["title"],
                "severity": i["severity"],
                "recommendation": (
                    f"{_SEVERITY_EFFORT_HINT.get(i['severity'], 'Review')} - see finding detail for "
                    "the specific condition. Upgrade to Premium for a full root-cause analysis and "
                    "fix recommendation on this issue."
                ),
            })
        return findings

    for i in issues:
        kb = _root_cause_and_fix(i["title"]) or _generic_kb_entry()
        findings.append({
            "title": i["title"],
            "severity": i["severity"],
            "root_cause": kb["root_cause"],
            "fix_recommendation": i.get("recommendation") or kb["fix"],
        })
    return findings


def remediation_priority(issues: List[Dict[str, str]]) -> List[Dict[str, str]]:
    ranked = sorted(issues, key=lambda i: _SEVERITY_ORDER.get(i["severity"], 99))
    queue = []
    for i in ranked:
        queue.append({
            "severity": i["severity"],
            "title": i["title"],
            "recommended_action": _SEVERITY_EFFORT_HINT.get(i["severity"], "Review"),
        })
    return queue


# ---------------------------------------------------------------------
# Legacy raw-LLM text safety net
# ---------------------------------------------------------------------

_THINK_BLOCK_RE = re.compile(r"<think\b[^>]*>.*?</think>", re.IGNORECASE | re.DOTALL)


def strip_think_blocks(text: str) -> str:
    """Some LLM providers (Groq reasoning models in particular) prepend a
    <think>...</think> reasoning block ahead of the actual answer. If that
    leaks into `text` unstripped it renders verbatim in the PDF (this was
    the cause of the wall-of-reasoning-text seen in old Premium reports).
    Kept as a safety net for any caller still passing raw LLM text through
    report_template.format_ai_recommendations."""
    if not text:
        return text
    return _THINK_BLOCK_RE.sub("", str(text)).strip()