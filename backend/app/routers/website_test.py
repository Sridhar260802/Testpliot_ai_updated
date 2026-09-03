from app.database.dependency import get_db
from fastapi import APIRouter, Depends, security

from app.core.auth import get_current_user
from app.models.user import User
from app.core.auth import get_current_user
from app.models.user import User
from sqlalchemy.orm import Session
from app.database.dependency import get_db
from app.core.auth import get_current_user
from app.models.user import User
from fastapi import HTTPException
from app.services.advanced_seo_service import advanced_seo_check
from app.database.dependency import get_db
from app.schemas.website_test import WebsiteTestRequest
from app.services.accessibility_service import accessibility_check
from app.services.website_service import (
    test_website,
    check_broken_links,
)
from app.services.website_severity_service import calculate_website_severity
from app.services.security_service import security_check
from app.services.performance_service import performance_check
from app.services.groq_service import generate_ai_suggestions
from fastapi.responses import FileResponse
from app.services.dashboard_service import update_dashboard_stats
from app.services.pdf_service import clean_issue_text, generate_pdf_report
from app.services.website_db_service import (
    save_website_test,
    get_all_website_tests,
    get_user_website_tests,
    get_user_website_test_by_id,
)
import os
from app.core.auth import get_current_user
from app.services.advanced_seo_service import advanced_seo_check
from app.services.ai_analysis_service import generate_website_ai_review
from app.services.functional_testing_service import functional_testing
from app.services.security_testing import (
    security_audit,
    generate_security_pdf
)
router = APIRouter(
    prefix="/website",
    tags=["Website Testing"]
)


@router.post("/test")
def website_test(
    data: WebsiteTestRequest,
    db: Session = Depends(get_db)
):
    result = test_website(data.url)

    security = security_check(data.url)

    seo = advanced_seo_check(data.url)
    
    

    performance = performance_check(data.url)

    accessibility = accessibility_check(data.url)
    print("========== PERFORMANCE ==========")
    print(performance)

    print("========== ACCESSIBILITY ==========")
    print(accessibility)

    print("========== SECURITY ==========")
    print(security)

    prompt = f"""
    Website URL: {data.url}

    Health Score: {result.get('health_score',0)}

    SEO Score: {seo.get('seo_score',0)}

    Performance Score: {performance.get('performance_score',0)}

    Accessibility Score: {accessibility.get('accessibility_score',0)}

    Security:
    {security}

    Provide:

    1. Overall Website Health
    2. Critical Issues
    3. SEO Improvements
    4. Security Improvements
    5. Performance Improvements
    6. Developer Action Items

    Return JSON only.
    """

    broken_links = check_broken_links(data.url)

    ai = generate_website_ai_review(
        url=data.url,
        health_score=result.get("health_score",0),
        broken_links=broken_links,
        seo=seo,
        accessibility=accessibility,
        performance=performance,
        security=security
    )


    result.update({

        "seo_score": seo.get("seo_score",0),

        "performance_score": performance.get("performance_score",0),

        "accessibility_score": accessibility.get("accessibility_score",0),

        "security_score": security.get("security_score",0)

    })


    save_website_test(

        db=db,

        url=data.url,

        website=result,

        seo=seo,

        accessibility=accessibility,

        performance=performance,

        security=security,

        broken=broken_links,

        ai=ai,

        severity=calculate_website_severity(result.get("health_score", 0))

    )
    update_dashboard_stats(
        db,"website_tests"
    )
    
    return result


