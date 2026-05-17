from __future__ import annotations

import csv
import io
import random
from typing import Any, Iterable

try:
    import pandas as pd
except Exception:  # pragma: no cover
    pd = None

from app.services.warehouse import (
    Coord,
    list_storage_slots,
    manhattan,
    nearest_dispatch,
    nearest_walkable,
)


SPECIAL_SKUS = [
    {
        "sku": "HAZ-ACD-100",
        "name": "Industrial acid additive",
        "category": "hazmat",
        "velocity": 36,
        "unit_cost": 140,
        "quantity": 55,
        "length": 0.6,
        "width": 0.5,
        "height": 0.5,
        "weight": 18,
        "hazardous": True,
        "fragile": False,
        "temperature_sensitive": False,
    },
    {
        "sku": "FRG-SNS-210",
        "name": "Vision sensor assembly",
        "category": "electronics",
        "velocity": 115,
        "unit_cost": 240,
        "quantity": 180,
        "length": 0.3,
        "width": 0.3,
        "height": 0.2,
        "weight": 2,
        "hazardous": False,
        "fragile": True,
        "temperature_sensitive": False,
    },
    {
        "sku": "TMP-RES-311",
        "name": "Temperature controlled resin",
        "category": "raw_material",
        "velocity": 76,
        "unit_cost": 88,
        "quantity": 92,
        "length": 0.45,
        "width": 0.45,
        "height": 0.7,
        "weight": 11,
        "hazardous": False,
        "fragile": False,
        "temperature_sensitive": True,
    },
    {
        "sku": "OVR-FRM-420",
        "name": "Oversized conveyor frame",
        "category": "fabrication",
        "velocity": 22,
        "unit_cost": 980,
        "quantity": 18,
        "length": 2.4,
        "width": 1.1,
        "height": 0.6,
        "weight": 84,
        "hazardous": False,
        "fragile": False,
        "temperature_sensitive": False,
    },
]


def default_inventory(count: int = 48) -> list[dict[str, Any]]:
    rng = random.Random(42)
    categories = ["bearings", "electronics", "fasteners", "packaging", "raw_material", "spares"]
    items: list[dict[str, Any]] = []

    for idx in range(count):
        category = categories[idx % len(categories)]
        velocity = max(4, int(rng.lognormvariate(3.7, 0.62)))
        unit_cost = round(rng.uniform(4, 420), 2)
        items.append(
            {
                "sku": f"SKU-{idx + 1:04d}",
                "name": f"{category.replace('_', ' ').title()} item {idx + 1}",
                "category": category,
                "velocity": velocity,
                "unit_cost": unit_cost,
                "quantity": rng.randint(15, 650),
                "length": round(rng.uniform(0.15, 1.0), 2),
                "width": round(rng.uniform(0.12, 0.8), 2),
                "height": round(rng.uniform(0.08, 0.9), 2),
                "weight": round(rng.uniform(0.2, 28), 2),
                "hazardous": False,
                "fragile": category == "electronics" and rng.random() < 0.35,
                "temperature_sensitive": category == "raw_material" and rng.random() < 0.25,
            }
        )

    return SPECIAL_SKUS + items


def _item_to_dict(item: Any) -> dict[str, Any]:
    if hasattr(item, "model_dump"):
        return item.model_dump()
    return dict(item)


def run_abc_analysis(items: Iterable[Any]) -> list[dict[str, Any]]:
    rows = [_item_to_dict(item) for item in items]
    if not rows:
        return []

    if pd is not None:
        df = pd.DataFrame(rows)
        df["annual_value"] = df["velocity"].astype(float) * df["unit_cost"].astype(float)
        df = df.sort_values("annual_value", ascending=False).reset_index(drop=True)
        total = max(float(df["annual_value"].sum()), 1.0)
        df["cumulative_pct"] = df["annual_value"].cumsum() / total
        df["abc_class"] = df["cumulative_pct"].apply(_classify_abc)
        return df.to_dict(orient="records")

    enriched = []
    total_value = 0.0
    for row in rows:
        annual_value = float(row.get("velocity", 0)) * float(row.get("unit_cost", 0))
        total_value += annual_value
        enriched.append({**row, "annual_value": annual_value})
    running = 0.0
    for row in sorted(enriched, key=lambda value: value["annual_value"], reverse=True):
        running += row["annual_value"]
        row["cumulative_pct"] = running / max(total_value, 1.0)
        row["abc_class"] = _classify_abc(row["cumulative_pct"])
    return sorted(enriched, key=lambda value: value["annual_value"], reverse=True)


def _classify_abc(cumulative_pct: float) -> str:
    if cumulative_pct <= 0.80:
        return "A"
    if cumulative_pct <= 0.95:
        return "B"
    return "C"


