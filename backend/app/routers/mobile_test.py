import os
import shutil
import time
import zipfile

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.plans import PLAN_RANK, TEMP_ALLOW_ALL_PLANS_NO_PAYMENT
from app.database.dependency import get_db
from app.models.user import User
from app.schemas.mobile_test import MobileTestHistoryItem
from app.services.dashboard_service import update_dashboard_stats
from app.services.mobile_analysis_service import analyze_mobile_app, detect_platform
from app.services.mobile_db_service import (
    get_user_mobile_test_by_id,
    get_user_mobile_tests,
    save_mobile_test,
)
from app.services.mobile_pdf_service import generate_mobile_pdf

router = APIRouter(prefix="/mobile", tags=["Mobile App Testing"])

UPLOAD_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads", "mobile"
)
os.makedirs(UPLOAD_DIR, exist_ok=True)

MAX_UPLOAD_BYTES = 300 * 1024 * 1024  # 300MB - generous for a real app binary

# Plan -> (allowed platforms, scan depth). Free/basic can only scan Android
# and only gets the basic-tier checks; standard unlocks iOS + deeper
# checks; premium adds the full security scan.
PLAN_MOBILE_CONFIG = {
    "basic": {"platforms": {"android"}, "depth": "basic"},
    "standard": {"platforms": {"android", "ios"}, "depth": "standard"},
    "premium": {"platforms": {"android", "ios"}, "depth": "premium"},
}

# Safest possible fallback when we truly have no signal for which plan to
# scan at (invalid/missing selected_plan during the TEMP no-payment period).
# Deliberately the SHALLOWEST tier, not the deepest - under-scanning is a
# missing feature, over-scanning silently hands out Premium for free.
_TEMP_DEFAULT_PLAN = "basic"


def _require_mobile_access(platform: str, current_user: User, selected_plan: str | None) -> str:
    """Validates the user's plan allows testing this platform and returns
    the scan depth to run at. Mirrors the spirit of core.plans.require_plan
    but needs custom logic here because access depends on BOTH the plan
    and the platform being tested (basic = Android only), and mobile
    testing is a single shared endpoint rather than one route per plan.

    TEMP: while TEMP_ALLOW_ALL_PLANS_NO_PAYMENT is True (see
    app/core/plans.py - Razorpay isn't wired up yet), nobody has a real
    `current_user.plan` yet, so there is no server-side source of truth for
    which tier to scan at. In that window ONLY, we trust `selected_plan` -
    the tier the user picked in the UI, sent as a form field alongside the
    file - falling back to the safest (basic) tier if it's missing/invalid.

    Once TEMP_ALLOW_ALL_PLANS_NO_PAYMENT is flipped back to False for real
    payments, `selected_plan` is IGNORED completely and only the
    authenticated user's paid-for `current_user.plan` from the database is
    ever used - so this can't be used to spoof a higher tier once money is
    involved.
    """

    if TEMP_ALLOW_ALL_PLANS_NO_PAYMENT:
        plan = (selected_plan or "").lower()
        if plan not in PLAN_MOBILE_CONFIG:
            plan = _TEMP_DEFAULT_PLAN

        config = PLAN_MOBILE_CONFIG[plan]
        if platform not in config["platforms"]:
            raise HTTPException(
                status_code=403,
                detail=(
                    f"iOS (.ipa) app testing requires the Standard or Premium plan. "
                    f"You selected '{plan}', which only covers Android (.apk)."
                ),
            )
        return config["depth"]

    if not current_user.plan:
        raise HTTPException(
            status_code=403,
            detail="You don't have an active plan yet. Subscribe via PUT /users/plan to run mobile app tests.",
        )

    plan = current_user.plan.lower()
    config = PLAN_MOBILE_CONFIG.get(plan)
    if not config:
        raise HTTPException(status_code=403, detail=f"Your account has an invalid plan ('{current_user.plan}').")

    if platform not in config["platforms"]:
        raise HTTPException(
            status_code=403,
            detail=(
                f"iOS (.ipa) app testing requires the Standard or Premium plan. "
                f"Your current plan is '{plan}', which only covers Android (.apk) basic checks. "
                "Switch plans via PUT /users/plan to unlock this."
            ),
        )

    return config["depth"]


@router.post("/test")
async def mobile_test(
    file: UploadFile = File(...),
    selected_plan: str | None = Form(
        None,
        description=(
            "Which plan tier to scan at ('basic' | 'standard' | 'premium'). Only honored "
            "while TEMP_ALLOW_ALL_PLANS_NO_PAYMENT is True (pre-payment testing) - ignored "
            "once real payments are live, when the user's paid `current_user.plan` is used "
            "instead so this can't be used to get a higher tier for free."
        ),
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upload a .apk or .ipa and run a real static analysis pass on it.
    Depth of the scan (basic/standard/premium) is resolved from the
    caller's subscription plan (or, pre-payment, the plan they picked in
    the UI), and iOS is gated to standard/premium."""

    platform = detect_platform(file.filename or "")
    if platform is None:
        raise HTTPException(
            status_code=400,
            detail="Unsupported file type. Upload an Android .apk or an iOS .ipa file.",
        )

    depth = _require_mobile_access(platform, current_user, selected_plan)

    safe_name = "".join(c for c in (file.filename or "upload") if c.isalnum() or c in ("_", "-", ".")) or "upload"
    dest_path = os.path.join(UPLOAD_DIR, f"{int(time.time() * 1000)}_{safe_name}")

    size = 0
    try:
        with open(dest_path, "wb") as out:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_UPLOAD_BYTES:
                    raise HTTPException(status_code=413, detail="File too large (limit 300MB).")
                out.write(chunk)
    finally:
        await file.close()

    if not zipfile.is_zipfile(dest_path):
        os.remove(dest_path)
        raise HTTPException(status_code=400, detail="File is not a valid APK/IPA (not a readable zip archive).")

    try:
        analysis = analyze_mobile_app(dest_path, platform, depth)
    except ValueError as exc:
        os.remove(dest_path)
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        os.remove(dest_path)
        raise HTTPException(status_code=422, detail=f"Could not analyze this file: {exc}")
    finally:
        if os.path.exists(dest_path):
            os.remove(dest_path)

    pdf_path = generate_mobile_pdf(analysis, file.filename or "app")

    saved = save_mobile_test(
        db=db,
        platform=platform,
        file_name=file.filename or "app",
        analysis=analysis,
        user_id=current_user.id,
        plan=current_user.plan or (selected_plan.lower() if selected_plan else None),
        report_path=pdf_path,
    )
    update_dashboard_stats(db, "mobile_tests")

    # Include the saved row's id so the caller can immediately hit
    # GET /mobile/history/{id}/download without a second round-trip to
    # look it up in history.
    analysis["id"] = saved.id
    return analysis


@router.get("/history", response_model=list[MobileTestHistoryItem])
def mobile_history(
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """This user's own mobile app scan history, most recent first."""
    return get_user_mobile_tests(db, current_user.id, limit=limit)


@router.get("/history/{test_id}/download")
def download_mobile_report(
    test_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    test = get_user_mobile_test_by_id(db, test_id, current_user.id)

    if test is None:
        raise HTTPException(status_code=404, detail="No mobile test history entry found for this user with that id.")

    if not test.report_path or not os.path.isfile(test.report_path):
        raise HTTPException(
            status_code=404,
            detail="No saved report for this scan. Run the test again to get a downloadable report.",
        )

    return FileResponse(
        test.report_path,
        media_type="application/pdf",
        filename=f"TestPilot_Mobile_{(test.plan or 'app').capitalize()}_Report_{test.id}.pdf",
    )