@router.get("/history")
def website_history(
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """This user's own scan history, most recent first.

    Previously this called get_all_website_tests(db) with no auth
    required, so every user's history (every site anyone had ever
    scanned) showed up for everyone. Now it's locked to the logged-in
    user, same as /dashboard/history.
    """
    return get_user_website_tests(db, current_user.id, limit=limit)


@router.get("/history/{test_id}/download")
def download_history_report(
    test_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Re-download the PDF that was generated for one specific past
    scan, without re-running the scan. Only works for a test that
    belongs to the logged-in user, and only for scans made after this
    feature shipped (older rows won't have a saved report_path)."""

    test = get_user_website_test_by_id(db, test_id, current_user.id)

    if test is None:
        raise HTTPException(
            status_code=404,
            detail="No history entry found for this user with that id."
        )

    if not test.report_path or not os.path.isfile(test.report_path):
        raise HTTPException(
            status_code=404,
            detail="No saved report for this scan. Run the test again to get a downloadable report."
        )

    return FileResponse(
        test.report_path,
        media_type="application/pdf",
        filename=f"TestPilot_{(test.plan or 'website').capitalize()}_Report_{test.id}.pdf"
    )


@router.post("/check-links")
def broken_links(
    data: WebsiteTestRequest
):
    return check_broken_links(data.url)


@router.post("/seo")
def seo_test(data:WebsiteTestRequest):
    return advanced_seo_check(data.url)


@router.post("/accessibility")
def accessibility_test(data:WebsiteTestRequest):
    return accessibility_check(data.url)   


@router.post("/performance")
def performance_test(data:WebsiteTestRequest):
    return performance_check(data.url)

@router.post("/ai-test")
def ai_test(data: WebsiteTestRequest):

    website = test_website(data.url)
    broken = check_broken_links(data.url)
    seo = advanced_seo_check(data.url)
    accessibility = accessibility_check(data.url)
    performance = performance_check(data.url)

    prompt = f"""
    Website URL: {data.url}

    Website Health Score: {website.get("health_score", 0)}
    Broken Links: {broken.get("broken_links", 0)}
    SEO Score: {seo.get("seo_score", 0)}
    Accessibility Score: {accessibility.get("accessibility_score", 0)}
    Performance Score: {performance.get("performance_score", 0)}

    Analyze this website and provide:
    1. Overall website health.
    2. SEO improvements.
    3. Accessibility improvements.
    4. Performance improvements.
    5. Priority-wise recommendations.
    """

    return {
        "website": website,
        "broken_links": broken,
        "seo": seo,
        "accessibility": accessibility,
        "performance": performance,
        "ai_suggestions": generate_ai_suggestions(prompt)
    }
    
@router.post("/report")
def report(
    data: WebsiteTestRequest,
    db: Session = Depends(get_db)
):

    
    website = test_website(data.url)
    broken = check_broken_links(data.url)
    seo = advanced_seo_check(data.url)
    accessibility = accessibility_check(data.url)
    performance = performance_check(data.url)
    security = security_check(data.url)

    severity = calculate_website_severity(
        website.get("health_score", 0)
    )
    prompt = f"""
        Website URL: {data.url}

        Website Health Score: {website.get("health_score", 0)}
        Broken Links: {broken.get("broken_links", 0)}
        SEO Score: {seo.get("seo_score", 0)}
        Accessibility Score: {accessibility.get("accessibility_score", 0)}
        Performance Score: {performance.get("performance_score", 0)}

        Analyze this website and provide:

        1. Overall website health.
        2. SEO improvements.
        3. Accessibility improvements.
        4. Performance improvements.
        5. Priority-wise recommendations.
        """

    ai = generate_website_ai_review(
        url=data.url,
        health_score=website.get("health_score", 0),
        broken_links=broken,
        seo=seo,
        accessibility=accessibility,
        performance=performance,
        security=security
    )
    print("========== SEO ==========")
    print(seo)
    report_data = {
        "url": data.url,
        "website": website,
        "seo": seo,
        "performance": performance,
        "accessibility": accessibility,
        "security": security,
        "broken_links": broken,
        "ai_suggestions": ai
    }

    pdf = generate_pdf_report(report_data)
    update_dashboard_stats(
        db,
        "reports_generated"
    )

    return FileResponse(
        pdf,
        media_type="application/pdf",
        filename="Website_Report.pdf"
    )
    
@router.post("/advanced-seo")
def advanced_seo(data: WebsiteTestRequest):
    return advanced_seo_check(data.url)  
@router.post("/security")
def security_test(data: WebsiteTestRequest):
    return security_check(data.url)  
@router.post("/functional")
def functional_test(data: WebsiteTestRequest):

    return functional_testing(data.url)

@router.post("/security_audit")
def security_audit_test(
    data: WebsiteTestRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    report = security_audit(
        data.url,
        db,
        current_user.id
    )

    pdf_path = generate_security_pdf(report)

    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename="TestPilot_Security_Audit_Report.pdf"
    )