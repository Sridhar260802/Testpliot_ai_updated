from typing import List
import os

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from app.services.dashboard_service import update_dashboard_stats
from app.database.dependency import get_db
from app.schemas.dashboard import DashboardResponse
from app.schemas.website_test import WebsiteTestHistoryItem
from app.services.dashboard_service import get_dashboard_stats
from app.services.website_db_service import get_user_website_tests, get_user_website_test_by_id
from app.core.auth import get_current_user
from app.models.user import User


router = APIRouter(
    prefix="/dashboard",
    tags=["Dashboard"]
)


@router.get("/stats", response_model=DashboardResponse)
def dashboard_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return get_dashboard_stats(db, current_user.id)


@router.get("/history", response_model=List[WebsiteTestHistoryItem])
def dashboard_history(
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Websites this user has tested, most recent first — for the
    'recent audits' list on the dashboard."""
    return get_user_website_tests(db, current_user.id, limit=limit)


@router.get("/history/{test_id}/download")
def download_dashboard_history_report(
    test_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Re-download the PDF for one row in this user's history list."""

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


@router.post("/increment/{field}")
def increment_dashboard(
    field: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return update_dashboard_stats(db, field, user_id=current_user.id)