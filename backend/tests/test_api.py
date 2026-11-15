"""Tests for the Flask REST API, NetworkService, and SQLite repositories."""

import sqlite3
from contextlib import closing

import pytest

from backend.algorithms.graph import build_graph
from backend.algorithms.network_validation import validate_network
from backend.app import create_app


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "test_routewise.db"


@pytest.fixture
def client(db_path):
    app = create_app({"TESTING": True, "DB_PATH": db_path})
    with app.test_client() as test_client:
        yield test_client


def _create_location(
    client,
    *,
    code="DEPOT_1",
    name="Main Depot",
    kind="DEPOT",
    x=500.0,
    y=500.0,
):
    return client.post(
        "/api/locations",
        json={"code": code, "name": name, "kind": kind, "x": x, "y": y},
    )


def _create_road(
    client,
    *,
    from_id,
    to_id,
    distance_km=5.0,
    is_one_way=False,
    is_closed=False,
):
    return client.post(
        "/api/roads",
        json={
            "from_id": from_id,
            "to_id": to_id,
            "distance_km": distance_km,
            "is_one_way": is_one_way,
            "is_closed": is_closed,
        },
    )


def test_app_initializes_database_tables_automatically(db_path):
    assert not db_path.exists()
    create_app({"TESTING": True, "DB_PATH": db_path})
    assert db_path.exists()

    with closing(sqlite3.connect(db_path)) as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
    assert {"locations", "roads", "routes", "route_legs"} <= tables


