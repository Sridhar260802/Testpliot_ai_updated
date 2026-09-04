import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import sessionmaker, declarative_base

# Load .env locally, but do NOT override existing Railway variables
load_dotenv(override=False)

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()

# Debug log to verify Railway injects the right URL
print("--- CONNECTING TO DATABASE ---")
print(f"DATABASE_URL found: {bool(DATABASE_URL)}")

# TEMP DEBUG — remove after fixing
all_env = {k: v for k, v in os.environ.items() if "DATABASE" in k or "POSTGRES" in k}
print(f"DEBUG - env vars: {all_env}")

if DATABASE_URL:
    # Fix protocol prefix for SQLAlchemy 2.0+
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg2://", 1)
    elif DATABASE_URL.startswith("postgresql://"):
        DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://", 1)
        
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
else:
    # Fallback for local development only
    DB_USER = os.getenv("POSTGRES_USER", "postgres")
    DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "Testpilot@123")
    DB_HOST = os.getenv("POSTGRES_HOST", "localhost")
    DB_PORT = os.getenv("POSTGRES_PORT", "5432")
    DB_NAME = os.getenv("POSTGRES_DB", "testpilot")

    database_url = URL.create(
        drivername="postgresql+psycopg2",
        username=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=int(DB_PORT),
        database=DB_NAME,
    )

    engine = create_engine(database_url)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()