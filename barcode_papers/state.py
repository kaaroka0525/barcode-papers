"""발송 이력(SQLite) — 같은 논문을 두 번 보내지 않기 위한 중복 관리."""
import datetime as dt
import sqlite3
from pathlib import Path

from .config import DB_PATH


def _connect(db_path: Path = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS sent (
            key TEXT PRIMARY KEY,
            doi TEXT,
            title TEXT,
            journal TEXT,
            impact_factor REAL,
            sent_at TEXT
        )
        """
    )
    return conn


def filter_unseen(papers, db_path: Path = DB_PATH):
    """아직 보내지 않은 논문만 반환."""
    conn = _connect(db_path)
    try:
        seen = {row[0] for row in conn.execute("SELECT key FROM sent")}
    finally:
        conn.close()
    return [p for p in papers if p.key not in seen]


def mark_sent(papers, db_path: Path = DB_PATH) -> None:
    conn = _connect(db_path)
    now = dt.datetime.now().isoformat(timespec="seconds")
    try:
        conn.executemany(
            "INSERT OR REPLACE INTO sent (key, doi, title, journal, impact_factor, sent_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            [
                (p.key, p.doi, p.title, p.journal, p.impact_factor, now)
                for p in papers
            ],
        )
        conn.commit()
    finally:
        conn.close()
