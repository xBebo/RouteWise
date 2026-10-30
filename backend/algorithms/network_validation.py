"""Network validation: isolation and reachability checks on the road graph.

Pure Python (standard library only). Works on the adjacency list produced
by ``graph.build_graph``.
"""

from collections import deque

from .graph import Graph, get_neighbors, get_nodes


def find_isolated_locations(graph: Graph) -> list[int]:
    """Return locations with no outgoing AND no incoming edges."""
    has_incoming: set[int] = set()
    for node in get_nodes(graph):
        for destination, _ in get_neighbors(graph, node):
            has_incoming.add(destination)

    return [
        node
        for node in get_nodes(graph)
        if not get_neighbors(graph, node) and node not in has_incoming
    ]


def get_reachable_locations(graph: Graph, depot_id: int) -> set[int]:
    """Return all locations reachable from the depot (BFS, directed edges).

    Includes the depot itself. Returns an empty set if the depot is missing.
    """
    if depot_id not in graph:
        return set()

    visited = {depot_id}
    queue = deque([depot_id])
    while queue:
        node = queue.popleft()
        for destination, _ in get_neighbors(graph, node):
            if destination not in visited:
                visited.add(destination)
                queue.append(destination)
    return visited


def find_unreachable_locations(graph: Graph, depot_id: int) -> list[int]:
    """Return all locations not reachable from the depot.

    If the depot is missing, every location is unreachable.
    """
    reachable = get_reachable_locations(graph, depot_id)
    return [node for node in get_nodes(graph) if node not in reachable]


def validate_network(graph: Graph, depot_id: int) -> dict:
    """Summarize network health relative to the depot.

    Returns ``{"isolated", "unreachable", "reachable_count",
    "is_fully_connected"}``. ``is_fully_connected`` is True only when the
    depot exists and every location is reachable from it (so it is False
    for an empty graph or a missing depot).
    """
    reachable = get_reachable_locations(graph, depot_id)
    unreachable = [node for node in get_nodes(graph) if node not in reachable]

    return {
        "isolated": find_isolated_locations(graph),
        "unreachable": unreachable,
        "reachable_count": len(reachable),
        "is_fully_connected": bool(reachable) and not unreachable,
    }
