import sqlite3
import uuid
from datetime import datetime, timedelta
from app.core.config import settings

def get_db():
    conn = sqlite3.connect(settings.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
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

def create_file_record(original_name, upload_path, file_type):
    file_id = str(uuid.uuid4())
    now = datetime.utcnow()
    expires_at = now + timedelta(hours=settings.FILE_EXPIRY_HOURS)
    conn = get_db()
    conn.execute(
        "INSERT INTO files (id,original_name,upload_path,file_type,created_at,expires_at) VALUES (?,?,?,?,?,?)",
        (file_id, original_name, upload_path, file_type, now.isoformat(), expires_at.isoformat())
    )
    conn.commit()
    conn.close()
    return file_id

def get_file(file_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM files WHERE id=?", (file_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def get_all_files():
    conn = get_db()
    rows = conn.execute("SELECT * FROM files ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def update_status(file_id, status, processed_path=None):
    conn = get_db()
    conn.execute("UPDATE files SET status=?, processed_path=? WHERE id=?",
                 (status, processed_path, file_id))
    conn.commit()
    conn.close()

def get_expired_files():
    conn = get_db()
    now = datetime.utcnow().isoformat()
    rows = conn.execute("SELECT * FROM files WHERE expires_at<?", (now,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def delete_file_record(file_id):
    conn = get_db()
    conn.execute("DELETE FROM files WHERE id=?", (file_id,))
    conn.commit()
    conn.close()
