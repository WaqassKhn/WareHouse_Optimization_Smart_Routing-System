from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.routers.auth import require_roles
from app.schemas import InventoryOptimizationRequest, Role
from app.services.inventory import default_inventory, optimize_inventory_placement, parse_inventory_csv
from app.services.warehouse import generate_warehouse_layout


router = APIRouter(prefix="/inventory", tags=["inventory"])


@router.get("/demo")
def get_demo_inventory() -> dict:
    return {"items": default_inventory()}


@router.post("/optimize")
def optimize_inventory(request: InventoryOptimizationRequest) -> dict:
    layout = generate_warehouse_layout(blocked=[coord.model_dump() for coord in request.blocked])
    return optimize_inventory_placement(request.items, layout)


@router.post("/upload")
async def upload_inventory(
    file: UploadFile = File(...),
    _user=Depends(require_roles(Role.admin, Role.planner)),
) -> dict:
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV uploads are supported")
    try:
        rows = parse_inventory_csv(await file.read())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    layout = generate_warehouse_layout()
    optimization = optimize_inventory_placement(rows, layout)
    return {"filename": file.filename, "row_count": len(rows), "optimization": optimization}

