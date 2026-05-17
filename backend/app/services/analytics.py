from __future__ import annotations

from statistics import mean
from typing import Any

try:
    import numpy as np
except Exception:  # pragma: no cover
    np = None

try:
    from sklearn.cluster import KMeans
except Exception:  # pragma: no cover
    KMeans = None

from app.services.delivery import optimize_delivery_routes
from app.services.inventory import optimize_inventory_placement
from app.services.picking import optimize_picking_routes
from app.services.warehouse import generate_warehouse_layout


def build_dashboard_snapshot(blocked: list[dict[str, int]] | None = None) -> dict[str, Any]:
    layout = generate_warehouse_layout(blocked=blocked)
    inventory = optimize_inventory_placement(None, layout)
    picking = optimize_picking_routes(layout, inventory_plan=inventory, algorithm="astar")
    delivery = optimize_delivery_routes(traffic="normal", dynamic_reroute=True)
    recommendations = generate_recommendations(layout, inventory, picking, delivery)

    completed_lines = sum(route["completed_lines"] for route in picking["routes"])
    line_count = picking["summary"]["line_count"]
    picking_time = picking["summary"]["estimated_picking_time_minutes"]
    throughput = completed_lines / max(picking_time / 60, 1)

    kpis = {
        "warehouse_utilization_pct": inventory["slotting_summary"]["utilization_pct"],
        "throughput_lines_per_hour": round(throughput, 2),
        "picking_efficiency_score": picking["summary"]["efficiency_score"],
        "picking_accuracy_pct": round(
            (completed_lines - picking["summary"]["missing_inventory_count"]) / max(line_count, 1) * 100,
            2,
        ),
        "order_fulfillment_rate_pct": round(completed_lines / max(line_count, 1) * 100, 2),
        "travel_reduction_pct": picking["summary"]["travel_reduction_pct"],
        "cost_optimization_pct": round(
            (picking["summary"]["travel_reduction_pct"] + delivery["summary"]["distance_savings_pct"]) / 2,
            2,
        ),
        "order_cycle_time_minutes": round(picking_time / max(len(picking["routes"]), 1) + 42, 2),
        "fuel_cost": delivery["summary"]["fuel_cost"],
        "labor_efficiency_lines_per_labor_hour": round(
            completed_lines / max((picking_time / 60) * max(len(picking["routes"]), 1), 1),
            2,
        ),
        "operational_savings_estimate": round(
            picking["summary"]["baseline_distance"] * 0.68
            - picking["summary"]["total_travel_distance"] * 0.68
            + (delivery["summary"]["baseline_distance_km"] - delivery["summary"]["total_distance_km"]) * 1.42,
            2,
        ),
    }

    return {
        "kpis": kpis,
        "warehouse": layout,
        "inventory": {
            "abc_summary": inventory["abc_summary"],
            "slotting_summary": inventory["slotting_summary"],
            "top_placements": inventory["placements"][:18],
            "unplaced": inventory["unplaced"],
        },
        "picking": picking,
        "delivery": delivery,
        "charts": {
            "abc": _abc_chart(inventory),
            "congestion_heatmap": _heatmap_matrix(layout, picking["heatmap"]),
            "delivery_performance": _delivery_chart(delivery),
            "fuel_cost": _fuel_chart(delivery),
        },
        "recommendations": recommendations,
    }


