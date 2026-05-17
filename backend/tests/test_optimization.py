from app.services.delivery import optimize_delivery_routes
from app.services.inventory import SPECIAL_SKUS, optimize_inventory_placement
from app.services.picking import optimize_picking_routes
from app.services.warehouse import generate_warehouse_layout, validate_blocked


def test_layout_marks_dynamic_obstacles_and_invalid_coordinates():
    layout = generate_warehouse_layout(blocked=[{"x": 10, "y": 7}, {"x": 99, "y": 99}])
    cell = next(item for item in layout["cells"] if item["x"] == 10 and item["y"] == 7)
    assert cell["type"] == "blocked"
    assert cell["walkable"] is False

    validation = validate_blocked(layout, [{"x": 10, "y": 7}, {"x": 99, "y": 99}])
    assert validation["accepted"] == [{"x": 10, "y": 7}]
    assert validation["invalid"] == [{"x": 99, "y": 99}]


def test_inventory_places_special_handling_items_in_compliant_zones():
    layout = generate_warehouse_layout()
    result = optimize_inventory_placement(SPECIAL_SKUS, layout)
    by_sku = {item["sku"]: item for item in result["placements"]}

    assert by_sku["HAZ-ACD-100"]["slot"]["type"] == "hazmat"
    assert by_sku["TMP-RES-311"]["slot"]["type"] == "cold_storage"
    assert by_sku["OVR-FRM-420"]["slot"]["type"] == "oversized"
    assert result["slotting_summary"]["occupied_slots"] == len(SPECIAL_SKUS)


def test_picking_optimizer_handles_duplicates_and_returns_routes():
    layout = generate_warehouse_layout(blocked=[{"x": 9, "y": 7}])
    inventory = optimize_inventory_placement(None, layout)
    sku = inventory["placements"][0]["sku"]
    request_lines = [
        {"order_id": "ORD-1", "sku": sku, "quantity": 1, "priority": 1},
        {"order_id": "ORD-1", "sku": sku, "quantity": 1, "priority": 1},
    ]

    result = optimize_picking_routes(
        layout,
        order_lines=request_lines,
        pickers=[{"id": "PICKER-1", "start": {"x": 1, "y": 14}, "shift_minutes_remaining": 120}],
        algorithm="astar",
        inventory_plan=inventory,
    )

    assert result["summary"]["duplicate_order_count"] == 1
    assert result["summary"]["total_travel_distance"] > 0
    assert result["routes"][0]["completed_lines"] == 2


def test_delivery_optimizer_detects_vehicle_overload():
    stops = [
        {"id": "S1", "customer": "Heavy Drop", "x": 5, "y": 5, "demand": 9, "deadline": "10:00", "service_minutes": 5, "priority": 1}
    ]
    vehicles = [{"id": "V1", "capacity": 3, "fuel_liters_per_km": 0.1, "start_x": 0, "start_y": 0, "available_from": "08:00"}]

    result = optimize_delivery_routes(stops=stops, vehicles=vehicles)

    assert result["summary"]["unassigned_stops"] == 1
    assert result["unassigned"][0]["reason"] == "Vehicle overload or no feasible capacity"

