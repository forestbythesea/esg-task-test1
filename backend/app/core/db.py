import secrets
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from app.core.config import get_settings


SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT UNIQUE NOT NULL,
  display_name TEXT NOT NULL,
  role TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
  token TEXT PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS companies (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  report_year TEXT NOT NULL,
  file_name TEXT NOT NULL,
  source_url TEXT NOT NULL,
  source_type TEXT NOT NULL DEFAULT 'baseline',
  local_path TEXT,
  document_label TEXT,
  status TEXT NOT NULL DEFAULT 'ready',
  generation_mode TEXT,
  summary_json TEXT,
  questions_json TEXT,
  scores_json TEXT,
  updated_at TEXT
);

CREATE TABLE IF NOT EXISTS chunks (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  company_id TEXT NOT NULL REFERENCES companies(id),
  document_name TEXT NOT NULL,
  page INTEGER NOT NULL,
  text TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS runs (
  id TEXT PRIMARY KEY,
  status TEXT NOT NULL,
  target_report_id TEXT,
  source_type TEXT,
  generation_mode TEXT,
  started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  completed_at TEXT,
  output_path TEXT,
  error TEXT
);

CREATE TABLE IF NOT EXISTS traces (
  id TEXT PRIMARY KEY,
  run_id TEXT,
  user_id INTEGER,
  route TEXT NOT NULL,
  step TEXT NOT NULL,
  model TEXT NOT NULL,
  reasoning_effort TEXT NOT NULL,
  prompt_tokens INTEGER NOT NULL DEFAULT 0,
  completion_tokens INTEGER NOT NULL DEFAULT 0,
  total_tokens INTEGER NOT NULL DEFAULT 0,
  estimated_cost_usd REAL NOT NULL DEFAULT 0,
  latency_ms INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL,
  error TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS chat_messages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL REFERENCES users(id),
  company_id TEXT NOT NULL REFERENCES companies(id),
  role TEXT NOT NULL,
  content TEXT NOT NULL,
  citations_json TEXT,
  trace_id TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


SEED_USERS = [
    ("analyst", "Demo Analyst", "analyst"),
    ("reviewer", "Risk Reviewer", "reviewer"),
    ("admin", "Admin User", "admin"),
]


def connect(path: Path | None = None) -> sqlite3.Connection:
    db_path = path or get_settings().sqlite_path
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def get_conn() -> Iterator[sqlite3.Connection]:
    conn = connect()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(SCHEMA)
        migrate_db(conn)
        conn.executemany(
            "INSERT OR IGNORE INTO users (username, display_name, role) VALUES (?, ?, ?)",
            SEED_USERS,
        )


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def migrate_db(conn: sqlite3.Connection) -> None:
    company_columns = _columns(conn, "companies")
    company_additions = {
        "source_type": "ALTER TABLE companies ADD COLUMN source_type TEXT NOT NULL DEFAULT 'baseline'",
        "local_path": "ALTER TABLE companies ADD COLUMN local_path TEXT",
        "document_label": "ALTER TABLE companies ADD COLUMN document_label TEXT",
        "status": "ALTER TABLE companies ADD COLUMN status TEXT NOT NULL DEFAULT 'ready'",
        "generation_mode": "ALTER TABLE companies ADD COLUMN generation_mode TEXT",
    }
    for column, statement in company_additions.items():
        if column not in company_columns:
            conn.execute(statement)

    run_columns = _columns(conn, "runs")
    run_additions = {
        "target_report_id": "ALTER TABLE runs ADD COLUMN target_report_id TEXT",
        "source_type": "ALTER TABLE runs ADD COLUMN source_type TEXT",
        "generation_mode": "ALTER TABLE runs ADD COLUMN generation_mode TEXT",
    }
    for column, statement in run_additions.items():
        if column not in run_columns:
            conn.execute(statement)


def create_session(username: str) -> dict | None:
    with get_conn() as conn:
        user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        if not user:
            return None
        token = secrets.token_urlsafe(32)
        conn.execute("INSERT INTO sessions (token, user_id) VALUES (?, ?)", (token, user["id"]))
        return {
            "token": token,
            "user": {
                "id": user["id"],
                "username": user["username"],
                "display_name": user["display_name"],
                "role": user["role"],
            },
        }


def get_user_for_token(token: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT u.* FROM sessions s
            JOIN users u ON u.id = s.user_id
            WHERE s.token = ?
            """,
            (token,),
        ).fetchone()
        return dict(row) if row else None
