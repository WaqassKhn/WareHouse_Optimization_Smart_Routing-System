from __future__ import annotations

from fastapi import APIRouter

from app.services.analytics import build_dashboard_snapshot, generate_recommendations, summarize_operational_health


router = APIRouter(tags=["analytics"])


@router.get("/analytics/dashboard")
def dashboard() -> dict:
    snapshot = build_dashboard_snapshot()
    return {**snapshot, "health": summarize_operational_health(snapshot)}


@router.get("/recommendations")
def recommendations() -> dict:
    return {"recommendations": generate_recommendations()}

