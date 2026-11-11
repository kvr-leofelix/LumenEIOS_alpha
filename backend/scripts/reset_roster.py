"""Back up the database, delete every row, and reseed the IIT Mandi roster.

Run from apps/lumeneios (the folder holding .env and lumeneios.db):

    python -m backend.scripts.reset_roster          # asks for confirmation
    python -m backend.scripts.reset_roster --yes    # no prompt

SQLite: the file is copied to lumeneios.db.backup-<timestamp> first. Other databases
are not backed up, so take your own backup before running against PostgreSQL.
Uploaded files in storage_uploads/ are left in place.
"""
import argparse
import asyncio
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import make_url

from backend.app.main import app  # noqa: F401  (imports every model so all tables are known)
from backend.app.core.config import settings
from backend.app.db.session import AsyncSessionLocal, Base, engine, init_db
from backend.app.seed.seed_data import seed_database_if_empty


def backup_sqlite(url: str) -> Path | None:
    parsed = make_url(url)
    if not parsed.drivername.startswith("sqlite") or not parsed.database:
        return None
    source = Path(parsed.database).resolve()
    if not source.exists():
        return None
    target = source.with_name(f"{source.name}.backup-{datetime.now():%Y%m%d-%H%M%S}")
    # sqlite3's backup API copies a consistent snapshot even while the server has it open.
    with sqlite3.connect(source) as src, sqlite3.connect(target) as dst:
        src.backup(dst)
    return target


async def reset() -> None:
    await init_db()
    async with engine.begin() as conn:
        if engine.dialect.name == "sqlite":
            await conn.execute(text("PRAGMA foreign_keys=OFF"))
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(table.delete())
    async with AsyncSessionLocal() as session:
        await seed_database_if_empty(session)
    await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--yes", action="store_true", help="skip the confirmation prompt")
    args = parser.parse_args()

    print(f"Database: {settings.DATABASE_URL}")
    if not args.yes and input("Delete ALL data and reseed the roster? Type 'reset': ").strip() != "reset":
        sys.exit("Cancelled.")
    backup = backup_sqlite(settings.DATABASE_URL)
    print(f"Backup: {backup}" if backup else "Backup: none (not a SQLite file)")
    asyncio.run(reset())
    print("Done. Every account's password is demo123.")


if __name__ == "__main__":
    main()
