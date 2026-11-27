"""Nearest-neighbor multi-stop heuristic route planner.

Pure Python (standard library only). Reuses Dijkstra shortest paths from
``backend.algorithms.dijkstra`` to plan 1-8 delivery stops from a depot.
"""

from collections.abc import Sequence
from typing import Any

from .dijkstra import dijkstra, location_sort_key, reconstruct_path, shortest_path
from .graph import Graph

MIN_STOPS = 1
MAX_STOPS = 8


def _normalize_stops(depot: int, stops: Sequence[int]) -> list[int]:
    """De-duplicate stops keeping first occurrence and exclude the depot.

    Raises ``ValueError`` if fewer than 1 or more than 8 unique delivery stops
    remain.
    """
    unique_stops: list[int] = []
    seen: set[int] = set()

    for stop_id in stops:
        if stop_id == depot or stop_id in seen:
            continue
        seen.add(stop_id)
        unique_stops.append(stop_id)

    if len(unique_stops) < MIN_STOPS:
        raise ValueError(
            f"At least {MIN_STOPS} delivery stop (excluding the depot) is required."
        )
    if len(unique_stops) > MAX_STOPS:
        raise ValueError(
            f"At most {MAX_STOPS} unique stops are supported (got {len(unique_stops)})."
        )

    return unique_stops


def plan_route(
    graph: Graph,
    depot: int,
    stops: Sequence[int],
    return_to_depot: bool = False,
    codes: dict[int, str] | None = None,
) -> dict[str, Any]:
    """Plan a multi-stop route using the nearest-neighbor heuristic.

    Validation policy: duplicate stops (preserving first occurrence) and stops
    equal to ``depot`` are removed first, and a ``ValueError`` is raised if the
    resulting stop count is outside 1..8.

    Starting at ``depot``, each step selects the unvisited stop with the
    smallest Dijkstra shortest distance from the current location. Ties are
    broken by ``codes`` (lower code first, defaulting to location id when
    ``codes`` is ``None``). Unreachable stops are skipped and reported in
    ``unreachable_stops`` without raising.

    Returns a dict with:
    - ``ordered_stops`` (list[int]): Visited stops in traversal order.
    - ``legs`` (list[dict]): Each leg has ``from_id``, ``to_id``,
      ``distance_km``, and ``path``.
    - ``total_distance_km`` (float): Sum of traversed leg distances.
    - ``unreachable_stops`` (list[int]): Stops that could not be reached.
    - ``returned_to_depot`` (bool): True only when ``return_to_depot`` was
      requested and the final return leg succeeded.
    - ``method`` (str): Always ``"heuristic"``.
    - ``warnings`` (list[str]): Human-readable notes for skipped stops or
      unreachable return legs.
    """
    remaining = _normalize_stops(depot, stops)
    ordered_stops: list[int] = []
    legs: list[dict[str, Any]] = []
    unreachable_stops: list[int] = []
    warnings: list[str] = []
    total_distance = 0.0
    current = depot

    while remaining:
        distances, predecessors = dijkstra(graph, current, codes=codes)
        reachable = [stop_id for stop_id in remaining if stop_id in distances]

        if not reachable:
            unreachable_stops.extend(remaining)
            warnings.append(f"Unreachable stop(s) skipped: {remaining}.")
            break

        next_stop = min(
            reachable,
            key=lambda stop_id: (
                distances[stop_id],
                location_sort_key(stop_id, codes),
            ),
        )
        leg_path = reconstruct_path(predecessors, current, next_stop)
        leg_distance = distances[next_stop]

        legs.append(
            {
                "from_id": current,
                "to_id": next_stop,
                "distance_km": leg_distance,
                "path": leg_path,
            }
        )
        ordered_stops.append(next_stop)
        total_distance += leg_distance
        current = next_stop
        remaining.remove(next_stop)

    returned_to_depot = False
    if return_to_depot:
        if not ordered_stops:
            warnings.append(
                "Cannot return to depot because no stops were reachable."
            )
        else:
            return_result = shortest_path(graph, current, depot, codes=codes)
            if return_result["found"]:
                return_distance = float(return_result["total_distance_km"])
                legs.append(
                    {
                        "from_id": current,
                        "to_id": depot,
                        "distance_km": return_distance,
                        "path": return_result["path"],
                    }
                )
                total_distance += return_distance
                returned_to_depot = True
            else:
                warnings.append(
                    f"Return leg from stop {current} to depot {depot} is unreachable."
                )

    return {
        "ordered_stops": ordered_stops,
        "legs": legs,
        "total_distance_km": total_distance,
        "unreachable_stops": unreachable_stops,
        "returned_to_depot": returned_to_depot,
        "method": "heuristic",
        "warnings": warnings,
    }
