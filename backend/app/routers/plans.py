import os
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.plans import require_plan, PLAN_FEATURES
from app.database.dependency import get_db
from app.models.user import User
from app.schemas.website_test import WebsiteTestRequest

from app.services.website_service import test_website
from app.services.seo_service import seo_check
from app.services.advanced_seo_service import advanced_seo_check
from app.services.accessibility_service import accessibility_check
from app.services.performance_service import performance_check
from app.services.basic_validation_service import (
    basic_content_validation,
    basic_image_validation,
)
from app.services.functional_testing_service import functional_testing
from app.services.groq_service import generate_ai_suggestions
from app.services.security_testing import security_audit
from app.services.content_audit_service import content_audit
from app.services.ux_audit_service import ux_audit
from app.services.cro_audit_service import cro_audit
from app.services.technical_audit_service import technical_audit
from app.services.dashboard_service import update_dashboard_stats
from app.services.website_db_service import save_website_test, save_functional_test_result
from app.services.website_severity_service import calculate_website_severity
from app.services.plan_pdf_service import (
    generate_basic_pdf_report,
    generate_standard_pdf_report,
    generate_premium_pdf_report,
)

router = APIRouter(
    prefix="/plans",
    tags=["Plans"]
)


def _new_report_path(plan: str, user_id: int) -> str:
    """A unique, persistent path for this one report. Previously every
    tier reused a fixed filename (e.g. Basic_Website_Report.pdf) which
    the next scan - by ANY user - would silently overwrite, so nothing
    could ever be re-downloaded from history."""
    os.makedirs("reports", exist_ok=True)
    return os.path.join("reports", f"{plan}_{user_id}_{uuid.uuid4().hex}.pdf")


@router.get("/features")
def plan_features():
    """Public reference of what each plan tier includes."""
    return PLAN_FEATURES


# ============================================================
# BASIC PLAN
# Basic SEO, basic accessibility, availability, basic performance,
# basic content validation, basic image validation -> basic PDF report.
# ============================================================

@router.post("/basic/report")
def basic_plan_report(
    data: WebsiteTestRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_plan("basic"))
):
    website = test_website(data.url)
    seo = seo_check(data.url)
    accessibility = accessibility_check(data.url)
    performance = performance_check(data.url)
    content = basic_content_validation(data.url)
    image = basic_image_validation(data.url)

    report_data = {
        "url": data.url,
        "website": website,
        "seo": seo,
        "accessibility": accessibility,
        "performance": performance,
        "content_validation": content,
        "image_validation": image,
    }

    pdf_path = generate_basic_pdf_report(
        report_data,
        filename=_new_report_path("basic", current_user.id)
    )

    save_website_test(
        db=db,
        url=data.url,
        website=website,
        seo=seo,
        accessibility=accessibility,
        performance=performance,
        security={},
        broken={},
        ai={"content_validation": content, "image_validation": image},
        severity=calculate_website_severity(website.get("health_score", 0)),
        user_id=current_user.id,
        plan="basic",
        report_path=pdf_path,
    )
    update_dashboard_stats(db, "website_tests", user_id=current_user.id)
    update_dashboard_stats(db, "reports_generated", user_id=current_user.id)

    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename="TestPilot_Basic_Report.pdf"
    )


@router.post("/basic/test")
def basic_plan_test(
    data: WebsiteTestRequest,
    current_user: User = Depends(require_plan("basic"))
):
    """Same checks as /basic/report, returned as JSON instead of a PDF."""

    return {
        "plan": "basic",
        "url": data.url,
        "website": test_website(data.url),
        "seo": seo_check(data.url),
        "accessibility": accessibility_check(data.url),
        "performance": performance_check(data.url),
        "content_validation": basic_content_validation(data.url),
        "image_validation": basic_image_validation(data.url),
    }


# ============================================================
# STANDARD PLAN
# Functional testing (navigation, links, forms, auth, responsive,
# browser compatibility, broken resources, console errors, API
# validation), advanced SEO, advanced accessibility, AI
# recommendations -> detailed PDF report.
# ============================================================

