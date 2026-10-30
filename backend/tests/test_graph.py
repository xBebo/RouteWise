"""Tests for the graph representation (backend/algorithms/graph.py)."""

from backend.algorithms.graph import build_graph, get_neighbors, get_nodes


def loc(location_id: int) -> dict:
    return {"id": location_id, "name": f"Location {location_id}"}


def road(road_id, start, end, distance=5.0, one_way=False, closed=False) -> dict:
    return {
        "id": road_id,
        "from_id": start,
        "to_id": end,
        "distance_km": distance,
        "is_one_way": one_way,
        "is_closed": closed,
    }


def test_two_way_road_adds_both_directions():
    graph = build_graph([loc(1), loc(2)], [road(1, 1, 2, 7.5)])

    assert graph[1] == [(2, 7.5)]
    assert graph[2] == [(1, 7.5)]


def test_one_way_road_adds_single_direction():
    graph = build_graph([loc(1), loc(2)], [road(1, 1, 2, 3.0, one_way=True)])

    assert graph[1] == [(2, 3.0)]
    assert graph[2] == []


def test_closed_road_is_excluded():
    graph = build_graph([loc(1), loc(2)], [road(1, 1, 2, closed=True)])

    assert graph == {1: [], 2: []}


def test_empty_input_returns_empty_graph():
    assert build_graph([], []) == {}


def test_isolated_location_is_still_a_key():
    graph = build_graph([loc(1), loc(2), loc(3)], [road(1, 1, 2)])

    assert 3 in graph
    assert graph[3] == []


def test_road_with_unknown_location_is_skipped():
    graph = build_graph(
        [loc(1), loc(2)],
        [road(1, 1, 99), road(2, 98, 2), road(3, 1, 2, 4.0)],
    )

    assert graph == {1: [(2, 4.0)], 2: [(1, 4.0)]}


def test_invalid_distances_are_skipped():
    roads = [
        road(1, 1, 2, -1),
        road(2, 1, 2, "far"),
        road(3, 1, 2, None),
        road(4, 1, 2, float("nan")),
        road(5, 1, 2, True),
    ]

    assert build_graph([loc(1), loc(2)], roads) == {1: [], 2: []}


def test_overflowing_distances_do_not_interrupt_graph_construction():
    roads = [
        road(1, 1, 2, 10**1000),
        road(2, 1, 2, -(10**1000)),
        road(3, 1, 2, 4.0),
    ]

    assert build_graph([loc(1), loc(2)], roads) == {
        1: [(2, 4.0)],
        2: [(1, 4.0)],
    }


def test_integer_flags_from_database_are_supported():
    # SQLite stores booleans as 0/1.
    roads = [road(1, 1, 2, 2, one_way=1), road(2, 2, 3, 4, closed=1)]

    graph = build_graph([loc(1), loc(2), loc(3)], roads)

    assert graph == {1: [(2, 2.0)], 2: [], 3: []}


def test_get_neighbors_returns_edges():
    graph = build_graph([loc(1), loc(2), loc(3)], [road(1, 1, 2, 1), road(2, 1, 3, 2)])

    assert sorted(get_neighbors(graph, 1)) == [(2, 1.0), (3, 2.0)]


def test_get_neighbors_on_missing_node_returns_empty_list():
    graph = build_graph([loc(1)], [])

    assert get_neighbors(graph, 42) == []
    assert get_neighbors({}, 1) == []


def test_get_nodes_returns_all_locations():
    graph = build_graph([loc(1), loc(2), loc(3)], [])

    assert sorted(get_nodes(graph)) == [1, 2, 3]
