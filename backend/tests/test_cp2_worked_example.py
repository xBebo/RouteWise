"""Integration tests and reusable catalog fixture for CP2-04 (Issue #14)."""

import pytest

from backend.algorithms.graph import build_graph, get_neighbors
from backend.algorithms.network_validation import validate_network
from backend.app import create_app


@pytest.fixture
def db_path(tmp_path):
    """Temporary SQLite database path so developer DB is never touched."""
    return tmp_path / "cp2_worked_example.db"


@pytest.fixture
def client(db_path):
    """Flask test client bound to the temporary database."""
    app = create_app({"TESTING": True, "DB_PATH": db_path})
    with app.test_client() as test_client:
        yield test_client


@pytest.fixture
def worked_example_catalog(client):
    """Reusable catalog fixture for the CP2 worked example + edge cases.

    Worked example topology:
      D (DEPOT) --4-- A --5-- C --2-- E
      |               |       |
      2               1       9
      |               |       |
      +-------------- B ------+   (and B --10-- E)

    Extra edge-case nodes:
      - ONEWAY_SRC -> ONEWAY_DST (is_one_way=True, distance=3.0)
      - ISOLATED (no connected roads)
    """
    nodes_spec = [
        ("D", "Depot D", "DEPOT", 100.0, 500.0),
        ("A", "Node A", "CUSTOMER", 300.0, 300.0),
        ("B", "Node B", "CUSTOMER", 300.0, 700.0),
        ("C", "Node C", "CUSTOMER", 600.0, 300.0),
        ("E", "Node E", "CUSTOMER", 900.0, 500.0),
        ("ONEWAY_SRC", "One-Way Start", "HUB", 100.0, 100.0),
        ("ONEWAY_DST", "One-Way End", "CUSTOMER", 200.0, 100.0),
        ("ISOLATED", "Unreachable Customer", "CUSTOMER", 950.0, 950.0),
    ]

    locations = {}
    for code, name, kind, x, y in nodes_spec:
        resp = client.post(
            "/api/locations",
            json={"code": code, "name": name, "kind": kind, "x": x, "y": y},
        )
        assert resp.status_code == 201
        locations[code] = resp.get_json()["location"]

    roads_spec = [
        ("D", "A", 4.0, False, False),
        ("D", "B", 2.0, False, False),
        ("B", "A", 1.0, False, False),
        ("A", "C", 5.0, False, False),
        ("B", "C", 9.0, False, False),
        ("B", "E", 10.0, False, False),
        ("C", "E", 2.0, False, False),
        ("D", "ONEWAY_SRC", 2.0, False, False),
        ("ONEWAY_SRC", "ONEWAY_DST", 3.0, True, False),
    ]

    roads = {}
    for u_code, v_code, dist, one_way, closed in roads_spec:
        resp = client.post(
            "/api/roads",
            json={
                "from_id": locations[u_code]["id"],
                "to_id": locations[v_code]["id"],
                "distance_km": dist,
                "is_one_way": one_way,
                "is_closed": closed,
            },
        )
        assert resp.status_code == 201
        roads[f"{u_code}-{v_code}"] = resp.get_json()["road"]

    return {"locations": locations, "roads": roads, "client": client}


def test_worked_example_topology_and_weights(worked_example_catalog):
    """Verify the worked example nodes and road weights load accurately into the graph."""
    client = worked_example_catalog["client"]
    locs = worked_example_catalog["locations"]

    all_locs = client.get("/api/locations").get_json()["locations"]
    all_roads = client.get("/api/roads").get_json()["roads"]
    graph = build_graph(all_locs, all_roads)

    d_neighbors = dict(get_neighbors(graph, locs["D"]["id"]))
    assert d_neighbors[locs["A"]["id"]] == 4.0
    assert d_neighbors[locs["B"]["id"]] == 2.0

    b_neighbors = dict(get_neighbors(graph, locs["B"]["id"]))
    assert b_neighbors[locs["A"]["id"]] == 1.0
    assert b_neighbors[locs["C"]["id"]] == 9.0
    assert b_neighbors[locs["E"]["id"]] == 10.0

    c_neighbors = dict(get_neighbors(graph, locs["C"]["id"]))
    assert c_neighbors[locs["A"]["id"]] == 5.0
    assert c_neighbors[locs["E"]["id"]] == 2.0


def test_worked_example_edge_cases_and_closure(worked_example_catalog):
    """Verify one-way rules, unreachable nodes, and A-C closure for the 12 km detour."""
    client = worked_example_catalog["client"]
    locs = worked_example_catalog["locations"]
    roads = worked_example_catalog["roads"]

    all_locs = client.get("/api/locations").get_json()["locations"]
    all_roads = client.get("/api/roads").get_json()["roads"]
    graph = build_graph(all_locs, all_roads)

    # 1. One-way rule: ONEWAY_SRC -> ONEWAY_DST exists, reverse does not
    src_id = locs["ONEWAY_SRC"]["id"]
    dst_id = locs["ONEWAY_DST"]["id"]
    assert (dst_id, 3.0) in graph[src_id]
    assert all(neighbor != src_id for neighbor, _ in graph[dst_id])

    # 2. Unreachable node detection
    validation = validate_network(graph, locs["D"]["id"])
    assert locs["ISOLATED"]["id"] in validation["unreachable"]
    assert validation["is_fully_connected"] is False

    # 3. Closing A-C removes edge from active graph so only D -> B -> E (12 km) remains
    ac_road_id = roads["A-C"]["id"]
    patch_resp = client.patch(f"/api/roads/{ac_road_id}", json={"is_closed": True})
    assert patch_resp.status_code == 200

    updated_roads = client.get("/api/roads").get_json()["roads"]
    detour_graph = build_graph(all_locs, updated_roads)
    assert all(neighbor != locs["C"]["id"] for neighbor, _ in detour_graph[locs["A"]["id"]])