@router.post("/standard/report")
def standard_plan_report(
    data: WebsiteTestRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_plan("standard"))
):
    website = test_website(data.url)
    seo = advanced_seo_check(data.url)
    accessibility = accessibility_check(data.url)
    performance = performance_check(data.url)
    functional = functional_testing(data.url)

    prompt = f"""
    Website URL: {data.url}

    Website Health Score: {website.get("health_score", 0)}
    Advanced SEO Score: {seo.get("seo_score", 0)}
    Accessibility Score: {accessibility.get("accessibility_score", 0)}
    Performance Score: {performance.get("performance_score", 0)}
    Functional Testing Score: {functional.get("functional_score", 0)}
    Functional Modules Passed: {functional.get("passed", 0)}
    Functional Modules Failed: {functional.get("failed", 0)}

    As a senior QA engineer, provide:
    1. Overall website quality summary.
    2. Top functional issues to fix first.
    3. SEO and accessibility improvements.
    4. Priority-wise developer action items.
    """

    ai_suggestions = generate_ai_suggestions(prompt)

    report_data = {
        "url": data.url,
        "website": website,
        "seo": seo,
        "accessibility": accessibility,
        "performance": performance,
        "functional": functional,
        "ai_suggestions": ai_suggestions,
    }

    pdf_path = generate_standard_pdf_report(
        report_data,
        filename=_new_report_path("standard", current_user.id)
    )

    save_website_test(
        db=db,
        url=data.url,
        website=website,
        seo=seo,
        accessibility=accessibility,
        performance=performance,
        security={},
        broken={},
        ai=ai_suggestions,
        severity=calculate_website_severity(website.get("health_score", 0)),
        user_id=current_user.id,
        plan="standard",
        report_path=pdf_path,
    )
    save_functional_test_result(
        db=db,
        url=data.url,
        functional=functional
    )
    update_dashboard_stats(db, "website_tests", user_id=current_user.id)
    update_dashboard_stats(db, "reports_generated", user_id=current_user.id)
    update_dashboard_stats(db, "ai_suggestions", user_id=current_user.id)

    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename="TestPilot_Standard_Report.pdf"
    )


@router.post("/standard/test")
def standard_plan_test(
    data: WebsiteTestRequest,
    current_user: User = Depends(require_plan("standard"))
):
    """Same checks as /standard/report, returned as JSON instead of a PDF."""

    website = test_website(data.url)
    seo = advanced_seo_check(data.url)
    accessibility = accessibility_check(data.url)
    performance = performance_check(data.url)
    functional = functional_testing(data.url)

    prompt = f"""
    Website URL: {data.url}
    Website Health Score: {website.get("health_score", 0)}
    Advanced SEO Score: {seo.get("seo_score", 0)}
    Accessibility Score: {accessibility.get("accessibility_score", 0)}
    Performance Score: {performance.get("performance_score", 0)}
    Functional Testing Score: {functional.get("functional_score", 0)}

    Provide a concise QA summary and priority action items.
    """

    return {
        "plan": "standard",
        "url": data.url,
        "website": website,
        "seo": seo,
        "accessibility": accessibility,
        "performance": performance,
        "functional": functional,
        "ai_suggestions": generate_ai_suggestions(prompt),
    }


# ============================================================
# PREMIUM PLAN
# Everything in Standard (functional testing, advanced SEO, advanced
# accessibility, performance, AI recommendations) COMBINED with a full
# website audit: Security, Content, UX, CRO and Technical (broken links,
# redirects, caching/compression, Core Web Vitals) -> one combined JSON
# response and one combined PDF report.
# ============================================================

def _run_standard_checks(url: str):
    """Shared helper: runs the same checks the Standard plan runs, so the
    Premium plan can combine them with its security audit instead of
    running the security audit alone."""

    website = test_website(url)
    seo = advanced_seo_check(url)
    accessibility = accessibility_check(url)
    performance = performance_check(url)
    functional = functional_testing(url)

    prompt = f"""
    Website URL: {url}

    Website Health Score: {website.get("health_score", 0)}
    Advanced SEO Score: {seo.get("seo_score", 0)}
    Accessibility Score: {accessibility.get("accessibility_score", 0)}
    Performance Score: {performance.get("performance_score", 0)}
    Functional Testing Score: {functional.get("functional_score", 0)}
    Functional Modules Passed: {functional.get("passed", 0)}
    Functional Modules Failed: {functional.get("failed", 0)}

    As a senior QA engineer, provide:
    1. Overall website quality summary.
    2. Top functional issues to fix first.
    3. SEO and accessibility improvements.
    4. Priority-wise developer action items.
    """

    ai_suggestions = generate_ai_suggestions(prompt)

    return {
        "website": website,
        "seo": seo,
        "accessibility": accessibility,
        "performance": performance,
        "functional": functional,
        "ai_suggestions": ai_suggestions,
    }


def _run_premium_only_checks(url: str):
    """Runs the extra audit categories that make Premium a full website
    audit on top of Standard + Security: Content, UX, CRO and Technical
    (broken links/redirects, caching/compression, Core Web Vitals)."""

    return {
        "content": content_audit(url),
        "ux": ux_audit(url),
        "cro": cro_audit(url),
        "technical": technical_audit(url),
    }


