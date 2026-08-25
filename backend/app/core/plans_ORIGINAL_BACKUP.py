"""
Central definition of the three subscription tiers (Basic / Standard / Premium)
and a reusable FastAPI dependency that gates a route behind a minimum plan.

Adding a new tier or moving a feature between tiers only requires editing the
data in this file - no changes are needed in the routers that use `require_plan`.
"""

from fastapi import Depends, HTTPException, status

from backend.app.database.core.auth import get_current_user
from app.models.user import User
# Higher number = more access. Every tier includes everything below it.
PLAN_RANK = {
    "basic": 1,
    "standard": 2,
    "premium": 3,
}

VALID_PLANS = tuple(PLAN_RANK.keys())

# ------------------------------------------------------------------
# Plan pricing (INR, whole rupees) - used by the Razorpay integration
# (app/routers/payments.py) to look up the amount to charge for a plan
# instead of trusting a price sent by the frontend.
#
# NOTE: no price configuration existed anywhere in the project before
# this was added (checked models, schemas, services, .env - nothing).
# These are PLACEHOLDER values - replace them with your real prices
# before going live. Nothing else reads this dict, so editing it is
# safe and does not touch PLAN_RANK / PLAN_FEATURES / require_plan.
# ------------------------------------------------------------------
PLAN_PRICES = {
    "basic": 199,
    "standard": 399,
    "premium": 799,
}

# Human readable feature matrix - used by GET /plans/features and to keep the
# routers self-documenting about what each tier actually contains.
PLAN_FEATURES = {
    "basic": {
        "name": "Basic Plan",
        "description": (
            "Essential evaluation features: basic SEO testing, basic accessibility "
            "testing, website availability checks, basic performance checks, basic "
            "content validation and basic image validation. Delivers a basic PDF "
            "report summarizing all checks."
        ),
        "includes": [
            "basic_seo",
            "basic_accessibility",
            "availability_check",
            "basic_performance",
            "basic_content_validation",
            "basic_image_validation",
            "basic_pdf_report",
        ],
    },
    "standard": {
        "name": "Standard Plan",
        "description": (
            "Everything in Basic, plus complete functional testing, navigation and "
            "link testing, forms and validation, authentication testing, responsive "
            "testing, browser compatibility, broken resource testing, advanced SEO, "
            "advanced accessibility, API validation, console error detection, AI "
            "recommendations and a detailed PDF report."
        ),
        "includes": [
            "functional_testing",
            "navigation_and_link_testing",
            "forms_and_validation",
            "authentication_testing",
            "responsive_testing",
            "browser_compatibility",
            "broken_resource_testing",
            "advanced_seo",
            "advanced_accessibility",
            "api_validation",
            "console_error_detection",
            "ai_recommendations",
            "detailed_pdf_report",
        ],
    },
    "premium": {
        "name": "Premium Plan",
        "description": (
            "Everything in Standard, plus a complete website audit across seven "
            "areas. SEO Audit: broken links and crawl errors, missing/duplicate "
            "title tags and meta descriptions, keyword optimization, XML sitemap "
            "and robots.txt, internal linking, mobile-friendliness and indexing "
            "issues. Performance Audit: page loading speed, Core Web Vitals, "
            "image optimization, JS/CSS optimization, caching and compression. "
            "Technical Audit: HTTPS implementation, 301/302 redirects, structured "
            "data (schema markup), canonical tags, crawlability and site "
            "architecture. User Experience (UX) Audit: navigation and menu "
            "structure, mobile responsiveness, readability, accessibility, "
            "calls-to-action (CTAs) and overall usability. Content Audit: "
            "outdated or thin content, duplicate content, content quality and "
            "relevance, grammar and readability, and opportunities for new "
            "content. Security Audit: SSL certificate status, malware "
            "detection, software/plugin updates, security headers and "
            "vulnerability checks (SSL/TLS audit, TLS cipher analysis, cookie "
            "security, CORS audit, HTTP/HTTPS audit, HTTP methods audit, "
            "sensitive path audit, mixed content audit, cache-control audit, "
            "information disclosure audit, security severity analysis and "
            "actionable security recommendations). Conversion Rate Optimization "
            "(CRO) Audit: landing page effectiveness, form usability, checkout "
            "process (for e-commerce), CTA placement, and analytics/conversion "
            "tracking. Delivered as a full audit report in both JSON and PDF "
            "formats."
        ),
        "includes": [
            # SEO Audit
            "broken_links_and_crawl_errors",
            "title_and_meta_description_audit",
            "keyword_optimization",
            "sitemap_and_robots_txt_audit",
            "internal_linking_audit",
            "mobile_friendliness_audit",
            "indexing_issues_audit",
            # Performance Audit
            "page_loading_speed",
            "core_web_vitals",
            "image_optimization_audit",
            "js_css_optimization",
            "caching_and_compression_audit",
            # Technical Audit
            "https_implementation_audit",
            "redirects_audit",
            "structured_data_schema_audit",
            "canonical_tags_audit",
            "crawlability_and_site_architecture",
            # UX Audit
            "navigation_and_menu_audit",
            "mobile_responsiveness_audit",
            "readability_audit",
            "accessibility_audit",
            "cta_audit",
            "overall_usability_audit",
            # Content Audit
            "outdated_and_thin_content_audit",
            "duplicate_content_audit",
            "content_quality_and_relevance",
            "grammar_and_readability_audit",
            "content_opportunities_audit",
            # Security Audit
            "ssl_tls_audit",
            "ssl_certificate_validation",
            "tls_cipher_analysis",
            "malware_detection",
            "software_plugin_update_check",
            "security_headers_audit",
            "cookie_security_audit",
            "cors_audit",
            "http_https_audit",
            "http_methods_audit",
            "sensitive_path_audit",
            "mixed_content_audit",
            "cache_control_audit",
            "information_disclosure_audit",
            "security_severity_analysis",
            "security_recommendations",
            "vulnerability_checks",
            # CRO Audit
            "landing_page_effectiveness",
            "form_usability_audit",
            "checkout_process_audit",
            "cta_placement_audit",
            "analytics_and_conversion_tracking",
            # Report delivery
            "full_audit_json_and_pdf",
        ],
    },
}


