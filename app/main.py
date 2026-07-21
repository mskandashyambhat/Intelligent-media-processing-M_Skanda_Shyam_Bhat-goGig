import logging

from fastapi import FastAPI

from app.api.routes import router
from app.db.models import init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

app = FastAPI(
    title="Intelligent Media Processing Pipeline",
    description="Async image upload and analysis for field vehicle photos",
    version="1.0.0",
)

app.include_router(router, prefix="/api/v1", tags=["media"])


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/")
def root() -> dict:
    return {
        "service": "Intelligent Media Processing Pipeline",
        "docs": "/docs",
        "health": "/api/v1/health",
    }
