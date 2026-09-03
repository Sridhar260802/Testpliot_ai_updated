from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import inspect, text

from app.models.dashboard import DashboardStats
from app.database.database import Base, engine
from app.database.dependency import get_db
from app.models.user import User
from app.core.security import hash_password

from app.routers.user import router as user_router
from app.routers.dashboard import router as dashboard_router
from app.models.website_test import WebsiteTest, FunctionalTestResult
from app.models.security_audit import SecurityAudit
from app.models.payment import PaymentTransaction
from app.models.mobile_test import MobileAppTest
from app.routers.website_test import router as website_router
from app.routers.code_analysis import router as code_router
from app.routers.pdf_report import router as pdf_router
from app.routers.security_audit import router as security_audit_router
from app.routers.plans import router as plans_router
from app.routers.payments import router as payments_router
from app.routers.mobile_test import router as mobile_router


# --------------------------------------------------
# CREATE APP
# --------------------------------------------------

app = FastAPI(
    title="TestPilot",
    version="1.0.0",
    description="AI Powered Software Testing Platform",
    swagger_ui_parameters={
        "persistAuthorization": True
    }
)


# --------------------------------------------------
# CORS
# --------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://testpliotfrontend.netlify.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------
# DATABASE
# --------------------------------------------------

Base.metadata.create_all(bind=engine)


# --------------------------------------------------
# WEBSITE TESTS HISTORY COLUMNS
# --------------------------------------------------

def _ensure_website_tests_history_columns():
    """
    PostgreSQL-compatible migration for older databases.

    create_all() creates missing tables, but it does not add
    new columns to an existing table.
    """

    inspector = inspect(engine)

    if "website_tests" not in inspector.get_table_names():
        return

    existing = {
        column["name"]
        for column in inspector.get_columns("website_tests")
    }

    with engine.begin() as conn:

        if "user_id" not in existing:
            conn.execute(
                text(
                    "ALTER TABLE website_tests "
                    "ADD COLUMN user_id INTEGER"
                )
            )

        if "plan" not in existing:
            conn.execute(
                text(
                    "ALTER TABLE website_tests "
                    "ADD COLUMN plan VARCHAR"
                )
            )

        if "created_at" not in existing:
            conn.execute(
                text(
                    "ALTER TABLE website_tests "
                    "ADD COLUMN created_at TIMESTAMP"
                )
            )


_ensure_website_tests_history_columns()


# --------------------------------------------------
# DASHBOARD STATS MOBILE COLUMN
# --------------------------------------------------

def _ensure_dashboard_stats_mobile_column():
    """
    PostgreSQL-compatible migration for dashboard_stats.
    """

    inspector = inspect(engine)

    if "dashboard_stats" not in inspector.get_table_names():
        return

    existing = {
        column["name"]
        for column in inspector.get_columns("dashboard_stats")
    }

    with engine.begin() as conn:

        if "mobile_tests" not in existing:
            conn.execute(
                text(
                    "ALTER TABLE dashboard_stats "
                    "ADD COLUMN mobile_tests INTEGER DEFAULT 0"
                )
            )


_ensure_dashboard_stats_mobile_column()


# --------------------------------------------------
# ROUTERS
# --------------------------------------------------

app.include_router(user_router)
app.include_router(dashboard_router)
app.include_router(website_router)
app.include_router(code_router)
app.include_router(pdf_router)
app.include_router(security_audit_router)
app.include_router(plans_router)
app.include_router(payments_router)
app.include_router(mobile_router)


# --------------------------------------------------
# ROOT
# --------------------------------------------------

@app.get("/")
def root():
    return {
        "message": "TestPilot Backend Running Successfully"
    }


# --------------------------------------------------
# DATABASE TEST
# --------------------------------------------------

@app.get("/db-test")
def db_test(db: Session = Depends(get_db)):
    return {
        "status": "Database Connected Successfully"
    }


# --------------------------------------------------
# HASH TEST
# --------------------------------------------------

@app.get("/hash-test")
def hash_test():
    password = "Test@123"
    hashed = hash_password(password)

    return {
        "original": password,
        "hashed": hashed
    }


# --------------------------------------------------
# FRONTEND CONNECTION TEST
# --------------------------------------------------

@app.get("/api/test")
def test_api():
    return {
        "message": "Backend connected successfully!"
    }