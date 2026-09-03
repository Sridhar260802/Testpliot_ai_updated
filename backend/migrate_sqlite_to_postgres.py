"""
One-time migration from SQLite testpilot.db to PostgreSQL.

Run from backend:
    python migrate_sqlite_to_postgres.py
"""

import argparse
import os
import sys

from sqlalchemy import create_engine, inspect, MetaData, Table, select, text

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database.database import Base, engine as postgres_engine, DATABASE_URL

# Import all models so Base.metadata knows every table.
from app.models.user import User  # noqa: F401,E402
from app.models.dashboard import DashboardStats  # noqa: F401,E402
from app.models.website_test import WebsiteTest, FunctionalTestResult  # noqa: F401,E402
from app.models.security_audit import SecurityAudit  # noqa: F401,E402
from app.models.payment import PaymentTransaction  # noqa: F401,E402
from app.models.mobile_test import MobileAppTest  # noqa: F401,E402
from app.models.code_analysis import CodeAnalysis  # noqa: F401,E402


def migrate(sqlite_path: str) -> None:

    # ---------------------------------------------------------
    # 1. Check SQLite database
    # ---------------------------------------------------------
    if not os.path.isfile(sqlite_path):
        print(f"No SQLite file found at '{sqlite_path}'.")
        print("Nothing to migrate.")
        return

    print(f"Source SQLite: {sqlite_path}")
    print("Target PostgreSQL: connected")

    # ---------------------------------------------------------
    # 2. Create SQLite engine
    # ---------------------------------------------------------
    sqlite_engine = create_engine(
        f"sqlite:///{os.path.abspath(sqlite_path)}"
    )

    # ---------------------------------------------------------
    # 3. Create PostgreSQL tables
    # ---------------------------------------------------------
    print("\nCreating PostgreSQL tables if needed...")
    Base.metadata.create_all(bind=postgres_engine)
    print("PostgreSQL tables ready.")

    # ---------------------------------------------------------
    # 4. Read SQLite table names
    # ---------------------------------------------------------
    sqlite_inspector = inspect(sqlite_engine)
    sqlite_tables = set(sqlite_inspector.get_table_names())

    print("\nSQLite tables found:")
    for table_name in sorted(sqlite_tables):
        print(f"  - {table_name}")

    # ---------------------------------------------------------
    # 5. Use Base.metadata for PostgreSQL tables
    #    DO NOT reflect PostgreSQL using inspect/PRAGMA
    # ---------------------------------------------------------
    postgres_tables = Base.metadata.tables

    total_copied = 0

    # ---------------------------------------------------------
    # 6. Connect to both databases
    # ---------------------------------------------------------
    with (
        sqlite_engine.connect() as sconn,
        postgres_engine.connect() as pconn
    ):

        for table_name in Base.metadata.tables.keys():

            # SQLite doesn't have this table
            if table_name not in sqlite_tables:
                print(
                    f"  - {table_name}: "
                    "not present in SQLite, skipping"
                )
                continue

            print(f"\nMigrating table: {table_name}")

            # -------------------------------------------------
            # Load SQLite table structure
            # -------------------------------------------------
            sqlite_meta = MetaData()

            sqlite_table = Table(
                table_name,
                sqlite_meta,
                autoload_with=sqlite_engine
            )

            # -------------------------------------------------
            # PostgreSQL table comes from SQLAlchemy metadata
            # -------------------------------------------------
            pg_table = postgres_tables[table_name]

            # -------------------------------------------------
            # Read SQLite rows
            # -------------------------------------------------
            rows = sconn.execute(
                select(sqlite_table)
            ).mappings().all()

            if not rows:
                print(f"  - {table_name}: 0 rows")
                continue

            print(f"  - SQLite rows: {len(rows)}")

            # -------------------------------------------------
            # Find existing PostgreSQL IDs
            # -------------------------------------------------
            pg_columns = set(pg_table.columns.keys())

            existing_ids = set()

            if "id" in pg_columns:

                result = pconn.execute(
                    select(pg_table.c.id)
                )

                existing_ids = {
                    row[0]
                    for row in result
                }

            # -------------------------------------------------
            # Prepare rows
            # -------------------------------------------------
            to_insert = []

            for row in rows:

                row_dict = {
                    key: value
                    for key, value in dict(row).items()
                    if key in pg_columns
                }

                # Skip already migrated IDs
                if (
                    "id" in row_dict
                    and row_dict["id"] in existing_ids
                ):
                    continue

                to_insert.append(row_dict)

            # -------------------------------------------------
            # Nothing new
            # -------------------------------------------------
            if not to_insert:

                print(
                    f"  - {table_name}: "
                    "all rows already migrated"
                )

                continue

            # -------------------------------------------------
            # Insert into PostgreSQL
            # -------------------------------------------------
            pconn.execute(
                pg_table.insert(),
                to_insert
            )

            pconn.commit()

            print(
                f"  - {table_name}: "
                f"copied {len(to_insert)} rows"
            )

            total_copied += len(to_insert)

            # -------------------------------------------------
            # Reset PostgreSQL sequence
            # -------------------------------------------------
            if "id" in pg_columns:

                try:

                    sequence_sql = text(
                        f"""
                        SELECT setval(
                            pg_get_serial_sequence(
                                '{table_name}',
                                'id'
                            ),
                            COALESCE(
                                (SELECT MAX(id) FROM "{table_name}"),
                                1
                            )
                        )
                        """
                    )

                    pconn.execute(sequence_sql)
                    pconn.commit()

                except Exception as sequence_error:

                    print(
                        f"  - Warning: could not reset "
                        f"sequence for {table_name}: "
                        f"{sequence_error}"
                    )

    # ---------------------------------------------------------
    # Done
    # ---------------------------------------------------------
    print("\n========================================")
    print("Migration completed successfully!")
    print(f"Total rows copied: {total_copied}")
    print("SQLite database was not modified.")
    print("========================================")


if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description="Migrate SQLite database to PostgreSQL"
    )

    parser.add_argument(
        "--sqlite-path",
        default=os.path.join(
            os.path.dirname(
                os.path.abspath(__file__)
            ),
            "testpilot.db"
        ),
        help="Path to SQLite database"
    )

    args = parser.parse_args()

    migrate(args.sqlite_path)