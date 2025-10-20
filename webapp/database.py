# webapp/database.py
import json
import sqlite3
from pathlib import Path

# Load configuration from config.json
with open("config.json", "r", encoding="utf-8") as f:
    config = json.load(f)

DB_PATH = Path(config.get("db_path", "data/jobs.db"))
TABLE_NAME = config.get("jobs_tablename", "jobs")  # read from the same table the legacy app used

NEEDED_COLUMNS = {
    "applied": "INTEGER DEFAULT 0",
    "rejected": "INTEGER DEFAULT 0",
    "interview": "INTEGER DEFAULT 0",
    "hidden": "INTEGER DEFAULT 0",
    "cover_letter": "TEXT"
}

def _connect():
    """Create a SQLite connection."""
    # Ensure parent folder exists
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(DB_PATH)

def _ensure_columns():
    """Add any missing columns (applied/rejected/interview/hidden/cover_letter)."""
    with _connect() as conn:
        cur = conn.cursor()
        # check if table exists; if not, nothing to migrate here (scraper creates it)
        cur.execute(
            "SELECT count(name) FROM sqlite_master WHERE type='table' AND name=?",
            (TABLE_NAME,)
        )
        if cur.fetchone()[0] != 1:
            return

        cur.execute(f"PRAGMA table_info({TABLE_NAME})")
        existing_cols = {row[1] for row in cur.fetchall()}
        for col, coltype in NEEDED_COLUMNS.items():
            if col not in existing_cols:
                cur.execute(f'ALTER TABLE {TABLE_NAME} ADD COLUMN "{col}" {coltype}')
        conn.commit()

# Run lightweight migration on import
_ensure_columns()

def get_jobs():
    """Retrieve all non-hidden jobs from the database."""
    query = f"""
        SELECT id, title, company, location, date, job_url, job_description,
               IFNULL(applied, 0)   AS applied,
               IFNULL(rejected, 0)  AS rejected,
               IFNULL(interview, 0) AS interview,
               IFNULL(hidden, 0)    AS hidden,
               cover_letter
        FROM {TABLE_NAME}
        WHERE IFNULL(hidden, 0) = 0
        ORDER BY id DESC
    """
    with _connect() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(query).fetchall()
        return [dict(r) for r in rows]

def get_job(job_id: int):
    """Retrieve a single job record by ID."""
    query = f"""
        SELECT id, title, company, location, date, job_url, job_description,
               IFNULL(applied, 0)   AS applied,
               IFNULL(rejected, 0)  AS rejected,
               IFNULL(interview, 0) AS interview,
               IFNULL(hidden, 0)    AS hidden,
               cover_letter
        FROM {TABLE_NAME}
        WHERE id = ?
    """
    with _connect() as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(query, (job_id,)).fetchone()
        return dict(row) if row else {}

def update_flag(job_id: int, **flags):
    """
    Update job status flags like applied, rejected, interview, or hidden.
    Example: update_flag(5, applied=1)
    """
    if not flags:
        return 0
    columns = ", ".join([f'"{key}" = ?' for key in flags])
    values = list(flags.values()) + [job_id]
    with _connect() as conn:
        cur = conn.execute(f'UPDATE "{TABLE_NAME}" SET {columns} WHERE id = ?', values)
        conn.commit()
        return cur.rowcount