def optimize_inventory_placement(items: Iterable[Any] | None, layout: dict) -> dict[str, Any]:
    analyzed_items = run_abc_analysis(items or default_inventory())
    slots = list_storage_slots(layout)
    assigned_slots: set[Coord] = set()
    placements: list[dict[str, Any]] = []
    unplaced: list[dict[str, Any]] = []

    for item in analyzed_items:
        scored_slots = []
        for slot in slots:
            coord = (slot["x"], slot["y"])
            if coord in assigned_slots:
                continue
            score, reason, hard_violation = _slot_score(item, slot, layout)
            scored_slots.append((score, hard_violation, reason, slot))

        scored_slots.sort(key=lambda value: (value[1], value[0]))
        if not scored_slots:
            unplaced.append({"sku": item["sku"], "reason": "No available storage slot"})
            continue

        score, hard_violation, reason, slot = scored_slots[0]
        if hard_violation and score > 500:
            unplaced.append(
                {
                    "sku": item["sku"],
                    "reason": "No compliant slot available for special handling constraints",
                    "required": _special_requirements(item),
                }
            )
            continue

        coord = (slot["x"], slot["y"])
        assigned_slots.add(coord)
        pick_face = nearest_walkable(layout, coord)
        placements.append(
            {
                "sku": item["sku"],
                "name": item["name"],
                "category": item.get("category", "general"),
                "abc_class": item["abc_class"],
                "annual_value": round(float(item.get("annual_value", 0)), 2),
                "velocity": item.get("velocity", 0),
                "quantity": item.get("quantity", 0),
                "slot": {"x": slot["x"], "y": slot["y"], "type": slot["type"]},
                "pick_face": {"x": pick_face[0], "y": pick_face[1]},
                "distance_to_dispatch": manhattan(coord, nearest_dispatch(layout, coord)),
                "special_handling": _special_requirements(item),
                "placement_reason": reason,
                "slot_score": round(float(score), 2),
            }
        )

    total_slots = len(slots)
    return {
        "placements": placements,
        "unplaced": unplaced,
        "abc_summary": _abc_summary(analyzed_items),
        "slotting_summary": {
            "total_slots": total_slots,
            "occupied_slots": len(placements),
            "available_slots": max(total_slots - len(placements), 0),
            "utilization_pct": round(len(placements) / max(total_slots, 1) * 100, 2),
        },
        "items": analyzed_items,
    }


def _slot_score(item: dict[str, Any], slot: dict[str, Any], layout: dict) -> tuple[float, str, bool]:
    coord = (slot["x"], slot["y"])
    distance = manhattan(coord, nearest_dispatch(layout, coord))
    score = float(distance)
    reasons: list[str] = []
    hard_violation = False

    if item["abc_class"] == "A":
        score *= 0.55
        reasons.append("High velocity item placed close to dispatch")
    elif item["abc_class"] == "B":
        score *= 0.9
        reasons.append("Moderate velocity item placed in mid-access storage")
    else:
        score *= 1.2
        reasons.append("Low velocity item allowed farther from dispatch")

    cube = float(item.get("length", 0.1)) * float(item.get("width", 0.1)) * float(item.get("height", 0.1))
    oversized = cube > 1.2 or float(item.get("weight", 0)) > 60

    if oversized:
        if slot["type"] != "oversized":
            score += 650
            hard_violation = True
        else:
            score -= 12
            reasons.append("Oversized item assigned to oversized bay")

    if item.get("hazardous"):
        if slot["type"] != "hazmat":
            score += 700
            hard_violation = True
        else:
            score -= 10
            reasons.append("Hazardous item isolated in hazmat storage")

    if item.get("temperature_sensitive"):
        if slot["type"] != "cold_storage":
            score += 700
            hard_violation = True
        else:
            score -= 10
            reasons.append("Temperature-sensitive item assigned to cold storage")

    if item.get("fragile"):
        score += float(slot.get("congestion", 0)) * 10
        reasons.append("Fragile item prefers lower congestion pick face")

    return score, "; ".join(reasons), hard_violation


def _special_requirements(item: dict[str, Any]) -> list[str]:
    requirements: list[str] = []
    cube = float(item.get("length", 0.1)) * float(item.get("width", 0.1)) * float(item.get("height", 0.1))
    if cube > 1.2 or float(item.get("weight", 0)) > 60:
        requirements.append("oversized")
    if item.get("hazardous"):
        requirements.append("hazardous")
    if item.get("fragile"):
        requirements.append("fragile")
    if item.get("temperature_sensitive"):
        requirements.append("temperature_controlled")
    return requirements or ["standard"]


def _abc_summary(items: list[dict[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {"A": 0, "B": 0, "C": 0}
    value_summary: dict[str, float] = {"A": 0.0, "B": 0.0, "C": 0.0}
    for item in items:
        item_class = item["abc_class"]
        summary[item_class] += 1
        value_summary[item_class] += float(item.get("annual_value", 0))
    return {
        "count_by_class": summary,
        "value_by_class": {key: round(value, 2) for key, value in value_summary.items()},
    }


def parse_inventory_csv(raw: bytes) -> list[dict[str, Any]]:
    text = raw.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    required = {"sku", "name", "category", "velocity", "unit_cost", "quantity"}
    missing = required - set(reader.fieldnames or [])
    if missing:
        raise ValueError(f"CSV missing required columns: {', '.join(sorted(missing))}")

    rows: list[dict[str, Any]] = []
    for row in reader:
        rows.append(
            {
                "sku": row["sku"],
                "name": row["name"],
                "category": row.get("category") or "general",
                "velocity": _float(row.get("velocity")),
                "unit_cost": _float(row.get("unit_cost")),
                "quantity": int(_float(row.get("quantity"))),
                "length": _float(row.get("length"), 0.5),
                "width": _float(row.get("width"), 0.5),
                "height": _float(row.get("height"), 0.5),
                "weight": _float(row.get("weight"), 1),
                "hazardous": _bool(row.get("hazardous")),
                "fragile": _bool(row.get("fragile")),
                "temperature_sensitive": _bool(row.get("temperature_sensitive")),
            }
        )
    return rows


def _float(value: str | None, default: float = 0) -> float:
    if value is None or value == "":
        return default
    return float(value)


def _bool(value: str | bool | None) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"true", "1", "yes", "y"}

