from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

import os

# SPRINTLINE_DB_PATH redirects the database — used by the test suite so runs
# don't write demo rows into the dev database. Unset in normal operation.
_env_db = os.environ.get("SPRINTLINE_DB_PATH", "").strip()
DB_PATH = (
    Path(_env_db).expanduser()
    if _env_db
    else Path(__file__).resolve().parent.parent / "data" / "app.db"
)
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Additive columns introduced after the first release. `create_all` only
# creates missing *tables*, so an existing app.db needs these patched in by
# hand. Kept as plain DDL rather than pulling in Alembic for a demo-scale app.
#
# (table, column, DDL type, optional unique index name)
_ADDITIVE_COLUMNS: tuple[tuple[str, str, str, str | None], ...] = (
    ("projects", "source_path", "VARCHAR(1000)", "ix_projects_source_path"),
)


def run_migrations() -> None:
    """Add post-release columns to an existing SQLite database.

    Idempotent: skips anything already present, and skips tables that do not
    exist yet (a fresh database gets them from ``create_all``).
    """
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())

    for table, column, ddl_type, index_name in _ADDITIVE_COLUMNS:
        if table not in table_names:
            continue  # fresh DB — create_all already built it correctly
        existing = {c["name"] for c in inspector.get_columns(table)}
        with engine.begin() as conn:
            if column not in existing:
                conn.execute(
                    text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl_type}")
                )
            if index_name:
                # SQLite cannot add a UNIQUE constraint via ALTER TABLE, so the
                # uniqueness lives in an index. NULLs stay non-conflicting,
                # which is what non-imported projects rely on.
                conn.execute(
                    text(
                        f"CREATE UNIQUE INDEX IF NOT EXISTS {index_name} "
                        f"ON {table} ({column})"
                    )
                )