def test_worked_example_routing_and_persistence(worked_example_catalog, db_path):
    """Full end-to-end CP2 routing & persistence verification (auto-activates once /api/routes merges)."""
    pytest.importorskip("backend.api.route_routes")

    client = worked_example_catalog["client"]
    locs = worked_example_catalog["locations"]
    roads = worked_example_catalog["roads"]

    id_d = locs["D"]["id"]
    id_a = locs["A"]["id"]
    id_b = locs["B"]["id"]
    id_c = locs["C"]["id"]
    id_e = locs["E"]["id"]
    id_ow_src = locs["ONEWAY_SRC"]["id"]
    id_ow_dst = locs["ONEWAY_DST"]["id"]
    id_isolated = locs["ISOLATED"]["id"]

    # 1. Same origin and destination -> 0.0 km, path [D]
    same_resp = client.post(
        "/api/routes/point",
        json={"origin_id": id_d, "destination_id": id_d, "avg_speed_kmh": 40.0, "save": False},
    )
    assert same_resp.status_code == 200
    same_route = same_resp.get_json()["route"]
    assert same_route["total_km"] == 0.0
    assert same_route["path"] == [id_d]
    assert same_route["legs"] == []

    # 2. One-way rules: forward succeeds (3.0 km), reverse fails cleanly without 500
    ow_ok = client.post(
        "/api/routes/point",
        json={"origin_id": id_ow_src, "destination_id": id_ow_dst, "avg_speed_kmh": 40.0, "save": False},
    )
    assert ow_ok.status_code == 200
    assert ow_ok.get_json()["route"]["total_km"] == 3.0

    ow_blocked = client.post(
        "/api/routes/point",
        json={"origin_id": id_ow_dst, "destination_id": id_ow_src, "avg_speed_kmh": 40.0, "save": False},
    )
    assert ow_blocked.status_code in (400, 404, 422)
    assert "error" in ow_blocked.get_json()

    # 3. Unreachable destination -> clean error response
    unreach_resp = client.post(
        "/api/routes/point",
        json={"origin_id": id_d, "destination_id": id_isolated, "avg_speed_kmh": 40.0, "save": False},
    )
    assert unreach_resp.status_code in (400, 404, 422)
    assert "error" in unreach_resp.get_json()

    # 4. Worked example shortest path: D -> E = 10.0 km via D -> B -> A -> C -> E (saved)
    point_resp = client.post(
        "/api/routes/point",
        json={"origin_id": id_d, "destination_id": id_e, "avg_speed_kmh": 40.0, "save": True},
    )
    assert point_resp.status_code == 201
    point_route = point_resp.get_json()["route"]
    assert point_route["total_km"] == 10.0
    assert point_route["path"] == [id_d, id_b, id_a, id_c, id_e]
    saved_point_id = point_route["id"]

    # 5. Multi-stop delivery run from D to {B, C, E} -> order D, B, C, E in 10.0 km (saved)
    run_resp = client.post(
        "/api/routes/run",
        json={
            "depot_id": id_d,
            "stop_ids": [id_e, id_c, id_b],
            "avg_speed_kmh": 40.0,
            "return_to_depot": False,
            "save": True,
        },
    )
    assert run_resp.status_code == 201
    run_route = run_resp.get_json()["route"]
    assert run_route["total_km"] == 10.0
    assert run_route["ordered_stops"] == [id_b, id_c, id_e]
    assert run_route["path"] == [id_d, id_b, id_a, id_c, id_e]
    saved_run_id = run_route["id"]

    # 6. Multi-stop run skips unreachable stop and reports it in unreachable_stops
    partial_run = client.post(
        "/api/routes/run",
        json={
            "depot_id": id_d,
            "stop_ids": [id_b, id_isolated],
            "avg_speed_kmh": 40.0,
            "save": False,
        },
    )
    assert partial_run.status_code == 200
    partial_data = partial_run.get_json()["route"]
    assert partial_data["ordered_stops"] == [id_b]
    assert id_isolated in partial_data["unreachable_stops"]

    # 7. Close road A-C -> detour D -> B -> E = 12.0 km (saved)
    ac_road_id = roads["A-C"]["id"]
    assert client.patch(f"/api/roads/{ac_road_id}", json={"is_closed": True}).status_code == 200

    detour_resp = client.post(
        "/api/routes/point",
        json={"origin_id": id_d, "destination_id": id_e, "avg_speed_kmh": 40.0, "save": True},
    )
    assert detour_resp.status_code == 201
    detour_route = detour_resp.get_json()["route"]
    assert detour_route["total_km"] == 12.0
    assert detour_route["path"] == [id_d, id_b, id_e]
    saved_detour_id = detour_route["id"]

    # 8. Persistence across app restart
    restarted_app = create_app({"TESTING": True, "DB_PATH": db_path})
    with restarted_app.test_client() as restarted_client:
        history_resp = restarted_client.get("/api/routes")
        assert history_resp.status_code == 200
        routes_list = history_resp.get_json()["routes"]
        persisted_ids = {r["id"] for r in routes_list}
        assert {saved_point_id, saved_run_id, saved_detour_id} <= persisted_ids

        detail_resp = restarted_client.get(f"/api/routes/{saved_run_id}")
        assert detail_resp.status_code == 200
        detail_route = detail_resp.get_json()["route"]
        assert detail_route["total_km"] == 10.0
        assert len(detail_route["legs"]) == 4