def require_plan(required_plan_name: str):
    """
    Dependency factory. Use as:

        @router.post("/plans/premium/security-audit")
        def premium(..., current_user: User = Depends(require_plan("premium"))):
            ...

    Raises 403 unless the authenticated user's plan is EXACTLY
    `required_plan_name`. Plans are exclusive, not tiered: a Basic user can
    only reach Basic routes, a Standard user only Standard routes, a
    Premium user only Premium routes - Premium does NOT also unlock
    Standard/Basic routes (no inheritance between tiers).
    """

    if required_plan_name not in PLAN_RANK:
        raise ValueError(f"Unknown plan '{required_plan_name}'. Must be one of {VALID_PLANS}")

    def _dependency(current_user: User = Depends(get_current_user)) -> User:
        # No plan assigned yet (new signup / Google sign-in that hasn't paid
        # for anything) - never fall back to "basic", block outright.
        if not current_user.plan:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "You don't have an active plan yet. Subscribe to the "
                    f"'{required_plan_name}' plan via PUT /users/plan to access this feature."
                ),
            )

        user_plan = current_user.plan.lower()

        if user_plan not in PLAN_RANK:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Your account has an invalid plan ('{current_user.plan}'). "
                    f"Subscribe via PUT /users/plan to access this feature."
                ),
            )

        if user_plan != required_plan_name:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"This feature is only available on the '{required_plan_name}' plan. "
                    f"Your current plan is '{user_plan}'. Switch plans via "
                    f"PUT /users/plan to access it."
                ),
            )

        return current_user

    return _dependency
