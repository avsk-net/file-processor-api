# app/core/database.py
import sqlite3
import uuid
from datetime import datetime, timedelta
from app.core.config import settings


def get_db():
    """
    Opens a connection to the SQLite database file.
    row_factory=sqlite3.Row makes rows behave like dictionaries —
    you can do row["status"] instead of row[4].
    
    We open/close per operation (not a persistent connection pool)
    because SQLite handles this fine for our scale.
    """
    conn = sqlite3.connect(settings.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """
    Creates the table if it doesn't exist.
    
    'IF NOT EXISTS' makes this idempotent — safe to call every time
    the server starts without wiping data.
    """
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS files (
            id             TEXT PRIMARY KEY,
            original_name  TEXT NOT NULL,
            upload_path    TEXT NOT NULL,
            processed_path TEXT,
            file_type      TEXT NOT NULL,
            status         TEXT NOT NULL DEFAULT 'pending',
            created_at     TEXT NOT NULL,
            expires_at     TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def create_file_record(original_name: str, upload_path: str, file_type: str) -> str:
    """
    Inserts a new row when a file is uploaded.
    Returns the UUID — this is what the client gets back and uses
    to check status and download their result.
    
    Why uuid4()? It's random and unguessable. Sequential IDs (1, 2, 3...)
    would let anyone enumerate other users' files.
    """
    file_id = str(uuid.uuid4())
    now = datetime.utcnow()
    expires_at = now + timedelta(hours=settings.FILE_EXPIRY_HOURS)

    conn = get_db()
    conn.execute(
        """
        INSERT INTO files
            (id, original_name, upload_path, file_type, created_at, expires_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (file_id, original_name, upload_path, file_type,
         now.isoformat(), expires_at.isoformat())
    )
    conn.commit()
    conn.close()
    return file_id


def get_file(file_id: str) -> dict | None:
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM files WHERE id = ?", (file_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def update_status(file_id: str, status: str, processed_path: str = None):
    conn = get_db()
    conn.execute(
        """
        UPDATE files
        SET status = ?, processed_path = ?
        WHERE id = ?
        """,
        (status, processed_path, file_id)
    )
    conn.commit()
    conn.close()


def get_expired_files() -> list[dict]:
    """
    Returns files whose expiry timestamp has passed.
    The scheduler calls this every hour.
    
    datetime.utcnow().isoformat() produces something like
    '2025-05-07T10:30:00' — SQLite's TEXT comparison works correctly
    on ISO format strings because they sort lexicographically.
    """
    conn = get_db()
    now = datetime.utcnow().isoformat()
    rows = conn.execute(
        "SELECT * FROM files WHERE expires_at < ?", (now,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_file_record(file_id: str):
    conn = get_db()
    conn.execute("DELETE FROM files WHERE id = ?", (file_id,))
    conn.commit()
    conn.close()
