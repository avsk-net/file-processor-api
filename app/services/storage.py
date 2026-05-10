# app/services/storage.py
import os
import shutil
from pathlib import Path
from fastapi import UploadFile, HTTPException
from app.core.config import settings


def ensure_dirs():
    """
    Create storage directories if they don't exist.
    exist_ok=True means no error if the dir already exists.
    """
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    os.makedirs(settings.PROCESSED_DIR, exist_ok=True)


def save_upload(file: UploadFile, file_id: str) -> str:
    """
    Saves the uploaded file to disk.
    Returns the full path where it was saved.
    
    Why use file_id in the filename instead of the original name?
    - Original names can contain spaces, special chars, path traversal attacks
    - Two users might upload 'report.csv' — they'd overwrite each other
    - UUIDs are unique and safe
    
    We preserve the extension so processors know the file type.
    """
    suffix = Path(file.filename).suffix.lower()
    upload_path = os.path.join(settings.UPLOAD_DIR, f"{file_id}{suffix}")

    # shutil.copyfileobj copies in chunks — it won't load a 50MB
    # file into memory all at once, which would crash under load.
    with open(upload_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    return upload_path


def delete_file_safe(path: str | None):
    """
    Deletes a file if it exists. 
    'Safe' means no crash if the path is None or file already gone.
    The scheduler calls this during cleanup.
    """
    if path and os.path.exists(path):
        os.remove(path)


def get_processed_path(file_id: str, file_type: str) -> str:
    """
    Returns the expected output path for a processed file.
    Used by processors to know where to write their output.
    """
    ext_map = {
        "csv":   "_report.json",
        "image": "_resized.jpg",
        "pdf":   "_extracted.json",
    }
    suffix = ext_map.get(file_type, "_output.bin")
    return os.path.join(settings.PROCESSED_DIR, f"{file_id}{suffix}")
