import os
from pathlib import Path
from datetime import datetime

from fastapi import APIRouter, UploadFile, File, HTTPException, Request
from fastapi.responses import JSONResponse, FileResponse

from app.core.database import (
    create_file_record, get_file, get_all_files,
    get_db, update_status, delete_file_record
)
from app.services.storage import save_upload, get_processed_path, delete_file_safe
from app.workers.tasks import process_file_task

router = APIRouter()

ALLOWED_EXTENSIONS = {
    ".csv": "csv", ".jpg": "image", ".jpeg": "image",
    ".png": "image", ".webp": "image", ".pdf": "pdf",
}
MAX_FILE_SIZE_MB    = 50
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024


@router.post("/upload", status_code=201)
async def upload_file(request: Request, file: UploadFile = File(...)):
    suffix = Path(file.filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400,
            detail=f"'{suffix}' not supported. Accepted: {', '.join(ALLOWED_EXTENSIONS)}")
    file_type = ALLOWED_EXTENSIONS[suffix]

    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(status_code=413, detail=f"Max {MAX_FILE_SIZE_MB}MB allowed.")
    await file.seek(0)

    file_id     = create_file_record(file.filename, "__pending__", file_type)
    upload_path = save_upload(file, file_id)

    conn = get_db()
    conn.execute("UPDATE files SET upload_path=? WHERE id=?", (upload_path, file_id))
    conn.commit()
    conn.close()

    output_path = get_processed_path(file_id, file_type)
    process_file_task.delay(file_id=file_id, file_type=file_type,
                            upload_path=upload_path, output_path=output_path)

    record = get_file(file_id)
    return JSONResponse(status_code=201, content={
        "file_id": file_id, "original_name": file.filename,
        "file_type": file_type, "status": "queued",
        "download_url": f"/api/v1/download/{file_id}",
        "expires_at": record["expires_at"],
        "message": "File received. Processing will begin shortly.",
    })


@router.get("/files")
def list_files():
    records = get_all_files()
    now = datetime.utcnow()
    result = []
    for r in records:
        expires_at   = datetime.fromisoformat(r["expires_at"])
        seconds_left = max(0, int((expires_at - now).total_seconds()))
        result.append({
            "file_id": r["id"], "original_name": r["original_name"],
            "file_type": r["file_type"], "status": r["status"],
            "created_at": r["created_at"], "expires_at": r["expires_at"],
            "seconds_left": seconds_left, "expired": seconds_left == 0,
        })
    return result


@router.get("/status/{file_id}")
def get_status(file_id: str):
    record = get_file(file_id)
    if not record:
        raise HTTPException(status_code=404, detail="File not found.")
    expires_at = datetime.fromisoformat(record["expires_at"])
    if datetime.utcnow() > expires_at:
        raise HTTPException(status_code=410, detail="File has expired.")
    return {"file_id": file_id, "original_name": record["original_name"],
            "file_type": record["file_type"], "status": record["status"],
            "created_at": record["created_at"], "expires_at": record["expires_at"]}


@router.get("/download/{file_id}")
def download_file(file_id: str):
    record = get_file(file_id)
    if not record:
        raise HTTPException(status_code=404, detail="File not found.")
    expires_at = datetime.fromisoformat(record["expires_at"])
    if datetime.utcnow() > expires_at:
        raise HTTPException(status_code=410, detail="File has expired.")
    if record["status"] in ("pending", "processing"):
        return JSONResponse(status_code=202,
            content={"message": f"File is {record['status']}. Try again shortly.",
                     "status": record["status"]})
    if record["status"] == "failed":
        raise HTTPException(status_code=500, detail="Processing failed. Please re-upload.")
    processed_path = record["processed_path"]
    if not processed_path or not os.path.exists(processed_path):
        raise HTTPException(status_code=404, detail="Processed file not found on disk.")
    stem = Path(record["original_name"]).stem
    ext  = Path(processed_path).suffix
    return FileResponse(path=processed_path, filename=f"{stem}_processed{ext}",
                        media_type="application/octet-stream")


@router.delete("/files/{file_id}")
def delete_file(file_id: str):
    record = get_file(file_id)
    if not record:
        raise HTTPException(status_code=404, detail="File not found.")
    delete_file_safe(record.get("upload_path"))
    delete_file_safe(record.get("processed_path"))
    delete_file_record(file_id)
    return {"message": f"File {file_id} deleted."}


@router.get("/health")
def health_check():
    return {"status": "ok", "service": "FileProcessorAPI"}
