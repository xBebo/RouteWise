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


@pytest.mark.skip(reason="Waiting for Kamal (Dijkstra/NN) and Ziad (/api/routes) to merge into main")
def test_worked_example_routing_and_persistence(worked_example_catalog, db_path):
    """End-to-end CP2 routing verification once /api/routes is merged:
    - Shortest path D -> E = 10.0 km (D -> B -> A -> C -> E)
    - Closing A-C yields detour D -> B -> E = 12.0 km
    - Same origin and destination D -> D = 0.0 km
    - Unreachable destination D -> ISOLATED returns unreachable error cleanly
    - Multi-stop delivery run from D to {B, C, E} visits D, B, C, E in 10.0 km
    - Saved routes & legs persist across app restarts
    """
    pass