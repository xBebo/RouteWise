"""Heap-based Dijkstra shortest-path algorithm for the road network.

Pure Python (standard library only). Operates on the directed adjacency list
produced by ``backend.algorithms.graph.build_graph``.
"""

import heapq
from typing import Any

from .graph import Graph, get_neighbors


def location_sort_key(
    location_id: int,
    codes: dict[int, str] | None = None,
) -> tuple[int, str | int]:
    """Return a deterministic tie-breaking key for a location id.

    When ``codes`` is provided and contains ``location_id``, locations are
    ordered lexicographically by their string code (e.g. ``"CUST_01"`` <
    ``"CUST_02"``). When ``codes`` is ``None`` or omits ``location_id``,
    sorting falls back to the numeric ``location_id`` in a separate tuple
    bucket so string codes and integer ids are never compared directly.
    """
    if codes is not None and location_id in codes:
        return (0, str(codes[location_id]))
    return (1, location_id)


def dijkstra(
    graph: Graph,
    source: int,
    codes: dict[int, str] | None = None,
    target: int | None = None,
) -> tuple[dict[int, float], dict[int, int | None]]:
    """Compute shortest paths from ``source`` using a binary min-heap.

    Runs in O((V + E) log V) time for non-negative road distances.
    Equal-distance candidates are broken using ``location_sort_key`` (lower
    location code first, defaulting to location id when ``codes`` is omitted).

    If ``target`` is provided, search stops early as soon as ``target`` is
    settled and only settled nodes are returned in ``distances`` and
    ``predecessors`` (tentative distances for unsettled nodes are excluded).
    When ``target`` is ``None``, a full single-source search is run.
    Returns ``(distances, predecessors)``; both dicts are empty if ``source``
    is not present in ``graph``.
    """
    if source not in graph:
        return {}, {}

    distances: dict[int, float] = {source: 0.0}
    predecessors: dict[int, int | None] = {source: None}
    settled: set[int] = set()
    heap: list[tuple[float, tuple[int, str | int], int]] = [
        (0.0, location_sort_key(source, codes), source)
    ]

    while heap:
        current_dist, _, current_node = heapq.heappop(heap)
        if current_node in settled:
            continue

        settled.add(current_node)
        if target is not None and current_node == target:
            break

        for neighbor, weight in get_neighbors(graph, current_node):
            if neighbor in settled:
                continue

            new_dist = current_dist + weight
            prev_dist = distances.get(neighbor)

            if prev_dist is None or new_dist < prev_dist:
                distances[neighbor] = new_dist
                predecessors[neighbor] = current_node
                heapq.heappush(
                    heap,
                    (new_dist, location_sort_key(neighbor, codes), neighbor),
                )
            elif new_dist == prev_dist:
                existing_pred = predecessors.get(neighbor)
                if existing_pred is not None and (
                    location_sort_key(current_node, codes)
                    < location_sort_key(existing_pred, codes)
                ):
                    predecessors[neighbor] = current_node

    if target is not None:
        distances = {
            node: dist for node, dist in distances.items() if node in settled
        }
        predecessors = {
            node: pred for node, pred in predecessors.items() if node in settled
        }

    return distances, predecessors


def reconstruct_path(
    predecessors: dict[int, int | None],
    source: int,
    target: int,
) -> list[int]:
    """Reconstruct the node id path from ``source`` to ``target``.

    Returns an empty list if ``target`` has no valid chain back to ``source``.
    """
    if source not in predecessors or target not in predecessors:
        return []

    path: list[int] = []
    seen: set[int] = set()
    current: int | None = target

    while current is not None:
        if current in seen:
            return []
        seen.add(current)
        path.append(current)
        if current == source:
            path.reverse()
            return path
        current = predecessors.get(current)

    return []


def shortest_path(
    graph: Graph,
    source: int,
    target: int,
    codes: dict[int, str] | None = None,
) -> dict[str, Any]:
    """Find the shortest directed path from ``source`` to ``target``.

    Returns a dict with:
    - ``found`` (bool): True if ``target`` is reachable from ``source``.
    - ``total_distance_km`` (float | None): Total path distance, or None.
    - ``path`` (list[int]): Ordered location ids from ``source`` to ``target``,
      or ``[]`` when not found.

    Tie-breaking between equal-distance paths prefers the lower location code
    via ``codes`` (defaulting to location id when ``codes`` is None).
    Missing nodes or unreachable targets never raise an exception.
    """
    if source not in graph or target not in graph:
        return {
            "found": False,
            "total_distance_km": None,
            "path": [],
        }

    if source == target:
        return {
            "found": True,
            "total_distance_km": 0.0,
            "path": [source],
        }

    distances, predecessors = dijkstra(graph, source, codes=codes, target=target)
    if target not in distances:
        return {
            "found": False,
            "total_distance_km": None,
            "path": [],
        }

    path = reconstruct_path(predecessors, source, target)
    if not path:
        return {
            "found": False,
            "total_distance_km": None,
            "path": [],
        }

    return {
        "found": True,
        "total_distance_km": distances[target],
        "path": path,
    }
