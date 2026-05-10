# app/api/routes.py

import os
from pathlib import Path
from datetime import datetime

from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse, FileResponse

from app.core.database import create_file_record, get_file, get_db, update_status
from app.services.storage import save_upload, get_processed_path
from app.workers.tasks import process_file_task

router = APIRouter()

# ─── Constants ─────────────────────────────────────────────────────────────────

ALLOWED_EXTENSIONS = {
    ".csv":  "csv",
    ".jpg":  "image",
    ".jpeg": "image",
    ".png":  "image",
    ".webp": "image",
    ".pdf":  "pdf",
}

MAX_FILE_SIZE_MB = 50
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024


# ─── Upload ────────────────────────────────────────────────────────────────────

@router.post("/upload", status_code=201)
async def upload_file(file: UploadFile = File(...)):
    """
    What changed from Phase 3 → Phase 4:

    BEFORE (BackgroundTasks):
      background_tasks.add_task(run_processing, ...)
      → Ran inside the same Uvicorn process
      → Lost if server restarted mid-job
      → No retry on failure

    AFTER (Celery):
      process_file_task.delay(...)
      → Pushes a JSON message into Redis
      → A separate worker process picks it up
      → Survives server restarts (Redis persists the job)
      → Retries automatically on failure (configured in tasks.py)

    .delay() returns immediately — the client still gets their
    response in milliseconds. Nothing else changes from their perspective.
    """

    # --- Validate: file type ---
    suffix = Path(file.filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"File type '{suffix}' is not supported. "
                f"Accepted: {', '.join(ALLOWED_EXTENSIONS.keys())}"
            ),
        )
    file_type = ALLOWED_EXTENSIONS[suffix]

    # --- Validate: file size ---
    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum allowed size is {MAX_FILE_SIZE_MB}MB.",
        )
    await file.seek(0)  # rewind pointer before saving

    # --- Create DB record ---
    file_id = create_file_record(
        original_name=file.filename,
        upload_path="__pending__",
        file_type=file_type,
    )

    # --- Save file to disk ---
    upload_path = save_upload(file, file_id)

    # --- Update DB with real path ---
    conn = get_db()
    conn.execute(
        "UPDATE files SET upload_path = ? WHERE id = ?",
        (upload_path, file_id),
    )
    conn.commit()
    conn.close()

    # --- Push job to Redis queue via Celery ---
    output_path = get_processed_path(file_id, file_type)
    process_file_task.delay(
        file_id=file_id,
        file_type=file_type,
        upload_path=upload_path,
        output_path=output_path,
    )

    # --- Respond immediately ---
    record = get_file(file_id)
    return JSONResponse(
        status_code=201,
        content={
            "file_id": file_id,
            "original_name": file.filename,
            "file_type": file_type,
            "status": "queued",
            "download_url": f"/api/v1/download/{file_id}",
            "expires_at": record["expires_at"],
            "message": "File received. Processing will begin shortly.",
        },
    )


# ─── Status ────────────────────────────────────────────────────────────────────

@router.get("/status/{file_id}")
def get_status(file_id: str):
    record = get_file(file_id)
    if not record:
        raise HTTPException(status_code=404, detail="File not found.")

    expires_at = datetime.fromisoformat(record["expires_at"])
    if datetime.utcnow() > expires_at:
        raise HTTPException(
            status_code=410,
            detail="This file has expired and been deleted.",
        )

    return {
        "file_id": file_id,
        "original_name": record["original_name"],
        "file_type": record["file_type"],
        "status": record["status"],
        "created_at": record["created_at"],
        "expires_at": record["expires_at"],
    }


# ─── Download ──────────────────────────────────────────────────────────────────

@router.get("/download/{file_id}")
def download_file(file_id: str):
    record = get_file(file_id)
    if not record:
        raise HTTPException(status_code=404, detail="File not found.")

    expires_at = datetime.fromisoformat(record["expires_at"])
    if datetime.utcnow() > expires_at:
        raise HTTPException(
            status_code=410,
            detail="This file has expired and been automatically deleted.",
        )

    if record["status"] in ("pending", "processing"):
        return JSONResponse(
            status_code=202,
            content={
                "message": f"File is {record['status']}. Try again in a few seconds.",
                "status": record["status"],
            },
        )

    if record["status"] == "failed":
        raise HTTPException(
            status_code=500,
            detail="Processing failed for this file. Please re-upload.",
        )

    processed_path = record["processed_path"]
    if not processed_path or not os.path.exists(processed_path):
        raise HTTPException(
            status_code=404,
            detail="Processed file not found on disk.",
        )

    original_stem = Path(record["original_name"]).stem
    output_ext = Path(processed_path).suffix
    download_name = f"{original_stem}_processed{output_ext}"

    return FileResponse(
        path=processed_path,
        filename=download_name,
        media_type="application/octet-stream",
    )


# ─── Health ────────────────────────────────────────────────────────────────────

@router.get("/health")
def health_check():
    return {"status": "ok", "service": "FileProcessorAPI"}
