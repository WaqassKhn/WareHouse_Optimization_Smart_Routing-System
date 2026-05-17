from __future__ import annotations

import heapq
import math
from collections import deque
from dataclasses import dataclass
from typing import Iterable

try:
    import networkx as nx
except Exception:  # pragma: no cover - fallback keeps core tests runnable without optional deps
    nx = None


Coord = tuple[int, int]


LEGEND = {
    "aisle": "Open travel aisle",
    "shelf": "Standard storage shelf",
    "dispatch": "Dispatch and staging zone",
    "restricted": "Restricted or unsafe zone",
    "blocked": "Dynamic obstacle or blocked aisle",
    "cold_storage": "Temperature-controlled shelf",
    "hazmat": "Hazardous goods shelf",
    "oversized": "Oversized goods bay",
}


@dataclass(frozen=True)
class PathResult:
    path: list[Coord]
    cost: float
    visited: int


def _as_coord_set(coords: Iterable[dict | Coord] | None) -> set[Coord]:
    normalized: set[Coord] = set()
    for coord in coords or []:
        if isinstance(coord, dict):
            normalized.add((int(coord["x"]), int(coord["y"])))
        else:
            normalized.add((int(coord[0]), int(coord[1])))
    return normalized


def validate_coordinate(coord: Coord, width: int, height: int) -> bool:
    return 0 <= coord[0] < width and 0 <= coord[1] < height


def _base_congestion(x: int, y: int, width: int, height: int) -> float:
    dispatch_pressure = max(0.0, 1.0 - math.dist((x, y), (2, height - 1)) / 14)
    center_pressure = max(0.0, 1.0 - math.dist((x, y), (width / 2, height / 2)) / 12)
    cross_aisle_pressure = 0.35 if y in {5, 9} else 0
    return round(min(1.0, 0.16 + dispatch_pressure * 0.36 + center_pressure * 0.28 + cross_aisle_pressure), 3)


def _is_shelf(x: int, y: int) -> bool:
    if y in {0, 1, 5, 9, 14, 15}:
        return False
    return x in {3, 4, 7, 8, 11, 12, 15, 16, 19, 20}


def _storage_type(x: int, y: int) -> str:
    if x in {3, 4} and 2 <= y <= 4:
        return "cold_storage"
    if x in {19, 20} and 10 <= y <= 13:
        return "hazmat"
    if x in {3, 4} and 10 <= y <= 13:
        return "oversized"
    return "shelf"


def generate_warehouse_layout(
    width: int = 24,
    height: int = 16,
    blocked: Iterable[dict | Coord] | None = None,
) -> dict:
    blocked_set = _as_coord_set(blocked)
    dispatch_set = {(x, y) for x in range(0, 6) for y in range(height - 2, height)}
    restricted_set = {(x, y) for x in range(width - 4, width) for y in range(0, 4)}
    cells: list[dict] = []
    obstacles: list[dict] = []

    for y in range(height):
        for x in range(width):
            coord = (x, y)
            cell_type = "aisle"
            walkable = True
            label = None

            if coord in dispatch_set:
                cell_type = "dispatch"
                label = "Dispatch"
            elif coord in restricted_set:
                cell_type = "restricted"
                walkable = False
                label = "Restricted"
            elif _is_shelf(x, y):
                cell_type = _storage_type(x, y)
                walkable = False
                label = cell_type.replace("_", " ").title()

            if coord in blocked_set and walkable:
                cell_type = "blocked"
                walkable = False
                label = "Blocked"
                obstacles.append({"x": x, "y": y})

            cells.append(
                {
                    "x": x,
                    "y": y,
                    "type": cell_type,
                    "walkable": walkable,
                    "congestion": _base_congestion(x, y, width, height),
                    "label": label,
                }
            )

    return {
        "width": width,
        "height": height,
        "cells": cells,
        "dispatch_zones": [{"x": x, "y": y} for x, y in sorted(dispatch_set)],
        "obstacles": obstacles,
        "legend": LEGEND,
    }


def cell_index(layout: dict) -> dict[Coord, dict]:
    return {(cell["x"], cell["y"]): cell for cell in layout["cells"]}


def list_storage_slots(layout: dict) -> list[dict]:
    return [
        cell
        for cell in layout["cells"]
        if cell["type"] in {"shelf", "cold_storage", "hazmat", "oversized"}
    ]


def list_walkable_cells(layout: dict) -> list[dict]:
    return [cell for cell in layout["cells"] if cell["walkable"]]


def nearest_dispatch(layout: dict, coord: Coord) -> Coord:
    dispatch = [(zone["x"], zone["y"]) for zone in layout["dispatch_zones"]]
    return min(dispatch, key=lambda point: manhattan(coord, point))


