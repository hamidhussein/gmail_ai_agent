"""
GmailAI Assistant - Versioned Database Migration Runner

Lightweight migration system for SQLite that replaces raw create_all()
with numbered, idempotent migration functions. Each migration runs once
and its completion is tracked in a ``schema_version`` table.

Strategy:
  - Brand-new databases: create_all() + stamp at latest version.
  - Existing databases missing ``schema_version``: detect as version 0,
    run all migrations sequentially.
  - Already-migrated databases: run only pending migrations.
"""
import logging
import datetime
from typing import List, Callable, Tuple

from sqlalchemy import text, inspect
from sqlalchemy.engine import Engine

from database.models import Base

logger = logging.getLogger("GmailAI.Migrations")

# Current schema version — bump this when adding a new migration.
LATEST_VERSION = 1

# ---------------------------------------------------------------------------
# Migration registry
# ---------------------------------------------------------------------------
# Each entry is (version_number, description, callable).
# The callable receives the SQLAlchemy Engine and must be idempotent.

MigrationFn = Callable[[Engine], None]
_MIGRATIONS: List[Tuple[int, str, MigrationFn]] = []


def _register(version: int, description: str):
    """Decorator to register a migration function."""
    def decorator(fn: MigrationFn) -> MigrationFn:
        _MIGRATIONS.append((version, description, fn))
        return fn
    return decorator


# ---------------------------------------------------------------------------
# Version tracking helpers
# ---------------------------------------------------------------------------

def _ensure_version_table(engine: Engine) -> None:
    """Creates the schema_version table if it does not exist."""
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS schema_version (
                version   INTEGER NOT NULL,
                applied_at TEXT NOT NULL
            )
        """))
        conn.commit()


def _get_current_version(engine: Engine) -> int:
    """Returns the highest applied migration version, or 0 if none."""
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT MAX(version) FROM schema_version")
            ).fetchone()
            if row and row[0] is not None:
                return int(row[0])
    except Exception:
        pass
    return 0


def _stamp_version(engine: Engine, version: int) -> None:
    """Records a migration version as applied."""
    now = datetime.datetime.utcnow().isoformat()
    with engine.connect() as conn:
        conn.execute(
            text("INSERT INTO schema_version (version, applied_at) VALUES (:v, :ts)"),
            {"v": version, "ts": now},
        )
        conn.commit()


def _is_fresh_database(engine: Engine) -> bool:
    """Returns True if the database has no application tables at all."""
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    # If at least one core application table exists, it is not fresh
    return "accounts" not in tables and "emails" not in tables


def _table_has_column(engine: Engine, table: str, column: str) -> bool:
    """Checks whether a column exists in a table (for idempotent ALTER)."""
    inspector = inspect(engine)
    if table not in inspector.get_table_names():
        return False
    columns = {c["name"] for c in inspector.get_columns(table)}
    return column in columns


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_migrations(engine: Engine) -> int:
    """
    Runs all pending migrations against the given engine.

    For a brand-new database, creates all tables via SQLAlchemy metadata
    and stamps at the latest version.  For existing databases, applies
    each migration sequentially.

    Returns:
        The schema version after migrations.
    """
    fresh = _is_fresh_database(engine)

    if fresh:
        # Brand-new database: create everything from models, stamp latest.
        Base.metadata.create_all(engine)
        _ensure_version_table(engine)
        _stamp_version(engine, LATEST_VERSION)
        logger.info(f"Fresh database — created schema at version {LATEST_VERSION}.")
        return LATEST_VERSION

    # Existing database — ensure version tracking exists.
    _ensure_version_table(engine)
    current = _get_current_version(engine)

    if current >= LATEST_VERSION:
        logger.debug(f"Database schema is up to date (version {current}).")
        return current

    # Sort migrations by version number, run pending ones.
    sorted_migrations = sorted(_MIGRATIONS, key=lambda m: m[0])
    applied = 0
    for version, description, fn in sorted_migrations:
        if version > current:
            logger.info(f"Applying migration {version}: {description}")
            try:
                fn(engine)
                _stamp_version(engine, version)
                applied += 1
            except Exception as e:
                logger.error(f"Migration {version} failed: {e}", exc_info=True)
                raise RuntimeError(
                    f"Database migration {version} ({description}) failed: {e}"
                ) from e

    final = _get_current_version(engine)
    if applied:
        logger.info(f"Applied {applied} migration(s). Schema now at version {final}.")
    return final


# ---------------------------------------------------------------------------
# Migration definitions
# ---------------------------------------------------------------------------

@_register(1, "Baseline — stamp existing v1.0.0 schema")
def _migration_001_baseline(engine: Engine) -> None:
    """
    First migration for existing databases that were created by create_all().
    Ensures all expected tables, columns, and indexes exist. Adds anything missing.
    This is idempotent — safe to run against a database that already has
    the full schema.
    """
    # 1. Ensure any entirely missing core tables are created
    Base.metadata.create_all(engine)

    # 2. Sync all missing columns from SQLAlchemy models to existing tables
    _sync_missing_columns_from_metadata(engine)

    # 3. Ensure indexes (CREATE INDEX IF NOT EXISTS is SQLite-safe)
    _create_index_if_missing(engine, "idx_email_account_received", "emails", "account_id, received_at")
    _create_index_if_missing(engine, "idx_email_category_importance", "emails", "category, importance_score")


def _sync_missing_columns_from_metadata(engine: Engine) -> None:
    """Ensures all columns defined in SQLAlchemy models exist in the database."""
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    with engine.connect() as conn:
        for table_name, table_obj in Base.metadata.tables.items():
            if table_name not in existing_tables:
                continue
            existing_cols = {c["name"] for c in inspector.get_columns(table_name)}
            for col in table_obj.columns:
                if col.name not in existing_cols:
                    col_type = col.type.compile(engine.dialect)
                    default_clause = ""
                    if col.server_default is not None:
                        default_clause = f" DEFAULT {col.server_default.arg}"
                    elif col.default is not None and getattr(col.default, "is_scalar", False):
                        val = col.default.arg
                        if isinstance(val, (int, float)):
                            default_clause = f" DEFAULT {val}"
                        elif isinstance(val, bool):
                            default_clause = f" DEFAULT {1 if val else 0}"
                        elif isinstance(val, str):
                            default_clause = f" DEFAULT '{val}'"
                    sql = f"ALTER TABLE {table_name} ADD COLUMN {col.name} {col_type}{default_clause}"
                    conn.execute(text(sql))
                    logger.info(f"  Added column {table_name}.{col.name} ({col_type})")
        conn.commit()


# ---------------------------------------------------------------------------
# Migration helper utilities
# ---------------------------------------------------------------------------

def _add_column_if_missing(engine: Engine, table: str, column: str, col_def: str) -> None:
    if not _table_has_column(engine, table, column):
        with engine.connect() as conn:
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {col_def}"))
            conn.commit()
        logger.info(f"  Added column {table}.{column}")


def _create_table_if_missing(engine: Engine, table: str, create_sql: str) -> None:
    inspector = inspect(engine)
    if table not in inspector.get_table_names():
        with engine.connect() as conn:
            conn.execute(text(create_sql))
            conn.commit()
        logger.info(f"  Created table {table}")


def _create_index_if_missing(engine: Engine, index_name: str, table: str, columns: str) -> None:
    with engine.connect() as conn:
        conn.execute(text(f"CREATE INDEX IF NOT EXISTS {index_name} ON {table} ({columns})"))
        conn.commit()
