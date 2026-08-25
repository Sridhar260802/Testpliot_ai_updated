"""
One-time data migration: copies every row from the old testpilot.db
(SQLite) into the new PostgreSQL database configured in app/database/database.py.

Run this ONLY if you have an existing testpilot.db with real data you
need to keep. On a fresh checkout with no testpilot.db, you don't need
this at all — just start the app and PostgreSQL tables are created
empty by main.py's Base.metadata.create_all().

Usage:
    cd backend
    python migrate_sqlite_to_postgres.py
    python migrate_sqlite_to_postgres.py --sqlite-path /path/to/testpilot.db

What it does, in order:
    1. Connects to the old SQLite file (default: ./testpilot.db).
    2. Connects to PostgreSQL using the same settings app/database/database.py
       uses (env vars / .env, or the built-in defaults — db "testpilot",
       user "postgres").
    3. Creates all tables in PostgreSQL if they don't exist yet
       (Base.metadata.create_all — safe to run even if they already exist).
    4. For every table that exists in the SQLite file, copies its rows into
       the matching PostgreSQL table, skipping rows whose primary key
       already exists there (safe to re-run).
    5. Resets each table's auto-increment sequence in PostgreSQL to match
       the highest copied id, so new rows created after migration don't
       collide with migrated ones.

This does not delete or modify the SQLite file — it's read-only here.
"""

import argparse
import os
import sys

from sqlalchemy import create_engine, inspect, MetaData, Table, select, text

# Make sure `app.*` imports resolve when this script is run from the
# backend/ directory (same place app/ lives).
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database.database import Base, engine as postgres_engine, DATABASE_URL  # noqa: E402

# Import every model so Base.metadata knows about all tables before
# create_all() runs — same imports main.py does at startup.
from app.models.user import User  # noqa: E402,F401
from app.models.dashboard import DashboardStats  # noqa: E402,F401
from app.models.website_test import WebsiteTest, FunctionalTestResult  # noqa: E402,F401
from app.models.security_audit import SecurityAudit  # noqa: E402,F401
from app.models.payment import PaymentTransaction  # noqa: E402,F401
from app.models.mobile_test import MobileAppTest  # noqa: E402,F401
from app.models.code_analysis import CodeAnalysis  # noqa: E402,F401


def migrate(sqlite_path: str) -> None:
    if not os.path.isfile(sqlite_path):
        print(f"No SQLite file found at '{sqlite_path}' — nothing to migrate.")
        print("(This is expected on a fresh checkout. The app will just use an empty PostgreSQL database.)")
        return

    sqlite_url = f"sqlite:///{sqlite_path}"
    print(f"Source (SQLite):   {sqlite_url}")
    print(f"Target (Postgres): {DATABASE_URL.split('@')[-1]}  (credentials hidden)")

    sqlite_engine = create_engine(sqlite_url)

    # 1. Make sure every table exists in Postgres first.
    Base.metadata.create_all(bind=postgres_engine)

    sqlite_inspector = inspect(sqlite_engine)
    sqlite_tables = set(sqlite_inspector.get_table_names())

    postgres_meta = MetaData()
    postgres_meta.reflect(bind=postgres_engine)

    total_copied = 0

    with sqlite_engine.connect() as sconn, postgres_engine.connect() as pconn:
        for table_name in Base.metadata.tables.keys():
            if table_name not in sqlite_tables:
                print(f"  - {table_name}: not present in SQLite, skipping")
                continue

            sqlite_meta = MetaData()
            sqlite_table = Table(table_name, sqlite_meta, autoload_with=sqlite_engine)
            pg_table = postgres_meta.tables[table_name]

            rows = sconn.execute(select(sqlite_table)).mappings().all()
            if not rows:
                print(f"  - {table_name}: 0 rows in SQLite, skipping")
                continue

            pg_columns = set(pg_table.columns.keys())
            existing_ids = set()
            if "id" in pg_columns:
                existing_ids = {
                    r[0] for r in pconn.execute(select(pg_table.c.id))
                }

            to_insert = []
            for row in rows:
                row_dict = {k: v for k, v in dict(row).items() if k in pg_columns}
                if "id" in row_dict and row_dict["id"] in existing_ids:
                    continue  # already migrated — safe to re-run this script
                to_insert.append(row_dict)

            if not to_insert:
                print(f"  - {table_name}: {len(rows)} rows in SQLite, all already migrated")
                continue

            pconn.execute(pg_table.insert(), to_insert)

            # Keep PostgreSQL's SERIAL/IDENTITY sequence ahead of the ids
            # we just inserted by hand, so the next auto-generated id
            # doesn't collide with a migrated row.
            if "id" in pg_columns:
                pconn.execute(
                    text(
                        f"SELECT setval("
                        f"pg_get_serial_sequence('{table_name}', 'id'), "
                        f"COALESCE((SELECT MAX(id) FROM {table_name}), 1)"
                        f")"
                    )
                )

            pconn.commit()
            print(f"  - {table_name}: copied {len(to_insert)} of {len(rows)} rows")
            total_copied += len(to_insert)

    print(f"\nDone. {total_copied} rows migrated into PostgreSQL.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sqlite-path",
        default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "testpilot.db"),
        help="Path to the old SQLite database file (default: ./testpilot.db)",
    )
    args = parser.parse_args()
    migrate(args.sqlite_path)