def generate_recommendations(
    layout: dict | None = None,
    inventory: dict[str, Any] | None = None,
    picking: dict[str, Any] | None = None,
    delivery: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    layout = layout or generate_warehouse_layout()
    inventory = inventory or optimize_inventory_placement(None, layout)
    picking = picking or optimize_picking_routes(layout, inventory_plan=inventory)
    delivery = delivery or optimize_delivery_routes()

    recommendations: list[dict[str, Any]] = []
    high_value_far = [
        item
        for item in inventory["placements"]
        if item["abc_class"] == "A" and item["distance_to_dispatch"] > 10
    ]
    if high_value_far:
        recommendations.append(
            {
                "type": "inventory_redistribution",
                "priority": "high",
                "title": "Move A-class fast movers closer to dispatch",
                "impact": "Expected 8-14% pick travel reduction for high-frequency orders",
                "evidence": f"{len(high_value_far)} A-class SKUs are more than 10 cells from dispatch",
                "action": "Reserve closest standard slots for A-class items and relegate C-class items outward",
            }
        )

    blocked_count = len(layout.get("obstacles", []))
    if blocked_count:
        recommendations.append(
            {
                "type": "congestion_reduction",
                "priority": "high",
                "title": "Clear dynamic aisle blocks before the next pick wave",
                "impact": "Reduces rerouting and simultaneous picker collision risk",
                "evidence": f"{blocked_count} blocked cells are active in the current layout",
                "action": "Dispatch floor staff to clear or route around blocked cross aisles",
            }
        )

    if picking["summary"]["congestion_risk_score"] > 55:
        recommendations.append(
            {
                "type": "labor_balancing",
                "priority": "medium",
                "title": "Stagger picker starts across dispatch lanes",
                "impact": "Improves flow through the highest traffic aisles",
                "evidence": f"Route congestion risk is {picking['summary']['congestion_risk_score']}",
                "action": "Start one picker from the secondary dispatch face and sequence A-class orders first",
            }
        )

    if picking["collision_risk"]:
        recommendations.append(
            {
                "type": "real_time_rerouting",
                "priority": "medium",
                "title": "Resolve simultaneous picker conflicts",
                "impact": "Reduces waiting time and improves safety compliance",
                "evidence": f"{len(picking['collision_risk'])} potential same-cell conflicts detected",
                "action": "Inject 30-60 second dispatch offsets or route lower-priority pickers via alternate cross aisles",
            }
        )

    if delivery["summary"]["unassigned_stops"] > 0:
        recommendations.append(
            {
                "type": "vehicle_capacity",
                "priority": "high",
                "title": "Add capacity or split overloaded delivery stops",
                "impact": "Improves order fulfillment and avoids missed delivery windows",
                "evidence": f"{delivery['summary']['unassigned_stops']} stops could not be assigned",
                "action": "Allocate a larger vehicle or split oversized drops into a second run",
            }
        )

    if delivery["summary"]["late_deliveries"] > 0:
        recommendations.append(
            {
                "type": "delivery_scheduling",
                "priority": "medium",
                "title": "Pull forward early-deadline stops",
                "impact": "Improves on-time performance under traffic pressure",
                "evidence": f"{delivery['summary']['late_deliveries']} stops are projected late",
                "action": "Prioritize first-wave loading for strict deadline customers",
            }
        )

    recommendations.extend(_cluster_congestion_recommendations(picking["heatmap"]))

    if not recommendations:
        recommendations.append(
            {
                "type": "continuous_improvement",
                "priority": "low",
                "title": "Maintain current layout and monitor demand drift",
                "impact": "Preserves stable operating performance",
                "evidence": "No critical congestion, slotting, or delivery exceptions detected",
                "action": "Re-run ABC analysis weekly and after major demand swings",
            }
        )

    return recommendations[:8]


def _cluster_congestion_recommendations(heatmap: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if KMeans is None or np is None:
        return []
    hot_cells = [cell for cell in heatmap if cell["combined"] > 0.74]
    if len(hot_cells) < 4:
        return []
    coords = np.array([[cell["x"], cell["y"]] for cell in hot_cells])
    clusters = KMeans(n_clusters=min(2, len(hot_cells)), n_init="auto", random_state=7).fit(coords)
    centers = clusters.cluster_centers_.round(1).tolist()
    return [
        {
            "type": "ai_congestion_cluster",
            "priority": "medium",
            "title": "Rebalance work around clustered congestion",
            "impact": "ML clustering detected concentrated traffic zones",
            "evidence": f"Hotspot centers near {centers}",
            "action": "Shift non-urgent picks to adjacent aisles and review shelf assignment near these cells",
        }
    ]


def _abc_chart(inventory: dict[str, Any]) -> dict[str, Any]:
    summary = inventory["abc_summary"]["count_by_class"]
    values = inventory["abc_summary"]["value_by_class"]
    return {
        "labels": list(summary.keys()),
        "counts": list(summary.values()),
        "annual_values": [values[key] for key in summary.keys()],
    }


def _heatmap_matrix(layout: dict, heatmap: list[dict[str, Any]]) -> dict[str, Any]:
    by_coord = {(cell["x"], cell["y"]): cell for cell in heatmap}
    z = []
    for y in range(layout["height"]):
        row = []
        for x in range(layout["width"]):
            row.append(by_coord[(x, y)]["combined"])
        z.append(row)
    return {"z": z, "x": list(range(layout["width"])), "y": list(range(layout["height"]))}


def _delivery_chart(delivery: dict[str, Any]) -> dict[str, Any]:
    return {
        "vehicles": [route["vehicle_id"] for route in delivery["routes"]],
        "distance": [route["route_distance_km"] for route in delivery["routes"]],
        "late_stops": [route["late_stops"] for route in delivery["routes"]],
        "capacity": [route["capacity_utilization_pct"] for route in delivery["routes"]],
    }


def _fuel_chart(delivery: dict[str, Any]) -> dict[str, Any]:
    return {
        "vehicles": [route["vehicle_id"] for route in delivery["routes"]],
        "fuel_liters": [route["fuel_liters"] for route in delivery["routes"]],
        "fuel_cost": [route["fuel_cost"] for route in delivery["routes"]],
    }


def summarize_operational_health(snapshot: dict[str, Any]) -> dict[str, Any]:
    kpis = snapshot["kpis"]
    scores = [
        kpis["picking_efficiency_score"],
        kpis["order_fulfillment_rate_pct"],
        snapshot["delivery"]["summary"]["on_time_rate_pct"],
        max(0, 100 - snapshot["picking"]["summary"]["congestion_risk_score"]),
    ]
    return {
        "overall_score": round(mean(scores), 2),
        "risk_level": "low" if mean(scores) >= 85 else "medium" if mean(scores) >= 70 else "high",
        "primary_constraint": _primary_constraint(snapshot),
    }


def _primary_constraint(snapshot: dict[str, Any]) -> str:
    if snapshot["picking"]["summary"]["missing_inventory_count"]:
        return "Inventory availability"
    if snapshot["delivery"]["summary"]["unassigned_stops"]:
        return "Vehicle capacity"
    if snapshot["picking"]["summary"]["congestion_risk_score"] > 55:
        return "Warehouse congestion"
    return "No dominant constraint"

