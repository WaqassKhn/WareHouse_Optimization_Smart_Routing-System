from datetime import time
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class Role(str, Enum):
    admin = "admin"
    planner = "planner"
    analyst = "analyst"
    viewer = "viewer"


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: Role


class UserPrincipal(BaseModel):
    email: str
    role: Role


class Coordinate(BaseModel):
    x: int = Field(ge=0)
    y: int = Field(ge=0)


class InventoryItem(BaseModel):
    sku: str
    name: str
    category: str = "general"
    velocity: float = Field(default=0, ge=0)
    unit_cost: float = Field(default=0, ge=0)
    quantity: int = Field(default=0, ge=0)
    length: float = Field(default=0.5, gt=0)
    width: float = Field(default=0.5, gt=0)
    height: float = Field(default=0.5, gt=0)
    weight: float = Field(default=1, ge=0)
    hazardous: bool = False
    fragile: bool = False
    temperature_sensitive: bool = False

    @property
    def cube(self) -> float:
        return self.length * self.width * self.height


class InventoryOptimizationRequest(BaseModel):
    items: list[InventoryItem] | None = None
    blocked: list[Coordinate] = Field(default_factory=list)


class PickOrderLine(BaseModel):
    order_id: str
    sku: str
    quantity: int = Field(default=1, gt=0)
    priority: int = Field(default=3, ge=1, le=5)


class Picker(BaseModel):
    id: str
    start: Coordinate = Field(default_factory=lambda: Coordinate(x=1, y=14))
    shift_minutes_remaining: int = Field(default=480, gt=0)


class PickingOptimizationRequest(BaseModel):
    algorithm: Literal["dijkstra", "astar"] = "astar"
    order_lines: list[PickOrderLine] = Field(default_factory=list)
    pickers: list[Picker] = Field(default_factory=list)
    blocked: list[Coordinate] = Field(default_factory=list)
    congestion_weight: bool = True


class DeliveryStop(BaseModel):
    id: str
    customer: str
    x: float
    y: float
    demand: int = Field(default=1, ge=0)
    deadline: time = Field(default=time(hour=17))
    service_minutes: int = Field(default=12, ge=0)
    priority: int = Field(default=3, ge=1, le=5)


class Vehicle(BaseModel):
    id: str
    capacity: int = Field(gt=0)
    fuel_liters_per_km: float = Field(default=0.13, gt=0)
    start_x: float = 0
    start_y: float = 0
    available_from: time = Field(default=time(hour=8))


class DeliveryOptimizationRequest(BaseModel):
    stops: list[DeliveryStop] | None = None
    vehicles: list[Vehicle] | None = None
    traffic: Literal["light", "normal", "heavy", "incident"] = "normal"
    fuel_cost_per_liter: float = Field(default=1.28, gt=0)
    dynamic_reroute: bool = True


class ReportFormat(str, Enum):
    json = "json"
    csv = "csv"


class Cell(BaseModel):
    x: int
    y: int
    type: str
    walkable: bool
    congestion: float = 0
    label: str | None = None


class WarehouseLayoutResponse(BaseModel):
    width: int
    height: int
    cells: list[Cell]
    dispatch_zones: list[Coordinate]
    obstacles: list[Coordinate]
    legend: dict[str, str]


class ApiMessage(BaseModel):
    message: str
    details: dict[str, Any] = Field(default_factory=dict)

