# File Processor API

Upload a CSV, image, or PDF — get back a processed result. Files expire automatically after 24 hours.

Live dashboard at `/` · API docs at `/docs`

---

## What it does

| Input | Output |
|---|---|
| `.csv` | JSON report — row count, column stats, null counts, 5-row preview |
| `.jpg .jpeg .png .webp` | Resized JPEG, max 800×800, quality 85 |
| `.pdf` | JSON text extraction per page |

---

## Stack

- **FastAPI** — REST API + serves web UI
- **Celery + Redis** — background processing queue
- **Celery Beat** — hourly cleanup of expired files
- **SQLite** — file metadata and expiry tracking
- **Nginx** — reverse proxy
- **systemd** — process management on VPS

---

## Local setup

**Requirements:** Python 3.10+, Redis

```bash
git clone https://github.com/avsk-net/file-processor-api.git
cd file-processor-api

python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
```

Run 3 terminals:

```bash
# API server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Worker
celery -A app.workers.celery_app worker --loglevel=info --concurrency=2

# Scheduler
celery -A app.workers.celery_app beat --loglevel=info
```

Open `http://localhost:8000`

---

## API

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/upload` | Upload a file |
| `GET` | `/api/v1/files` | List all files |
| `GET` | `/api/v1/status/{id}` | Check processing status |
| `GET` | `/api/v1/download/{id}` | Download processed result |
| `DELETE` | `/api/v1/files/{id}` | Delete a file |
| `GET` | `/api/v1/health` | Health check |

```bash
# Upload
curl -X POST http://localhost:8000/api/v1/upload -F "file=@data.csv"

# Download
curl -OJ http://localhost:8000/api/v1/download/<file_id>
```

**Limits:** 50MB max · CSV, JPG, PNG, WEBP, PDF only · 10 uploads/min per IP

---

## VPS deployment

```bash
# Clone and set up
git clone https://github.com/avsk-net/file-processor-api.git /opt/file_processor_api
cd /opt/file_processor_api
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env && nano .env

# Services
sudo cp systemd/*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now file_processor_api file_processor_worker file_processor_beat

# Nginx
sudo cp nginx/file_processor.conf /etc/nginx/sites-available/file_processor
sudo ln -s /etc/nginx/sites-available/file_processor /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

**Updating:**

```bash
cd /opt/file_processor_api && git pull
sudo systemctl restart file_processor_api file_processor_worker file_processor_beat
```

---

## Project structure

```
app/
├── main.py               # App entry point
├── api/routes.py         # All endpoints
├── core/
│   ├── config.py         # Settings (.env)
│   └── database.py       # SQLite queries
├── services/
│   ├── processor.py      # CSV / image / PDF logic
│   └── storage.py        # File I/O helpers
├── static/index.html     # Web dashboard
└── workers/
    ├── celery_app.py     # Celery + Beat config
    └── tasks.py          # Background jobs
```
