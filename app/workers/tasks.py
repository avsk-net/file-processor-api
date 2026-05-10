from app.workers.celery_app import celery_app
from app.services.processor import process_file
from app.services.storage import delete_file_safe
from app.core.database import update_status, get_expired_files, delete_file_record

@celery_app.task(bind=True, max_retries=3, default_retry_delay=10)
def process_file_task(self, file_id, file_type, upload_path, output_path):
    try:
        print(f"[Worker] Processing {file_id} ({file_type})")
        update_status(file_id, "processing")
        process_file(file_id, file_type, upload_path, output_path)
        update_status(file_id, "done", processed_path=output_path)
        print(f"[Worker] ✓ Done: {file_id}")
        return {"status": "done", "file_id": file_id}
    except Exception as exc:
        print(f"[Worker] ✗ Failed: {file_id} — {exc}")
        update_status(file_id, "failed")
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)

@celery_app.task
def cleanup_expired_files():
    expired = get_expired_files()
    if not expired:
        print("[Cleanup] No expired files.")
        return
    print(f"[Cleanup] Deleting {len(expired)} expired file(s)")
    for record in expired:
        fid = record["id"]
        try:
            delete_file_safe(record.get("upload_path"))
            delete_file_safe(record.get("processed_path"))
            delete_file_record(fid)
            print(f"[Cleanup] ✓ Deleted {fid}")
        except Exception as e:
            print(f"[Cleanup] ✗ Failed on {fid}: {e}")
