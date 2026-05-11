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
├── nginx/
│   └── file_processor.conf   # Nginx reverse proxy config
├── systemd/
│   ├── file_processor_api.service
│   ├── file_processor_worker.service
│   └── file_processor_beat.service
├── storage/
│   ├── uploads/              # Raw uploaded files
│   └── processed/            # Processed output files
├── .env.example
├── requirements.txt
└── README.md
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
 
## Local development
 
**Requirements:** Python 3.10+, Redis
 
```bash
git clone https://github.com/avsk-net/file-processor-api.git
cd file-processor-api
 
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
 
cp .env.example .env
```
 
**`.env` defaults (local):**
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
 
## VPS deployment (Ubuntu 22.04)
 
### 1. Server setup
 
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3.10-venv redis-server nginx git
 
sudo systemctl enable --now redis-server
redis-cli ping   # must return PONG
```
 
### 2. Deploy the app
 
```bash
git clone https://github.com/avsk-net/file-processor-api.git /opt/file_processor_api
cd /opt/file_processor_api
 
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
 
cp .env.example .env
nano .env
```
 
**`.env` on VPS (use absolute paths):**
```
APP_NAME=FileProcessorAPI
UPLOAD_DIR=/opt/file_processor_api/storage/uploads
PROCESSED_DIR=/opt/file_processor_api/storage/processed
MAX_FILE_SIZE_MB=50
FILE_EXPIRY_HOURS=24
REDIS_URL=redis://localhost:6379/0
DATABASE_PATH=/opt/file_processor_api/files.db
```
 
```bash
mkdir -p storage/uploads storage/processed
```
 
### 3. systemd services
 
```bash
sudo cp systemd/*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now file_processor_api file_processor_worker file_processor_beat
 
# Verify all 3 are running
sudo systemctl status file_processor_api file_processor_worker file_processor_beat
```
 
### 4. Nginx
 
```bash
sudo cp nginx/file_processor.conf /etc/nginx/sites-available/file_processor
sudo ln -s /etc/nginx/sites-available/file_processor /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```
 
### 5. HTTPS (optional)
 
```bash
sudo apt install certbot python3-certbot-nginx -y
sudo certbot --nginx -d yourdomain.com
```
 
### Updating after a code push
 
```bash
cd /opt/file_processor_api
git pull
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart file_processor_api file_processor_worker file_processor_beat