def manhattan(a: Coord, b: Coord) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def euclidean(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.dist(a, b)


def build_adjacency(layout: dict, congestion_weight: bool = True) -> dict[Coord, list[tuple[Coord, float]]]:
    cells = cell_index(layout)
    adjacency: dict[Coord, list[tuple[Coord, float]]] = {}
    for coord, cell in cells.items():
        if not cell["walkable"]:
            continue
        neighbors: list[tuple[Coord, float]] = []
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            neighbor = (coord[0] + dx, coord[1] + dy)
            neighbor_cell = cells.get(neighbor)
            if not neighbor_cell or not neighbor_cell["walkable"]:
                continue
            congestion_cost = 0
            if congestion_weight:
                congestion_cost = (cell["congestion"] + neighbor_cell["congestion"]) * 0.55
            neighbors.append((neighbor, 1.0 + congestion_cost))
        adjacency[coord] = neighbors
    return adjacency


def build_networkx_graph(layout: dict, congestion_weight: bool = True):
    if nx is None:
        return None
    graph = nx.Graph()
    for node, neighbors in build_adjacency(layout, congestion_weight).items():
        graph.add_node(node)
        for neighbor, cost in neighbors:
            graph.add_edge(node, neighbor, weight=cost)
    return graph


def nearest_walkable(layout: dict, coord: Coord) -> Coord:
    cells = cell_index(layout)
    if coord in cells and cells[coord]["walkable"]:
        return coord

    queue: deque[Coord] = deque([coord])
    seen = {coord}
    while queue:
        current = queue.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            candidate = (current[0] + dx, current[1] + dy)
            if candidate in seen:
                continue
            seen.add(candidate)
            candidate_cell = cells.get(candidate)
            if candidate_cell and candidate_cell["walkable"]:
                return candidate
            if candidate_cell:
                queue.append(candidate)

    raise ValueError(f"No walkable cell is reachable from {coord}")


def shortest_path(
    layout: dict,
    start: Coord,
    goal: Coord,
    algorithm: str = "astar",
    congestion_weight: bool = True,
) -> PathResult:
    start_node = nearest_walkable(layout, start)
    goal_node = nearest_walkable(layout, goal)
    if algorithm == "dijkstra":
        return _dijkstra(layout, start_node, goal_node, congestion_weight)
    return _astar(layout, start_node, goal_node, congestion_weight)


def _dijkstra(layout: dict, start: Coord, goal: Coord, congestion_weight: bool) -> PathResult:
    graph = build_networkx_graph(layout, congestion_weight)
    if graph is not None:
        try:
            path = list(nx.dijkstra_path(graph, start, goal, weight="weight"))
            return PathResult(path=path, cost=float(nx.path_weight(graph, path, weight="weight")), visited=0)
        except Exception:
            pass

    return _priority_search(layout, start, goal, congestion_weight, heuristic=lambda _: 0)


def _astar(layout: dict, start: Coord, goal: Coord, congestion_weight: bool) -> PathResult:
    graph = build_networkx_graph(layout, congestion_weight)
    if graph is not None:
        try:
            path = list(
                nx.astar_path(
                    graph,
                    start,
                    goal,
                    heuristic=lambda a, b: manhattan(a, b),
                    weight="weight",
                )
            )
            return PathResult(path=path, cost=float(nx.path_weight(graph, path, weight="weight")), visited=0)
        except Exception:
            pass

    return _priority_search(
        layout,
        start,
        goal,
        congestion_weight,
        heuristic=lambda node: manhattan(node, goal),
    )


def _priority_search(
    layout: dict,
    start: Coord,
    goal: Coord,
    congestion_weight: bool,
    heuristic,
) -> PathResult:
    adjacency = build_adjacency(layout, congestion_weight)
    frontier: list[tuple[float, Coord]] = [(0, start)]
    came_from: dict[Coord, Coord | None] = {start: None}
    cost_so_far: dict[Coord, float] = {start: 0.0}
    visited = 0

    while frontier:
        _, current = heapq.heappop(frontier)
        visited += 1
        if current == goal:
            break
        for neighbor, edge_cost in adjacency.get(current, []):
            new_cost = cost_so_far[current] + edge_cost
            if neighbor not in cost_so_far or new_cost < cost_so_far[neighbor]:
                cost_so_far[neighbor] = new_cost
                heapq.heappush(frontier, (new_cost + heuristic(neighbor), neighbor))
                came_from[neighbor] = current

    if goal not in came_from:
        raise ValueError(f"No route found between {start} and {goal}")

    path: list[Coord] = []
    current: Coord | None = goal
    while current is not None:
        path.append(current)
        current = came_from[current]
    path.reverse()
    return PathResult(path=path, cost=cost_so_far[goal], visited=visited)


def validate_blocked(layout: dict, blocked: Iterable[dict | Coord] | None) -> dict[str, list[dict]]:
    invalid: list[dict] = []
    accepted: list[dict] = []
    width = layout["width"]
    height = layout["height"]
    for coord in _as_coord_set(blocked):
        serialized = {"x": coord[0], "y": coord[1]}
        if validate_coordinate(coord, width, height):
            accepted.append(serialized)
        else:
            invalid.append(serialized)
    return {"accepted": accepted, "invalid": invalid}


def coords_to_dicts(path: Iterable[Coord]) -> list[dict[str, int]]:
    return [{"x": x, "y": y} for x, y in path]

