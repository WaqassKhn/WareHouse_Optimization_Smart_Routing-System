from __future__ import annotations

from fastapi import APIRouter, Depends

from app.routers.auth import require_roles
from app.schemas import PickingOptimizationRequest, Role
from app.services.inventory import optimize_inventory_placement
from app.services.picking import optimize_picking_routes
from app.services.warehouse import generate_warehouse_layout, validate_blocked


router = APIRouter(prefix="/picking", tags=["picking"])


@router.post("/optimize")
def optimize_picking(
    request: PickingOptimizationRequest,
    _user=Depends(require_roles(Role.admin, Role.planner, Role.analyst)),
) -> dict:
    blocked = [coord.model_dump() for coord in request.blocked]
    layout = generate_warehouse_layout(blocked=blocked)
    inventory_plan = optimize_inventory_placement(None, layout)
    return {
        **optimize_picking_routes(
            layout=layout,
            order_lines=request.order_lines,
            pickers=request.pickers,
            algorithm=request.algorithm,
            congestion_weight=request.congestion_weight,
            inventory_plan=inventory_plan,
        ),
        "coordinate_validation": validate_blocked(layout, blocked),
    }

