from __future__ import annotations

from fastapi import APIRouter, Depends

from app.routers.auth import require_roles
from app.schemas import DeliveryOptimizationRequest, Role
from app.services.delivery import optimize_delivery_routes


router = APIRouter(prefix="/delivery", tags=["delivery"])


@router.post("/optimize")
def optimize_delivery(
    request: DeliveryOptimizationRequest,
    _user=Depends(require_roles(Role.admin, Role.planner, Role.analyst)),
) -> dict:
    return optimize_delivery_routes(
        stops=request.stops,
        vehicles=request.vehicles,
        traffic=request.traffic,
        fuel_cost_per_liter=request.fuel_cost_per_liter,
        dynamic_reroute=request.dynamic_reroute,
    )

