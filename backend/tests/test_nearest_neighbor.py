"""Tests for nearest-neighbor multi-stop planner (backend/algorithms/nearest_neighbor.py)."""

import pytest

from backend.algorithms.graph import build_graph
from backend.algorithms.nearest_neighbor import plan_route


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


def test_worked_stop_order_and_heuristic_label():
    # Depot 1 -> closest stop is 3 (2 km), then from 3 closest is 2 (3 km),
    # then from 2 closest is 4 (4 km), total = 9 km.
    locations = [_loc(1, "DEPOT"), _loc(2, "CUST_A"), _loc(3, "CUST_B"), _loc(4, "CUST_C")]
    roads = [
        _road(1, 2, 6.0),
        _road(1, 3, 2.0),
        _road(1, 4, 10.0),
        _road(3, 2, 3.0),
        _road(3, 4, 8.0),
        _road(2, 4, 4.0),
    ]
    graph = build_graph(locations, roads)

    result = plan_route(graph, depot=1, stops=[2, 3, 4], return_to_depot=False)

    assert result["method"] == "heuristic"
    assert result["ordered_stops"] == [3, 2, 4]
    assert result["total_distance_km"] == 9.0
    assert result["unreachable_stops"] == []
    assert result["returned_to_depot"] is False
    assert result["legs"] == [
        {"from_id": 1, "to_id": 3, "distance_km": 2.0, "path": [1, 3]},
        {"from_id": 3, "to_id": 2, "distance_km": 3.0, "path": [3, 2]},
        {"from_id": 2, "to_id": 4, "distance_km": 4.0, "path": [2, 4]},
    ]


def test_return_to_depot_true_and_false():
    locations = [_loc(1), _loc(2), _loc(3)]
    roads = [
        _road(1, 2, 2.0),
        _road(2, 3, 3.0),
        _road(3, 1, 4.0),
    ]
    graph = build_graph(locations, roads)

    without_return = plan_route(graph, depot=1, stops=[2, 3], return_to_depot=False)
    assert without_return["returned_to_depot"] is False
    assert without_return["total_distance_km"] == 5.0
    assert len(without_return["legs"]) == 2

    with_return = plan_route(graph, depot=1, stops=[2, 3], return_to_depot=True)
    assert with_return["returned_to_depot"] is True
    assert with_return["total_distance_km"] == 9.0
    assert len(with_return["legs"]) == 3
    assert with_return["legs"][-1] == {
        "from_id": 3,
        "to_id": 1,
        "distance_km": 4.0,
        "path": [3, 1],
    }


def test_return_to_depot_unreachable_reported_clearly():
    locations = [_loc(1), _loc(2)]
    roads = [_road(1, 2, 3.5, one_way=1)]
    graph = build_graph(locations, roads)

    result = plan_route(graph, depot=1, stops=[2], return_to_depot=True)

    assert result["ordered_stops"] == [2]
    assert result["total_distance_km"] == 3.5
    assert result["returned_to_depot"] is False
    assert len(result["legs"]) == 1
    assert any("return" in msg.lower() for msg in result["warnings"])


def test_unreachable_stop_skipped_and_reported():
    locations = [_loc(1), _loc(2), _loc(3), _loc(4)]
    roads = [_road(1, 2, 3.0), _road(2, 3, 4.0)]  # 4 is isolated
    graph = build_graph(locations, roads)

    result = plan_route(graph, depot=1, stops=[4, 3, 2], return_to_depot=True)

    assert result["method"] == "heuristic"
    assert result["ordered_stops"] == [2, 3]
    assert result["unreachable_stops"] == [4]
    assert result["returned_to_depot"] is True
    assert result["total_distance_km"] == 14.0  # 1->2 (3) + 2->3 (4) + 3->2->1 (7)


def test_all_stops_unreachable():
    graph = build_graph([_loc(1), _loc(2), _loc(3)], [])

    result = plan_route(graph, depot=1, stops=[2, 3], return_to_depot=True)

    assert result["ordered_stops"] == []
    assert result["legs"] == []
    assert result["total_distance_km"] == 0.0
    assert result["unreachable_stops"] == [2, 3]
    assert result["returned_to_depot"] is False
    assert result["method"] == "heuristic"


def test_tie_breaking_by_location_code():
    locations = [_loc(1, "DEPOT"), _loc(2, "CUST_Z"), _loc(3, "CUST_A")]
    roads = [
        _road(1, 2, 5.0),
        _road(1, 3, 5.0),
        _road(2, 3, 6.0),
    ]
    graph = build_graph(locations, roads)
    codes = {loc["id"]: loc["code"] for loc in locations}

    by_code = plan_route(graph, depot=1, stops=[2, 3], codes=codes)
    assert by_code["ordered_stops"] == [3, 2]

    by_id = plan_route(graph, depot=1, stops=[2, 3])
    assert by_id["ordered_stops"] == [2, 3]


def test_one_stop_and_eight_stops_supported():
    locations = [_loc(i) for i in range(1, 10)]  # 1 = depot, 2..9 = 8 stops
    roads = [_road(i, i + 1, 1.5) for i in range(1, 9)]
    graph = build_graph(locations, roads)

    one_stop = plan_route(graph, depot=1, stops=[2])
    assert one_stop["ordered_stops"] == [2]
    assert one_stop["total_distance_km"] == 1.5
    assert one_stop["method"] == "heuristic"

    eight_stops = plan_route(graph, depot=1, stops=[9, 8, 7, 6, 5, 4, 3, 2])
    assert eight_stops["ordered_stops"] == [2, 3, 4, 5, 6, 7, 8, 9]
    assert eight_stops["total_distance_km"] == 12.0
    assert eight_stops["method"] == "heuristic"


def test_invalid_stop_counts_rejected():
    locations = [_loc(i) for i in range(1, 12)]
    roads = [_road(i, i + 1, 1.0) for i in range(1, 11)]
    graph = build_graph(locations, roads)

    with pytest.raises(ValueError):
        plan_route(graph, depot=1, stops=[])

    with pytest.raises(ValueError):
        plan_route(graph, depot=1, stops=[2, 3, 4, 5, 6, 7, 8, 9, 10])


def test_duplicate_stops_and_stop_equal_to_depot():
    locations = [_loc(i) for i in range(1, 10)]
    roads = [_road(i, i + 1, 2.0) for i in range(1, 9)]
    graph = build_graph(locations, roads)

    # Duplicates and depot stop are stripped cleanly without exceeding 8 stops.
    result = plan_route(graph, depot=1, stops=[1, 2, 2, 3, 1, 3])
    assert result["ordered_stops"] == [2, 3]
    assert result["total_distance_km"] == 4.0

    # 9 items with a duplicate yields 8 unique stops (valid).
    eight_unique = plan_route(graph, depot=1, stops=[2, 2, 3, 4, 5, 6, 7, 8, 9])
    assert len(eight_unique["ordered_stops"]) == 8

    # Only the depot in stops leaves 0 delivery stops -> rejected clearly.
    with pytest.raises(ValueError):
        plan_route(graph, depot=1, stops=[1, 1])