@router.post("/premium/security-audit")
def premium_plan_security_audit(
    data: WebsiteTestRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_plan("premium"))
):
    """
    Premium = Standard plan features + a full website audit, combined.

    Returns the Standard-plan checks (functional testing, advanced SEO,
    advanced accessibility, performance, AI recommendations) together with
    the full security audit, plus real Content, UX, CRO and Technical
    audit results, in the same response body. Includes the path to the
    generated security audit PDF. Download it via
    GET /plans/premium/security-audit/pdf?path=<security.pdf_report>.
    """

    standard = _run_standard_checks(data.url)
    security = security_audit(data.url, db, current_user.id)
    extra = _run_premium_only_checks(data.url)

    website = standard["website"]
    functional = standard["functional"]

    save_website_test(
        db=db,
        url=data.url,
        website=website,
        seo=standard["seo"],
        accessibility=standard["accessibility"],
        performance=standard["performance"],
        security=security,
        broken=extra["technical"].get("crawl", {}),
        ai=standard["ai_suggestions"],
        severity=calculate_website_severity(website.get("health_score", 0)),
        user_id=current_user.id,
        plan="premium",
        report_path=security.get("pdf_report"),
    )
    save_functional_test_result(
        db=db,
        url=data.url,
        functional=functional
    )
    update_dashboard_stats(db, "website_tests", user_id=current_user.id)
    update_dashboard_stats(db, "reports_generated", user_id=current_user.id)
    update_dashboard_stats(db, "ai_suggestions", user_id=current_user.id)

    return {
        "plan": "premium",
        "url": data.url,
        "website": website,
        "seo": standard["seo"],
        "accessibility": standard["accessibility"],
        "performance": standard["performance"],
        "functional": functional,
        "ai_suggestions": standard["ai_suggestions"],
        "security": security,
        "content": extra["content"],
        "ux": extra["ux"],
        "cro": extra["cro"],
        "technical": extra["technical"],
    }


@router.post("/premium/report")
def premium_plan_report(
    data: WebsiteTestRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_plan("premium"))
):
    """
    Same combined checks as POST /plans/premium/security-audit (Standard
    plan features + full website audit: Security, Content, UX, CRO and
    Technical), returned as a single combined PDF report instead of JSON.
    """

    standard = _run_standard_checks(data.url)
    security = security_audit(data.url, db, current_user.id)
    extra = _run_premium_only_checks(data.url)

    website = standard["website"]
    functional = standard["functional"]

    report_data = {
        "url": data.url,
        "website": website,
        "seo": standard["seo"],
        "accessibility": standard["accessibility"],
        "performance": standard["performance"],
        "functional": functional,
        "ai_suggestions": standard["ai_suggestions"],
        "security": security,
        "content": extra["content"],
        "ux": extra["ux"],
        "cro": extra["cro"],
        "technical": extra["technical"],
    }

    pdf_path = generate_premium_pdf_report(
        report_data,
        filename=_new_report_path("premium", current_user.id)
    )

    save_website_test(
        db=db,
        url=data.url,
        website=website,
        seo=standard["seo"],
        accessibility=standard["accessibility"],
        performance=standard["performance"],
        security=security,
        broken=extra["technical"].get("crawl", {}),
        ai=standard["ai_suggestions"],
        severity=calculate_website_severity(website.get("health_score", 0)),
        user_id=current_user.id,
        plan="premium",
        report_path=pdf_path,
    )
    save_functional_test_result(
        db=db,
        url=data.url,
        functional=functional
    )
    update_dashboard_stats(db, "website_tests", user_id=current_user.id)
    update_dashboard_stats(db, "reports_generated", user_id=current_user.id)
    update_dashboard_stats(db, "ai_suggestions", user_id=current_user.id)

    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename="TestPilot_Premium_Report.pdf"
    )


@router.get("/premium/security-audit/pdf")
def download_premium_security_pdf(
    path: str,
    current_user: User = Depends(require_plan("premium"))
):
    """
    Downloads a previously generated security audit PDF.
    `path` is the `pdf_report` value returned by POST /plans/premium/security-audit.

    Only files inside the `security_reports` directory can be downloaded, to
    prevent this endpoint being used to read arbitrary files off the server.
    """

    reports_dir = os.path.abspath("security_reports")
    requested_path = os.path.abspath(path)

    if os.path.commonpath([reports_dir, requested_path]) != reports_dir:
        raise HTTPException(status_code=400, detail="Invalid report path.")

    if not os.path.isfile(requested_path):
        raise HTTPException(status_code=404, detail="Report file not found.")

    return FileResponse(
        requested_path,
        media_type="application/pdf",
        filename="TestPilot_Security_Audit_Report.pdf"
    )