def test_health_endpoint(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_locations_crud_flow(client):
    create_resp = _create_location(
        client, code="D1", name="Central Depot", kind="DEPOT", x=0, y=1000
    )
    assert create_resp.status_code == 201
    created = create_resp.get_json()["location"]
    assert created["code"] == "D1"
    assert created["x"] == 0.0
    assert created["y"] == 1000.0

    list_resp = client.get("/api/locations")
    assert list_resp.status_code == 200
    assert len(list_resp.get_json()["locations"]) == 1

    patch_resp = client.patch(
        f"/api/locations/{created['id']}",
        json={"name": "Updated Depot", "x": 250.5},
    )
    assert patch_resp.status_code == 200
    updated = patch_resp.get_json()["location"]
    assert updated["name"] == "Updated Depot"
    assert updated["x"] == 250.5
    assert updated["code"] == "D1"

    delete_resp = client.delete(f"/api/locations/{created['id']}")
    assert delete_resp.status_code == 200
    assert delete_resp.get_json() == {"deleted": True, "id": created["id"]}
    assert client.get("/api/locations").get_json()["locations"] == []


def test_locations_search_and_kind_filter(client):
    _create_location(client, code="DEP_1", name="Central Depot", kind="DEPOT")
    _create_location(client, code="HUB_N", name="North Hub", kind="HUB", x=200)
    _create_location(client, code="CUS_1", name="North Mart", kind="CUSTOMER", x=300)

    by_kind = client.get("/api/locations?kind=HUB")
    assert by_kind.status_code == 200
    assert [loc["code"] for loc in by_kind.get_json()["locations"]] == ["HUB_N"]

    by_search = client.get("/api/locations?search=north")
    assert by_search.status_code == 200
    assert [loc["code"] for loc in by_search.get_json()["locations"]] == [
        "HUB_N",
        "CUS_1",
    ]

    combined = client.get("/api/locations?q=north&kind=CUSTOMER")
    assert combined.status_code == 200
    assert [loc["code"] for loc in combined.get_json()["locations"]] == ["CUS_1"]

    invalid_filter = client.get("/api/locations?kind=WAREHOUSE")
    assert invalid_filter.status_code == 400


def test_location_validation_and_duplicate_code(client):
    assert _create_location(client, code="DEP1").status_code == 201

    dup_resp = _create_location(client, code="dep1")
    assert dup_resp.status_code == 409
    assert "error" in dup_resp.get_json()

    bad_coords = _create_location(
        client, code="BAD", name="", kind="INVALID", x=-1, y=1001
    )
    assert bad_coords.status_code == 400
    fields = bad_coords.get_json()["fields"]
    assert {"name", "kind", "x", "y"} <= set(fields.keys())

    bool_coord = _create_location(client, code="BOOL", x=True, y=100)
    assert bool_coord.status_code == 400


def test_cannot_delete_location_referenced_by_road_or_route(client, db_path):
    a = _create_location(client, code="A", kind="DEPOT").get_json()["location"]
    b = _create_location(client, code="B", kind="CUSTOMER").get_json()["location"]
    c = _create_location(client, code="C", kind="HUB").get_json()["location"]

    _create_road(client, from_id=a["id"], to_id=b["id"], distance_km=4.5)

    road_block = client.delete(f"/api/locations/{a['id']}")
    assert road_block.status_code == 409

    with closing(sqlite3.connect(db_path)) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        with conn:
            conn.execute(
                "INSERT INTO routes (mode, origin_id, total_km, avg_speed_kmh) "
                "VALUES (?, ?, ?, ?)",
                ("POINT", c["id"], 10.0, 40.0),
            )

    route_block = client.delete(f"/api/locations/{c['id']}")
    assert route_block.status_code == 409


def test_roads_crud_and_two_way_direction_normalization(client):
    loc1 = _create_location(client, code="L1", kind="DEPOT").get_json()["location"]
    loc2 = _create_location(client, code="L2", kind="CUSTOMER").get_json()["location"]

    # Send from_id > to_id for a two-way road: service must normalize to from_id < to_id.
    resp = _create_road(
        client,
        from_id=loc2["id"],
        to_id=loc1["id"],
        distance_km=12.5,
        is_one_way=False,
    )
    assert resp.status_code == 201
    road = resp.get_json()["road"]
    assert road["from_id"] == loc1["id"]
    assert road["to_id"] == loc2["id"]
    assert road["is_one_way"] is False
    assert road["is_closed"] is False

    # Reverse duplicate of the same two-way road must be rejected.
    dup = _create_road(client, from_id=loc1["id"], to_id=loc2["id"], distance_km=7.0)
    assert dup.status_code == 409

    # Conflicting one-way road between the same pair must also be rejected.
    conflict = _create_road(
        client,
        from_id=loc2["id"],
        to_id=loc1["id"],
        distance_km=7.0,
        is_one_way=True,
    )
    assert conflict.status_code == 409

    patch_resp = client.patch(
        f"/api/roads/{road['id']}",
        json={"distance_km": 15.0, "is_closed": True},
    )
    assert patch_resp.status_code == 200
    updated = patch_resp.get_json()["road"]
    assert updated["distance_km"] == 15.0
    assert updated["is_closed"] is True

    closed_only = client.get("/api/roads?is_closed=true")
    assert closed_only.status_code == 200
    assert len(closed_only.get_json()["roads"]) == 1

    del_resp = client.delete(f"/api/roads/{road['id']}")
    assert del_resp.status_code == 200
    assert client.get("/api/roads").get_json()["roads"] == []


def test_opposite_one_way_roads_allowed_and_patch_to_two_way_normalizes(client):
    loc1 = _create_location(client, code="N1", kind="DEPOT").get_json()["location"]
    loc2 = _create_location(client, code="N2", kind="CUSTOMER").get_json()["location"]

    r1 = _create_road(
        client, from_id=loc2["id"], to_id=loc1["id"], distance_km=4.0, is_one_way=True
    )
    assert r1.status_code == 201
    r1_id = r1.get_json()["road"]["id"]

    # Opposite one-way is valid, same-direction duplicate is rejected.
    r2 = _create_road(
        client, from_id=loc1["id"], to_id=loc2["id"], distance_km=6.0, is_one_way=True
    )
    assert r2.status_code == 201
    r2_id = r2.get_json()["road"]["id"]

    dup_same_dir = _create_road(
        client, from_id=loc2["id"], to_id=loc1["id"], distance_km=8.0, is_one_way=True
    )
    assert dup_same_dir.status_code == 409

    # Converting r1 to two-way conflicts while r2 exists; after deleting r2 it succeeds and swaps IDs.
    conflict_patch = client.patch(f"/api/roads/{r1_id}", json={"is_one_way": False})
    assert conflict_patch.status_code == 409

    assert client.delete(f"/api/roads/{r2_id}").status_code == 200
    ok_patch = client.patch(f"/api/roads/{r1_id}", json={"is_one_way": False})
    assert ok_patch.status_code == 200
    normalized = ok_patch.get_json()["road"]
    assert normalized["from_id"] == loc1["id"]
    assert normalized["to_id"] == loc2["id"]
    assert normalized["is_one_way"] is False


def test_road_validation_errors(client):
    loc1 = _create_location(client, code="V1", kind="DEPOT").get_json()["location"]
    loc2 = _create_location(client, code="V2", kind="CUSTOMER").get_json()["location"]

    assert (
        _create_road(client, from_id=loc1["id"], to_id=loc1["id"], distance_km=5).status_code
        == 400
    )
    assert (
        _create_road(client, from_id=loc1["id"], to_id=loc2["id"], distance_km=0).status_code
        == 400
    )
    assert (
        _create_road(client, from_id=loc1["id"], to_id=loc2["id"], distance_km=500.1).status_code
        == 400
    )
    assert (
        _create_road(client, from_id=loc1["id"], to_id=99999, distance_km=10).status_code
        == 400
    )
    assert (
        _create_road(
            client, from_id=loc1["id"], to_id=loc2["id"], distance_km=True
        ).status_code
        == 400
    )


def test_data_persists_across_app_restarts_and_integrates_with_graph(db_path):
    app_one = create_app({"TESTING": True, "DB_PATH": db_path})
    with app_one.test_client() as client_one:
        depot = _create_location(client_one, code="D", kind="DEPOT").get_json()["location"]
        hub = _create_location(client_one, code="H", kind="HUB").get_json()["location"]
        _create_location(client_one, code="ISO", kind="CUSTOMER")
        _create_road(
            client_one, from_id=depot["id"], to_id=hub["id"], distance_km=8.0
        )

    app_two = create_app({"TESTING": True, "DB_PATH": db_path})
    with app_two.test_client() as client_two:
        locations = client_two.get("/api/locations").get_json()["locations"]
        roads = client_two.get("/api/roads").get_json()["roads"]

    assert len(locations) == 3
    assert len(roads) == 1

    graph = build_graph(locations, roads)
    validation = validate_network(graph, depot["id"])
    assert validation["reachable_count"] == 2
    assert validation["is_fully_connected"] is False


def test_malformed_json_and_not_found_return_json_errors(client):
    bad_json = client.post(
        "/api/locations",
        data="{not valid json",
        content_type="application/json",
    )
    assert bad_json.status_code == 400
    assert "error" in bad_json.get_json()

    missing_loc = client.patch("/api/locations/999", json={"name": "Nope"})
    assert missing_loc.status_code == 404
    assert "error" in missing_loc.get_json()

    missing_road = client.delete("/api/roads/999")
    assert missing_road.status_code == 404
    assert "error" in missing_road.get_json()
