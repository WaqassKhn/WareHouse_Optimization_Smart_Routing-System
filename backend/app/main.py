from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.database import init_database
from app.routers import analytics, auth, delivery, inventory, picking, reports, warehouse


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="AI-powered warehouse optimization and smart routing simulation API.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(warehouse.router, prefix="/api")
app.include_router(inventory.router, prefix="/api")
app.include_router(picking.router, prefix="/api")
app.include_router(delivery.router, prefix="/api")
app.include_router(analytics.router, prefix="/api")
app.include_router(reports.router, prefix="/api")


@app.on_event("startup")
def startup() -> None:
    init_database()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "warehouse-optimization-api"}

