import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text
import uvicorn

from app.ai.model_loader import model_status, preload_models
from app.api.v1.router import api_router
from app.core.config import settings
from app.db.base import Base, import_models
from app.db.database import engine

logger = logging.getLogger(__name__)

# Import models so SQLAlchemy knows them
import_models()

# Development bootstrap.
# Later this will be replaced completely by Alembic migrations.
Base.metadata.create_all(bind=engine)

# Keep older local databases usable when adding claim fields. ``create_all``
# creates missing tables but does not add columns to existing ones.
def ensure_columns(table_name: str, columns: dict[str, str]) -> None:
    existing_columns = {
        column["name"] for column in inspect(engine).get_columns(table_name)
    }
    with engine.begin() as connection:
        for column_name, column_type in columns.items():
            if column_name not in existing_columns:
                connection.execute(text(
                    f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"
                ))


claim_columns = {
    "customer_address": "VARCHAR(1000)",
    "policy_number": "VARCHAR(100)",
    "insurance_company": "VARCHAR(255)",
    "policy_type": "VARCHAR(100)",
    "policy_expiry": "VARCHAR(30)",
    "accident_time": "VARCHAR(20)",
    "accident_type": "VARCHAR(100)",
}
ensure_columns("claims", claim_columns)
ensure_columns("vehicles", {
    "vin": "VARCHAR(100)",
    "engine_number": "VARCHAR(100)",
})
ensure_columns("users", {
    "address_line": "VARCHAR(500)",
    "city": "VARCHAR(100)",
    "state": "VARCHAR(100)",
    "pincode": "VARCHAR(20)",
    "country": "VARCHAR(100)",
})


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Load YOLO weights once at startup (never per request) and log clearly
    # if something is missing.
    status = preload_models()
    if not (status["damage_model_loaded"] and status["parts_model_loaded"]):
        logger.error("AI models NOT fully loaded: %s", status)
    yield


app = FastAPI(
    lifespan=lifespan,
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "AI-powered vehicle damage assessment "
        "and insurance claim management system."
    ),
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


import os
from fastapi.staticfiles import StaticFiles

os.makedirs("storage", exist_ok=True)
app.mount("/storage", StaticFiles(directory="storage"), name="storage")

# Uploaded claim evidence is stored under settings.UPLOAD_DIR. Expose it so the
# service center can display submitted damage photos in its assessment view.
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")

app.include_router(
    api_router,
    prefix=settings.API_V1_PREFIX,
)


@app.get("/")
def root():
    return {
        "application": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
    }


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "database": "configured",
        "ai_models": model_status(),
    }


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
