# tests/test_api.py
"""
Automated tests for File Processor API.

Run:
    pip install pytest httpx
    pytest tests/ -v
"""
import io
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


# ── Health ────────────────────────────────────────────────────────────────────

def test_health():
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


# ── Upload validation ─────────────────────────────────────────────────────────

def test_upload_rejects_unsupported_type():
    r = client.post(
        "/api/v1/upload",
        files={"file": ("malware.exe", b"fake content", "application/octet-stream")},
    )
    assert r.status_code == 400
    assert "not supported" in r.json()["detail"]


def test_upload_rejects_oversized_file():
    # 51MB of zeros — exceeds 50MB limit
    big = io.BytesIO(b"0" * (51 * 1024 * 1024))
    r = client.post(
        "/api/v1/upload",
        files={"file": ("big.csv", big, "text/csv")},
    )
    assert r.status_code == 413


# ── CSV upload ────────────────────────────────────────────────────────────────

def test_upload_csv_returns_file_id():
    csv_content = b"name,age,city\nAlice,30,Dhaka\nBob,25,Chittagong\n"
    r = client.post(
        "/api/v1/upload",
        files={"file": ("test.csv", io.BytesIO(csv_content), "text/csv")},
    )
    assert r.status_code == 201
    data = r.json()
    assert "file_id" in data
    assert data["file_type"] == "csv"
    assert data["status"] == "queued"
    assert "/api/v1/download/" in data["download_url"]
    return data["file_id"]


# ── Image upload ──────────────────────────────────────────────────────────────

def test_upload_image_returns_file_id():
    # Minimal valid 1x1 red PNG (binary)
    png = (
        b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01'
        b'\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00'
        b'\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18'
        b'\xd8N\x00\x00\x00\x00IEND\xaeB`\x82'
    )
    r = client.post(
        "/api/v1/upload",
        files={"file": ("photo.png", io.BytesIO(png), "image/png")},
    )
    assert r.status_code == 201
    data = r.json()
    assert data["file_type"] == "image"
    assert "file_id" in data


# ── Status endpoint ───────────────────────────────────────────────────────────

def test_status_unknown_id_returns_404():
    r = client.get("/api/v1/status/nonexistent-id-1234")
    assert r.status_code == 404


def test_status_returns_queued_after_upload():
    csv_content = b"x,y\n1,2\n3,4\n"
    upload = client.post(
        "/api/v1/upload",
        files={"file": ("data.csv", io.BytesIO(csv_content), "text/csv")},
    )
    file_id = upload.json()["file_id"]
    r = client.get(f"/api/v1/status/{file_id}")
    assert r.status_code == 200
    assert r.json()["status"] in ("queued", "processing", "done")


# ── Files list ────────────────────────────────────────────────────────────────

def test_list_files_returns_array():
    r = client.get("/api/v1/files")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_list_files_contains_uploaded_file():
    csv_content = b"col1,col2\nval1,val2\n"
    upload = client.post(
        "/api/v1/upload",
        files={"file": ("listing_test.csv", io.BytesIO(csv_content), "text/csv")},
    )
    file_id = upload.json()["file_id"]
    files = client.get("/api/v1/files").json()
    ids = [f["file_id"] for f in files]
    assert file_id in ids


# ── Download ──────────────────────────────────────────────────────────────────

def test_download_unknown_id_returns_404():
    r = client.get("/api/v1/download/nonexistent-id-5678")
    assert r.status_code == 404


def test_download_returns_202_while_pending():
    csv_content = b"a,b\n1,2\n"
    upload = client.post(
        "/api/v1/upload",
        files={"file": ("pending.csv", io.BytesIO(csv_content), "text/csv")},
    )
    file_id = upload.json()["file_id"]
    r = client.get(f"/api/v1/download/{file_id}")
    # Either 202 (still processing) or 200 (done very fast in test env)
    assert r.status_code in (200, 202)


# ── Delete ────────────────────────────────────────────────────────────────────

def test_delete_removes_file():
    csv_content = b"name\nAlice\n"
    upload = client.post(
        "/api/v1/upload",
        files={"file": ("to_delete.csv", io.BytesIO(csv_content), "text/csv")},
    )
    file_id = upload.json()["file_id"]

    # Delete it
    r = client.delete(f"/api/v1/files/{file_id}")
    assert r.status_code == 200

    # Confirm it's gone
    r = client.get(f"/api/v1/status/{file_id}")
    assert r.status_code == 404


def test_delete_unknown_id_returns_404():
    r = client.delete("/api/v1/files/ghost-id-9999")
    assert r.status_code == 404
