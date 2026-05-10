# app/workers/tasks.py
from app.workers.celery_app import celery_app
from app.services.processor import process_file
from app.core.database import update_status

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
