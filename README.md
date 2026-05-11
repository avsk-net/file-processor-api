# File Processor API

Upload a CSV, image, or PDF — get back a processed result. Files expire automatically after 24 hours.

**Dashboard** at `/` · **API docs** at `/docs`

---

## What it does

| Input | Output |
|---|---|
| `.csv` | JSON report — row count, column stats, null counts, 5-row preview |
| `.jpg .jpeg .png .webp` | Resized JPEG, max 800×800, quality 85 |
| `.pdf` | JSON text extraction per page |

---

## Stack

- **FastAPI** — REST API + web dashboard
- **Celery + Redis** — background processing queue
- **Celery Beat** — hourly cleanup of expired files
- **SQLite** — file metadata and expiry tracking
- **Nginx** — reverse proxy
- **systemd** — process management on VPS

---

## One-click deployment (VPS)

```bash
git clone https://github.com/avsk-net/file-processor-api.git
cd file-processor-api
sudo bash deploy.sh
```

The script will ask for your domain (optional) and whether to enable HTTPS, then handle everything: packages, Redis, Python env, systemd services, Nginx, and Let's Encrypt.

**Update after a code push:**
```bash
sudo bash update.sh
```

---

## Local development

**Requirements:** Python 3.10+, Redis

```bash
git clone https://github.com/avsk-net/file-processor-api.git
cd file-processor-api

python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

**`.env` (local defaults):**
```
APP_NAME=FileProcessorAPI
UPLOAD_DIR=storage/uploads
PROCESSED_DIR=storage/processed
MAX_FILE_SIZE_MB=50
FILE_EXPIRY_HOURS=24
REDIS_URL=redis://localhost:6379/0
DATABASE_PATH=files.db
```

Run 3 terminals:

```bash
# Terminal 1 — API server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2 — Celery worker
celery -A app.workers.celery_app worker --loglevel=info --concurrency=2

# Terminal 3 — Celery Beat scheduler
celery -A app.workers.celery_app beat --loglevel=info
```

Open `http://localhost:8000`

---

## Run tests

```bash
pip install pytest httpx
pytest tests/ -v
```

---

## API reference

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/upload` | Upload a file |
| `GET` | `/api/v1/files` | List all files with status |
| `GET` | `/api/v1/status/{id}` | Check processing status |
| `GET` | `/api/v1/download/{id}` | Download processed result |
| `DELETE` | `/api/v1/files/{id}` | Delete a file manually |
| `GET` | `/api/v1/health` | Health check |

**Limits:** 50MB max · CSV, JPG, PNG, WEBP, PDF only · 10 uploads/min per IP · 24h expiry

```bash
# Upload
curl -X POST http://localhost:8000/api/v1/upload -F "file=@data.csv"

# Poll status
curl http://localhost:8000/api/v1/status/<file_id>

# Download result
curl -OJ http://localhost:8000/api/v1/download/<file_id>
```

---

## Project structure

```
file-processor-api/
├── app/
│   ├── main.py               # App entry point, static files, rate limiting
│   ├── api/routes.py         # All HTTP endpoints
│   ├── core/
│   │   ├── config.py         # Settings loaded from .env
│   │   └── database.py       # SQLite queries
│   ├── services/
│   │   ├── processor.py      # CSV / image / PDF logic
│   │   └── storage.py        # File save / delete / path helpers
│   ├── static/index.html     # Web dashboard UI
│   └── workers/
│       ├── celery_app.py     # Celery instance + Beat schedule
│       └── tasks.py          # Background job definitions
├── tests/
│   └── test_api.py           # Automated test suite
├── nginx/
│   └── file_processor.conf   # Nginx config (used by deploy.sh)
├── systemd/                  # systemd service files (used by deploy.sh)
├── storage/
│   ├── uploads/              # Raw uploaded files
│   └── processed/            # Processed output files
├── deploy.sh                 # One-click VPS deployment
├── update.sh                 # One-click update after git push
├── .env.example
└── requirements.txt
```

---

## Checkpoint

| Component | Status |
|---|---|
| Upload endpoint | ✅ |
| File listing + status + download + delete | ✅ |
| CSV processor (pandas) | ✅ |
| Image processor (Pillow, max 800×800) | ✅ |
| PDF processor (pdfplumber) | ✅ |
| Redis + Celery background queue | ✅ |
| Celery Beat 24h auto-cleanup | ✅ |
| SQLite metadata tracking | ✅ |
| Rate limiting (10 req/min per IP) | ✅ |
| Structured logging | ✅ |
| Web dashboard UI | ✅ |
| Automated tests | ✅ |
| One-click deploy script | ✅ |
| One-click update script | ✅ |
| systemd services | ✅ |
| Nginx reverse proxy | ✅ |
| HTTPS / Let's Encrypt | ✅ (via deploy.sh with domain) |
| GitHub repository | ✅ |
| VPS deployed | ✅ |
