from __future__ import annotations

from fastapi import APIRouter

from app.schemas import Coordinate
from app.services.warehouse import generate_warehouse_layout, validate_blocked


router = APIRouter(prefix="/warehouse", tags=["warehouse"])


@router.get("/layout")
def get_layout() -> dict:
    return generate_warehouse_layout()


@router.post("/layout")
def get_layout_with_obstacles(blocked: list[Coordinate]) -> dict:
    blocked_dicts = [coord.model_dump() for coord in blocked]
    layout = generate_warehouse_layout(blocked=blocked_dicts)
    return {**layout, "coordinate_validation": validate_blocked(layout, blocked_dicts)}

