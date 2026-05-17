from __future__ import annotations

import math
from datetime import time, timedelta
from typing import Any

from app.services.warehouse import euclidean


TRAFFIC_MULTIPLIERS = {
    "light": 0.88,
    "normal": 1.0,
    "heavy": 1.28,
    "incident": 1.55,
}


def default_delivery_stops() -> list[dict[str, Any]]:
    return [
        {"id": "DLV-001", "customer": "North Assembly", "x": 8.5, "y": 15.2, "demand": 8, "deadline": "10:30", "service_minutes": 14, "priority": 1},
        {"id": "DLV-002", "customer": "Paint Line", "x": 16.2, "y": 8.8, "demand": 5, "deadline": "11:15", "service_minutes": 12, "priority": 2},
        {"id": "DLV-003", "customer": "Supplier Dock A", "x": 4.3, "y": 24.7, "demand": 9, "deadline": "13:00", "service_minutes": 16, "priority": 2},
        {"id": "DLV-004", "customer": "Packaging Cell", "x": 21.4, "y": 18.2, "demand": 4, "deadline": "12:10", "service_minutes": 10, "priority": 3},
        {"id": "DLV-005", "customer": "Service Depot", "x": 29.1, "y": 6.2, "demand": 7, "deadline": "15:20", "service_minutes": 18, "priority": 3},
        {"id": "DLV-006", "customer": "Final QA", "x": 12.8, "y": 29.5, "demand": 3, "deadline": "14:00", "service_minutes": 10, "priority": 2},
        {"id": "DLV-007", "customer": "Overflow Warehouse", "x": 33.2, "y": 17.8, "demand": 10, "deadline": "16:00", "service_minutes": 20, "priority": 4},
        {"id": "DLV-008", "customer": "Line Maintenance", "x": 18.5, "y": 27.2, "demand": 2, "deadline": "09:45", "service_minutes": 8, "priority": 1},
    ]


def default_vehicles() -> list[dict[str, Any]]:
    return [
        {"id": "VAN-01", "capacity": 18, "fuel_liters_per_km": 0.12, "start_x": 0, "start_y": 0, "available_from": "08:00"},
        {"id": "TRUCK-02", "capacity": 30, "fuel_liters_per_km": 0.22, "start_x": 0, "start_y": 0, "available_from": "08:15"},
        {"id": "EV-03", "capacity": 12, "fuel_liters_per_km": 0.04, "start_x": 0, "start_y": 0, "available_from": "08:00"},
    ]


def optimize_delivery_routes(
    stops: list[Any] | None = None,
    vehicles: list[Any] | None = None,
    traffic: str = "normal",
    fuel_cost_per_liter: float = 1.28,
    dynamic_reroute: bool = True,
) -> dict[str, Any]:
    normalized_stops = [_normalize_stop(stop) for stop in (stops or default_delivery_stops())]
    normalized_vehicles = [_normalize_vehicle(vehicle) for vehicle in (vehicles or default_vehicles())]
    traffic_multiplier = TRAFFIC_MULTIPLIERS.get(traffic, 1.0)

    states = {
        vehicle["id"]: {
            "vehicle": vehicle,
            "load": 0,
            "current": (vehicle["start_x"], vehicle["start_y"]),
            "clock_minutes": _time_to_minutes(vehicle["available_from"]),
            "stops": [],
            "distance": 0.0,
            "late_stops": 0,
            "fuel_liters": 0.0,
        }
        for vehicle in normalized_vehicles
    }
    unassigned: list[dict[str, Any]] = []

    for stop in sorted(normalized_stops, key=lambda item: (item["priority"], _time_to_minutes(item["deadline"]))):
        candidates = []
        for state in states.values():
            vehicle = state["vehicle"]
            if state["load"] + stop["demand"] > vehicle["capacity"]:
                continue
            effective_distance = _distance_with_traffic(
                state["current"],
                (stop["x"], stop["y"]),
                traffic_multiplier,
                dynamic_reroute,
            )
            travel_minutes = _travel_minutes(effective_distance)
            arrival = state["clock_minutes"] + travel_minutes
            lateness = max(0, arrival - _time_to_minutes(stop["deadline"]))
            capacity_pressure = (state["load"] + stop["demand"]) / vehicle["capacity"]
            score = effective_distance + lateness * 0.9 + capacity_pressure * 4
            candidates.append((score, state, effective_distance, arrival, lateness))

        if not candidates:
            unassigned.append({**stop, "reason": "Vehicle overload or no feasible capacity"})
            continue

        _, state, effective_distance, arrival, lateness = min(candidates, key=lambda value: value[0])
        vehicle = state["vehicle"]
        state["load"] += stop["demand"]
        state["distance"] += effective_distance
        state["fuel_liters"] += effective_distance * vehicle["fuel_liters_per_km"]
        state["current"] = (stop["x"], stop["y"])
        state["clock_minutes"] = arrival + stop["service_minutes"]
        state["late_stops"] += int(lateness > 0)
        state["stops"].append(
            {
                **stop,
                "arrival": _minutes_to_time(arrival),
                "departure": _minutes_to_time(state["clock_minutes"]),
                "distance_from_previous": round(effective_distance, 2),
                "late_by_minutes": round(lateness, 1),
            }
        )

    routes = []
    for state in states.values():
        vehicle = state["vehicle"]
        return_distance = _distance_with_traffic(
            state["current"],
            (vehicle["start_x"], vehicle["start_y"]),
            traffic_multiplier,
            dynamic_reroute,
        )
        if state["stops"]:
            state["distance"] += return_distance
            state["fuel_liters"] += return_distance * vehicle["fuel_liters_per_km"]
            state["clock_minutes"] += _travel_minutes(return_distance)
        routes.append(
            {
                "vehicle_id": vehicle["id"],
                "capacity": vehicle["capacity"],
                "load": state["load"],
                "capacity_utilization_pct": round(state["load"] / vehicle["capacity"] * 100, 2),
                "stops": state["stops"],
                "polyline": _route_polyline(vehicle, state["stops"]),
                "route_distance_km": round(state["distance"], 2),
                "fuel_liters": round(state["fuel_liters"], 2),
                "fuel_cost": round(state["fuel_liters"] * fuel_cost_per_liter, 2),
                "late_stops": state["late_stops"],
                "estimated_finish": _minutes_to_time(state["clock_minutes"]),
                "return_to_depot_km": round(return_distance if state["stops"] else 0, 2),
            }
        )

    total_distance = sum(route["route_distance_km"] for route in routes)
    total_fuel = sum(route["fuel_liters"] for route in routes)
    total_late = sum(route["late_stops"] for route in routes)
    assigned_count = sum(len(route["stops"]) for route in routes)
    baseline_distance = _baseline_delivery_distance(normalized_stops, traffic_multiplier)
    distance_savings = (
        round((baseline_distance - total_distance) / baseline_distance * 100, 2)
        if baseline_distance
        else 0
    )

    return {
        "traffic": traffic,
        "dynamic_reroute": dynamic_reroute,
        "routes": routes,
        "unassigned": unassigned,
        "summary": {
            "assigned_stops": assigned_count,
            "unassigned_stops": len(unassigned),
            "total_distance_km": round(total_distance, 2),
            "baseline_distance_km": round(baseline_distance, 2),
            "distance_savings_pct": distance_savings,
            "fuel_liters": round(total_fuel, 2),
            "fuel_cost": round(total_fuel * fuel_cost_per_liter, 2),
            "late_deliveries": total_late,
            "on_time_rate_pct": round((assigned_count - total_late) / max(assigned_count, 1) * 100, 2),
            "average_capacity_utilization_pct": round(
                sum(route["capacity_utilization_pct"] for route in routes) / max(len(routes), 1),
                2,
            ),
        },
    }


