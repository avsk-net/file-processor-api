# app/main.py
from fastapi import FastAPI
from contextlib import asynccontextmanager

from app.core.config import settings
from app.core.database import init_db
from app.services.storage import ensure_dirs
from app.api.routes import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan runs setup code BEFORE the server accepts requests,
    and teardown code AFTER the server shuts down.
    
    Why lifespan instead of @app.on_event("startup")?
    on_event is deprecated in newer FastAPI. lifespan is the modern way.
    """
    # --- Startup ---
    print(f"Starting {settings.APP_NAME}...")
    init_db()        # create SQLite tables if they don't exist
    ensure_dirs()    # create storage/uploads and storage/processed
    print("✓ Database ready")
    print("✓ Storage directories ready")
    
    yield  # Server runs here — everything after yield is teardown
    
    # --- Shutdown ---
    print("Shutting down...")


app = FastAPI(
    title=settings.APP_NAME,
    description=(
        "Upload CSV, images, or PDFs. "
        "Get back a processed result. "
        "Files automatically expire after 24 hours."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# Register all routes under the /api/v1 prefix
# Good practice: version your API from day one
app.include_router(router, prefix="/api/v1")
