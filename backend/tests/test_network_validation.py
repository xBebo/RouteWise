"""Tests for network validation (backend/algorithms/network_validation.py)."""

from backend.algorithms.network_validation import (
    find_isolated_locations,
    find_unreachable_locations,
    get_reachable_locations,
    validate_network,
)


def test_isolated_location_detected():
    graph = {1: [(2, 1.0)], 2: [(1, 1.0)], 3: []}

    assert find_isolated_locations(graph) == [3]


def test_node_with_only_incoming_edge_is_not_isolated():
    graph = {1: [(2, 1.0)], 2: []}

    assert find_isolated_locations(graph) == []


def test_reachability_from_depot():
    graph = {1: [(2, 1.0)], 2: [(1, 1.0), (3, 2.0)], 3: [(2, 2.0)]}

    assert get_reachable_locations(graph, 1) == {1, 2, 3}
    assert find_unreachable_locations(graph, 1) == []


def test_one_way_road_blocks_reverse_direction():
    graph = {1: [(2, 1.0)], 2: []}  # one-way 1 -> 2

    assert get_reachable_locations(graph, 1) == {1, 2}
    assert get_reachable_locations(graph, 2) == {2}
    assert find_unreachable_locations(graph, 2) == [1]


def test_disconnected_components():
    graph = {
        1: [(2, 1.0)],
        2: [(1, 1.0)],
        3: [(4, 1.0)],
        4: [(3, 1.0)],
    }

    result = validate_network(graph, 1)

    assert sorted(result["unreachable"]) == [3, 4]
    assert result["isolated"] == []
    assert result["reachable_count"] == 2
    assert result["is_fully_connected"] is False


def test_fully_connected_network():
    graph = {1: [(2, 1.0)], 2: [(1, 1.0)]}

    assert validate_network(graph, 1) == {
        "isolated": [],
        "unreachable": [],
        "reachable_count": 2,
        "is_fully_connected": True,
    }


def test_empty_graph():
    assert find_isolated_locations({}) == []
    assert get_reachable_locations({}, 1) == set()
    assert find_unreachable_locations({}, 1) == []
    assert validate_network({}, 1) == {
        "isolated": [],
        "unreachable": [],
        "reachable_count": 0,
        "is_fully_connected": False,
    }


def test_missing_depot():
    graph = {1: [(2, 1.0)], 2: [(1, 1.0)]}

    assert get_reachable_locations(graph, 99) == set()
    assert sorted(find_unreachable_locations(graph, 99)) == [1, 2]

    result = validate_network(graph, 99)
    assert result["reachable_count"] == 0
    assert result["is_fully_connected"] is False