def _distance_with_traffic(
    a: tuple[float, float],
    b: tuple[float, float],
    traffic_multiplier: float,
    dynamic_reroute: bool,
) -> float:
    distance = euclidean(a, b)
    if dynamic_reroute and traffic_multiplier > 1.3 and b[0] > 20:
        return distance * (traffic_multiplier - 0.18)
    return distance * traffic_multiplier


def _baseline_delivery_distance(stops: list[dict[str, Any]], traffic_multiplier: float) -> float:
    current = (0.0, 0.0)
    distance = 0.0
    for stop in stops:
        target = (stop["x"], stop["y"])
        distance += euclidean(current, target) * traffic_multiplier
        current = target
    distance += euclidean(current, (0.0, 0.0)) * traffic_multiplier
    return distance


def _route_polyline(vehicle: dict[str, Any], stops: list[dict[str, Any]]) -> list[dict[str, float]]:
    points = [{"x": vehicle["start_x"], "y": vehicle["start_y"]}]
    points.extend({"x": stop["x"], "y": stop["y"]} for stop in stops)
    points.append({"x": vehicle["start_x"], "y": vehicle["start_y"]})
    return points


def _travel_minutes(distance_km: float, avg_speed_kmh: float = 38) -> float:
    return distance_km / avg_speed_kmh * 60


def _normalize_stop(stop: Any) -> dict[str, Any]:
    raw = stop.model_dump() if hasattr(stop, "model_dump") else dict(stop)
    raw["deadline"] = _parse_time(raw["deadline"])
    raw["x"] = float(raw["x"])
    raw["y"] = float(raw["y"])
    raw["demand"] = int(raw["demand"])
    raw["priority"] = int(raw.get("priority", 3))
    raw["service_minutes"] = int(raw.get("service_minutes", 12))
    return raw


def _normalize_vehicle(vehicle: Any) -> dict[str, Any]:
    raw = vehicle.model_dump() if hasattr(vehicle, "model_dump") else dict(vehicle)
    raw["available_from"] = _parse_time(raw["available_from"])
    raw["capacity"] = int(raw["capacity"])
    raw["fuel_liters_per_km"] = float(raw["fuel_liters_per_km"])
    raw["start_x"] = float(raw.get("start_x", 0))
    raw["start_y"] = float(raw.get("start_y", 0))
    return raw


def _parse_time(value: str | time) -> time:
    if isinstance(value, time):
        return value
    hours, minutes = value.split(":")[:2]
    return time(hour=int(hours), minute=int(minutes))


def _time_to_minutes(value: str | time) -> int:
    parsed = _parse_time(value)
    return parsed.hour * 60 + parsed.minute


def _minutes_to_time(value: float) -> str:
    value = int(math.ceil(value))
    day_minutes = 24 * 60
    normalized = value % day_minutes
    converted = (timedelta(minutes=normalized) + timedelta()).seconds // 60
    return f"{converted // 60:02d}:{converted % 60:02d}"

