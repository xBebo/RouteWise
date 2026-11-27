"""Tests for heap-based Dijkstra (backend/algorithms/dijkstra.py)."""

from backend.algorithms.dijkstra import dijkstra, reconstruct_path, shortest_path
from backend.algorithms.graph import build_graph


def _loc(location_id: int, code: str | None = None) -> dict:
    return {
        "id": location_id,
        "code": code or f"LOC_{location_id:02d}",
        "name": f"Location {location_id}",
    }


def _road(
    from_id: int,
    to_id: int,
    distance_km: float,
    *,
    one_way: int | bool = 0,
    closed: int | bool = 0,
) -> dict:
    return {
        "from_id": from_id,
        "to_id": to_id,
        "distance_km": distance_km,
        "is_one_way": one_way,
        "is_closed": closed,
    }


def _worked_network(*, close_primary: bool = False):
    locations = [_loc(1, "DEPOT"), _loc(2, "HUB_A"), _loc(3, "HUB_B"), _loc(4, "CUST_1")]
    roads = [
        _road(1, 2, 4.0),
        _road(2, 4, 6.0, closed=1 if close_primary else 0),
        _road(1, 3, 5.0),
        _road(3, 4, 7.0),
        _road(1, 4, 15.0),
    ]
    return build_graph(locations, roads)


def test_10km_worked_example():
    graph = _worked_network(close_primary=False)

    result = shortest_path(graph, 1, 4)

    assert result == {
        "found": True,
        "total_distance_km": 10.0,
        "path": [1, 2, 4],
    }


def test_12km_closure_detour():
    graph = _worked_network(close_primary=True)

    result = shortest_path(graph, 1, 4)

    assert result == {
        "found": True,
        "total_distance_km": 12.0,
        "path": [1, 3, 4],
    }


def test_same_origin_and_destination():
    graph = build_graph([_loc(1), _loc(2)], [_road(1, 2, 3.5)])

    result = shortest_path(graph, 1, 1)

    assert result == {
        "found": True,
        "total_distance_km": 0.0,
        "path": [1],
    }


def test_unreachable_and_missing_nodes_never_raise():
    graph = build_graph([_loc(1), _loc(2), _loc(3)], [_road(1, 2, 5.0)])

    assert shortest_path(graph, 1, 3) == {
        "found": False,
        "total_distance_km": None,
        "path": [],
    }
    assert shortest_path(graph, 99, 1) == {
        "found": False,
        "total_distance_km": None,
        "path": [],
    }
    assert shortest_path(graph, 1, 99) == {
        "found": False,
        "total_distance_km": None,
        "path": [],
    }
    assert shortest_path(graph, 99, 99) == {
        "found": False,
        "total_distance_km": None,
        "path": [],
    }
    assert shortest_path({}, 1, 2) == {
        "found": False,
        "total_distance_km": None,
        "path": [],
    }


def test_one_way_restriction_forward_and_reverse():
    locations = [_loc(1), _loc(2), _loc(3)]
    roads = [
        _road(1, 2, 2.0, one_way=1),
        _road(2, 3, 4.0, one_way=1),
        _road(3, 1, 5.0, one_way=1),
    ]
    graph = build_graph(locations, roads)

    forward = shortest_path(graph, 1, 2)
    reverse = shortest_path(graph, 2, 1)

    assert forward == {"found": True, "total_distance_km": 2.0, "path": [1, 2]}
    assert reverse == {"found": True, "total_distance_km": 9.0, "path": [2, 3, 1]}

    strictly_one_way = build_graph([_loc(1), _loc(2)], [_road(1, 2, 2.0, one_way=1)])
    assert shortest_path(strictly_one_way, 2, 1) == {
        "found": False,
        "total_distance_km": None,
        "path": [],
    }


def test_tie_breaking_by_location_code_and_id_fallback():
    locations = [_loc(1, "DEPOT"), _loc(2, "Z_NODE"), _loc(3, "A_NODE"), _loc(4, "TARGET")]
    roads = [
        _road(1, 2, 5.0),
        _road(2, 4, 5.0),
        _road(1, 3, 5.0),
        _road(3, 4, 5.0),
    ]
    graph = build_graph(locations, roads)
    codes = {loc["id"]: loc["code"] for loc in locations}

    by_code = shortest_path(graph, 1, 4, codes=codes)
    assert by_code == {"found": True, "total_distance_km": 10.0, "path": [1, 3, 4]}

    by_id = shortest_path(graph, 1, 4)
    assert by_id == {"found": True, "total_distance_km": 10.0, "path": [1, 2, 4]}


def test_tie_breaking_when_intermediate_legs_have_different_splits():
    locations = [_loc(1, "DEPOT"), _loc(2, "Z_HUB"), _loc(3, "A_HUB"), _loc(4, "TARGET")]
    roads = [
        _road(1, 2, 3.0),
        _road(2, 4, 7.0),
        _road(1, 3, 7.0),
        _road(3, 4, 3.0),
    ]
    graph = build_graph(locations, roads)
    codes = {loc["id"]: loc["code"] for loc in locations}

    result = shortest_path(graph, 1, 4, codes=codes)
    assert result == {"found": True, "total_distance_km": 10.0, "path": [1, 3, 4]}


def test_single_source_dijkstra_returns_distances_and_predecessors():
    graph = _worked_network(close_primary=False)

    distances, predecessors = dijkstra(graph, 1)

    assert distances == {1: 0.0, 2: 4.0, 3: 5.0, 4: 10.0}
    assert reconstruct_path(predecessors, 1, 4) == [1, 2, 4]
    assert reconstruct_path(predecessors, 1, 99) == []


def test_preserves_very_small_positive_distance():
    graph = build_graph(
        [_loc(1, "DEPOT"), _loc(2, "CUST_1")],
        [_road(1, 2, 1e-11, one_way=1)],
    )

    result = shortest_path(graph, 1, 2)

    assert result["found"] is True
    assert result["path"] == [1, 2]
    assert result["total_distance_km"] == 1e-11
    assert result["total_distance_km"] > 0.0


def test_target_limited_dijkstra_returns_only_settled_nodes():
    locations = [_loc(1, "SRC"), _loc(2, "TARGET"), _loc(3, "FAR"), _loc(4, "BEYOND")]
    roads = [
        _road(1, 2, 2.0, one_way=1),
        _road(1, 3, 5.0, one_way=1),
        _road(3, 4, 1.0, one_way=1),
    ]
    graph = build_graph(locations, roads)

    distances, predecessors = dijkstra(graph, 1, target=2)

    assert distances == {1: 0.0, 2: 2.0}
    assert predecessors == {1: None, 2: 1}
    assert 3 not in distances
    assert 3 not in predecessors
    assert set(distances.keys()) == set(predecessors.keys())

    # Full single-source search remains unchanged when target is omitted.
    full_distances, full_predecessors = dijkstra(graph, 1)
    assert full_distances == {1: 0.0, 2: 2.0, 3: 5.0, 4: 6.0}
    assert full_predecessors == {1: None, 2: 1, 3: 1, 4: 3}

    # shortest_path continues to work with target-limited results.
    assert shortest_path(graph, 1, 2) == {
        "found": True,
        "total_distance_km": 2.0,
        "path": [1, 2],
    }
