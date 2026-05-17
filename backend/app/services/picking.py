from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from app.services.inventory import optimize_inventory_placement
from app.services.warehouse import (
    Coord,
    coords_to_dicts,
    manhattan,
    nearest_walkable,
    shortest_path,
)


def default_pick_order(placements: list[dict[str, Any]], count: int = 14) -> list[dict[str, Any]]:
    sorted_items = sorted(
        placements,
        key=lambda item: ({"A": 0, "B": 1, "C": 2}[item["abc_class"]], -float(item["velocity"])),
    )
    return [
        {
            "order_id": f"ORD-{1000 + idx}",
            "sku": item["sku"],
            "quantity": 1 + (idx % 3 == 0),
            "priority": 1 if item["abc_class"] == "A" else 3,
        }
        for idx, item in enumerate(sorted_items[:count])
    ]


def default_pickers() -> list[dict[str, Any]]:
    return [
        {"id": "PICKER-1", "start": {"x": 1, "y": 14}, "shift_minutes_remaining": 420},
        {"id": "PICKER-2", "start": {"x": 5, "y": 14}, "shift_minutes_remaining": 420},
        {"id": "PICKER-3", "start": {"x": 2, "y": 15}, "shift_minutes_remaining": 360},
    ]


def optimize_picking_routes(
    layout: dict,
    order_lines: list[Any] | None = None,
    pickers: list[Any] | None = None,
    algorithm: str = "astar",
    congestion_weight: bool = True,
    inventory_plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    inventory_plan = inventory_plan or optimize_inventory_placement(None, layout)
    placements = inventory_plan["placements"]
    placement_by_sku = {item["sku"]: item for item in placements}
    normalized_lines = [_model_to_dict(line) for line in (order_lines or default_pick_order(placements))]
    normalized_pickers = [_model_to_dict(picker) for picker in (pickers or default_pickers())]

    duplicate_orders = _duplicate_order_lines(normalized_lines)
    available_lines: list[dict[str, Any]] = []
    missing_inventory: list[dict[str, Any]] = []
    for line in normalized_lines:
        if line["sku"] not in placement_by_sku:
            missing_inventory.append(
                {
                    "order_id": line["order_id"],
                    "sku": line["sku"],
                    "reason": "SKU is not present in optimized inventory placement",
                }
            )
        else:
            available_lines.append(line)

    assignments = _assign_lines_to_pickers(available_lines, normalized_pickers, placement_by_sku)
    routes = []
    all_paths: list[Coord] = []
    for picker in normalized_pickers:
        picker_id = picker["id"]
        assigned = assignments[picker_id]
        route = _build_picker_route(
            layout=layout,
            picker=picker,
            lines=assigned,
            placement_by_sku=placement_by_sku,
            algorithm=algorithm,
            congestion_weight=congestion_weight,
        )
        all_paths.extend([(point["x"], point["y"]) for point in route["path"]])
        routes.append(route)

    collision_risk = _collision_risk(routes)
    total_distance = round(sum(route["travel_distance"] for route in routes), 2)
    baseline_distance = round(sum(route["baseline_distance"] for route in routes), 2)
    travel_reduction = (
        round((baseline_distance - total_distance) / baseline_distance * 100, 2)
        if baseline_distance
        else 0
    )
    avg_efficiency = round(
        sum(route["efficiency_score"] for route in routes) / max(len(routes), 1),
        2,
    )

    return {
        "algorithm": algorithm,
        "routes": routes,
        "summary": {
            "total_travel_distance": total_distance,
            "baseline_distance": baseline_distance,
            "travel_reduction_pct": travel_reduction,
            "estimated_picking_time_minutes": round(
                sum(route["estimated_picking_time_minutes"] for route in routes), 2
            ),
            "efficiency_score": avg_efficiency,
            "picker_count": len(normalized_pickers),
            "line_count": len(normalized_lines),
            "missing_inventory_count": len(missing_inventory),
            "duplicate_order_count": len(duplicate_orders),
            "congestion_risk_score": _congestion_risk_score(layout, all_paths),
        },
        "missing_inventory": missing_inventory,
        "duplicate_orders": duplicate_orders,
        "collision_risk": collision_risk,
        "heatmap": route_heatmap(layout, all_paths),
    }


def _build_picker_route(
    layout: dict,
    picker: dict[str, Any],
    lines: list[dict[str, Any]],
    placement_by_sku: dict[str, dict[str, Any]],
    algorithm: str,
    congestion_weight: bool,
) -> dict[str, Any]:
    start = _coord_from_dict(picker["start"])
    current = nearest_walkable(layout, start)
    remaining = list(lines)
    path: list[Coord] = [current]
    stops: list[dict[str, Any]] = []
    travel_cost = 0.0
    failed_lines: list[dict[str, Any]] = []

    while remaining:
        candidates: list[tuple[float, dict[str, Any], Any]] = []
        unreachable: list[dict[str, Any]] = []
        for line in remaining:
            target = _coord_from_dict(placement_by_sku[line["sku"]]["pick_face"])
            try:
                result = shortest_path(layout, current, target, algorithm, congestion_weight)
                priority_weight = max(0.25, line.get("priority", 3) / 5)
                candidates.append((result.cost * priority_weight, line, result))
            except ValueError:
                unreachable.append({**line, "reason": "No path available due to blocked aisles"})

        failed_lines.extend(unreachable)
        if unreachable:
            unreachable_keys = {(line["order_id"], line["sku"]) for line in unreachable}
            remaining = [
                line
                for line in remaining
                if (line["order_id"], line["sku"]) not in unreachable_keys
            ]

        if not candidates:
            break

        _, line, best_result = min(candidates, key=lambda value: value[0])
        remaining.remove(line)
        placement = placement_by_sku[line["sku"]]
        segment = best_result.path
        if len(segment) > 1:
            path.extend(segment[1:])
        travel_cost += best_result.cost
        current = segment[-1]
        stops.append(
            {
                "order_id": line["order_id"],
                "sku": line["sku"],
                "quantity": line["quantity"],
                "slot": placement["slot"],
                "pick_face": placement["pick_face"],
                "abc_class": placement["abc_class"],
                "segment_distance": round(best_result.cost, 2),
            }
        )

    baseline_distance = _baseline_distance(layout, start, lines, placement_by_sku)
    picking_time = travel_cost * 0.42 + len(stops) * 0.65 + _congestion_risk_score(layout, path) * 0.12
    efficiency = round(min(125.0, baseline_distance / max(travel_cost, 1) * 100), 2)

    return {
        "picker_id": picker["id"],
        "assigned_lines": len(lines),
        "completed_lines": len(stops),
        "failed_lines": failed_lines,
        "path": coords_to_dicts(path),
        "stops": stops,
        "travel_distance": round(travel_cost, 2),
        "baseline_distance": round(baseline_distance, 2),
        "estimated_picking_time_minutes": round(picking_time, 2),
        "efficiency_score": efficiency,
        "timeline": _timeline(path),
    }


def _assign_lines_to_pickers(
    lines: list[dict[str, Any]],
    pickers: list[dict[str, Any]],
    placement_by_sku: dict[str, dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    assignments: dict[str, list[dict[str, Any]]] = {picker["id"]: [] for picker in pickers}
    loads: dict[str, float] = {picker["id"]: 0 for picker in pickers}
    picker_positions: dict[str, Coord] = {
        picker["id"]: _coord_from_dict(picker["start"]) for picker in pickers
    }

    sorted_lines = sorted(lines, key=lambda line: (line.get("priority", 3), line["order_id"], line["sku"]))
    for line in sorted_lines:
        target = _coord_from_dict(placement_by_sku[line["sku"]]["pick_face"])
        picker = min(
            pickers,
            key=lambda candidate: loads[candidate["id"]]
            + manhattan(picker_positions[candidate["id"]], target) * 0.35,
        )
        picker_id = picker["id"]
        assignments[picker_id].append(line)
        loads[picker_id] += manhattan(picker_positions[picker_id], target) + line["quantity"]
        picker_positions[picker_id] = target
    return assignments


def _duplicate_order_lines(lines: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counter = Counter((line["order_id"], line["sku"]) for line in lines)
    return [
        {"order_id": order_id, "sku": sku, "count": count}
        for (order_id, sku), count in counter.items()
        if count > 1
    ]


def _baseline_distance(
    layout: dict,
    start: Coord,
    lines: list[dict[str, Any]],
    placement_by_sku: dict[str, dict[str, Any]],
) -> float:
    current = nearest_walkable(layout, start)
    distance = 0.0
    for line in lines:
        if line["sku"] not in placement_by_sku:
            continue
        target = _coord_from_dict(placement_by_sku[line["sku"]]["pick_face"])
        distance += manhattan(current, target)
        current = target
    return max(distance, 1.0)


def _congestion_risk_score(layout: dict, path: list[Coord]) -> float:
    cell_lookup = {(cell["x"], cell["y"]): cell for cell in layout["cells"]}
    if not path:
        return 0
    return round(
        sum(float(cell_lookup.get(point, {}).get("congestion", 0)) for point in path)
        / max(len(path), 1)
        * 100,
        2,
    )


def route_heatmap(layout: dict, points: list[Coord]) -> list[dict[str, Any]]:
    counts = Counter(points)
    heatmap = []
    for cell in layout["cells"]:
        coord = (cell["x"], cell["y"])
        heatmap.append(
            {
                "x": cell["x"],
                "y": cell["y"],
                "visits": counts.get(coord, 0),
                "base_congestion": cell["congestion"],
                "combined": round(cell["congestion"] + counts.get(coord, 0) * 0.08, 3),
            }
        )
    return heatmap


def _collision_risk(routes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_time: dict[int, defaultdict[Coord, list[str]]] = defaultdict(lambda: defaultdict(list))
    for route in routes:
        for tick, point in enumerate(route["path"]):
            by_time[tick][(point["x"], point["y"])].append(route["picker_id"])

    collisions = []
    for tick, cells in by_time.items():
        for coord, pickers in cells.items():
            if len(pickers) > 1:
                collisions.append({"tick": tick, "x": coord[0], "y": coord[1], "pickers": pickers})
    return collisions[:25]


def _timeline(path: list[Coord]) -> list[dict[str, Any]]:
    return [{"tick": idx, "x": x, "y": y} for idx, (x, y) in enumerate(path)]


def _coord_from_dict(value: dict[str, Any] | Coord) -> Coord:
    if isinstance(value, tuple):
        return value
    return int(value["x"]), int(value["y"])


def _model_to_dict(value: Any) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    return dict(value)
