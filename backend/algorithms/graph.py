"""Graph representation of the delivery road network.

Pure Python (standard library only). The graph is an adjacency list:

    graph[location_id] = [(destination_id, distance_km), ...]

Every location is a key, even if it has no outgoing roads.
"""

import math
from typing import Any

# Input field names (pending confirmation of the real data format).
LOCATION_ID = "id"
ROAD_FROM = "from_id"
ROAD_TO = "to_id"
ROAD_DISTANCE = "distance_km"
ROAD_ONE_WAY = "is_one_way"
ROAD_CLOSED = "is_closed"

Graph = dict[int, list[tuple[int, float]]]


def _valid_distance(value: Any) -> float | None:
    """Return the distance as a float, or None if it is not usable.

    Valid: a finite, non-negative int/float representable as a float
    (bools are rejected).
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        distance = float(value)
    except OverflowError:
        return None
    if not math.isfinite(distance) or distance < 0:
        return None
    return distance


def build_graph(locations: list[dict], roads: list[dict]) -> Graph:
    """Build a directed adjacency list from locations and roads.

    Rules:
    - Every location id becomes a key (with an empty list if unconnected).
    - Two-way road: edges in both directions.
    - One-way road: a single edge from ``from_id`` to ``to_id``.
    - Closed roads are skipped.
    - Roads are silently skipped (never raise) when they:
      reference an unknown location id, are missing fields, or have an
      invalid distance (non-numeric, bool, NaN/inf, or negative).
      A distance of 0 is accepted.
    - Locations without an ``id`` field are skipped.
    """
    graph: Graph = {}

    for location in locations or []:
        location_id = location.get(LOCATION_ID)
        if location_id is not None:
            graph.setdefault(location_id, [])

    for road in roads or []:
        if road.get(ROAD_CLOSED, False):
            continue

        start = road.get(ROAD_FROM)
        end = road.get(ROAD_TO)
        if start not in graph or end not in graph:
            continue

        distance = _valid_distance(road.get(ROAD_DISTANCE))
        if distance is None:
            continue

        graph[start].append((end, distance))
        if not road.get(ROAD_ONE_WAY, False):
            graph[end].append((start, distance))

    return graph


def get_neighbors(graph: Graph, node_id: int) -> list[tuple[int, float]]:
    """Return outgoing ``(destination_id, distance_km)`` pairs, or [] if missing."""
    return list(graph.get(node_id, []))


def get_nodes(graph: Graph) -> list[int]:
    """Return all location ids in the graph."""
    return list(graph.keys())
