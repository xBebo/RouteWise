"""Tests for CP2 route planning API endpoints, validation, and route persistence."""

import sqlite3
from contextlib import closing

import pytest

from backend.app import create_app


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "test_routes.db"


@pytest.fixture
def client(db_path):
    app = create_app({"TESTING": True, "DB_PATH": db_path})
    with app.test_client() as test_client:
        yield test_client


@pytest.fixture
def worked_network(client):
    """Build the catalog worked example plus one-way and isolated nodes."""
    nodes_spec = [
        ("D", "Depot D", "DEPOT", 100.0, 500.0),
        ("A", "Node A", "CUSTOMER", 300.0, 300.0),
        ("B", "Node B", "CUSTOMER", 300.0, 700.0),
        ("C", "Node C", "CUSTOMER", 600.0, 300.0),
        ("E", "Node E", "CUSTOMER", 900.0, 500.0),
        ("OW_SRC", "One-Way Start", "HUB", 100.0, 100.0),
        ("OW_DST", "One-Way End", "CUSTOMER", 200.0, 100.0),
        ("ISOLATED", "Isolated Customer", "CUSTOMER", 950.0, 950.0),
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
        ("D", "OW_SRC", 2.0, False, False),
        ("OW_SRC", "OW_DST", 3.0, True, False),
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


def test_point_route_worked_example_and_closure_detour(worked_network):
    client = worked_network["client"]
    locs = worked_network["locations"]
    roads = worked_network["roads"]

    resp = client.post(
        "/api/routes/point",
        json={
            "origin_id": locs["D"]["id"],
            "destination_id": locs["E"]["id"],
            "avg_speed_kmh": 60.0,
        },
    )
    assert resp.status_code == 200
    route = resp.get_json()["route"]
    assert route["id"] is None
    assert route["mode"] == "POINT"
    assert route["total_km"] == 10.0
    assert route["eta_minutes"] == 10.0
    assert route["path"] == [
        locs["D"]["id"],
        locs["B"]["id"],
        locs["A"]["id"],
        locs["C"]["id"],
        locs["E"]["id"],
    ]
    assert [leg["cumulative_km"] for leg in route["legs"]] == [2.0, 3.0, 8.0, 10.0]

    # Closing A-C forces detour D -> B -> E = 12.0 km.
    close_resp = client.patch(
        f"/api/roads/{roads['A-C']['id']}",
        json={"is_closed": True},
    )
    assert close_resp.status_code == 200

    detour_resp = client.post(
        "/api/routes/point",
        json={
            "origin_id": locs["D"]["id"],
            "destination_id": locs["E"]["id"],
            "avg_speed_kmh": 30.0,
        },
    )
    assert detour_resp.status_code == 200
    detour = detour_resp.get_json()["route"]
    assert detour["total_km"] == 12.0
    assert detour["eta_minutes"] == 24.0
    assert detour["path"] == [locs["D"]["id"], locs["B"]["id"], locs["E"]["id"]]


def test_point_route_same_origin_and_no_route_cases(worked_network):
    client = worked_network["client"]
    locs = worked_network["locations"]

    same_resp = client.post(
        "/api/routes/point",
        json={
            "origin_id": locs["D"]["id"],
            "destination_id": locs["D"]["id"],
            "avg_speed_kmh": 50.0,
        },
    )
    assert same_resp.status_code == 200
    same_route = same_resp.get_json()["route"]
    assert same_route["total_km"] == 0.0
    assert same_route["eta_minutes"] == 0.0
    assert same_route["path"] == [locs["D"]["id"]]
    assert same_route["legs"] == []

    # Isolated destination -> 422 no-route response.
    iso_resp = client.post(
        "/api/routes/point",
        json={
            "origin_id": locs["D"]["id"],
            "destination_id": locs["ISOLATED"]["id"],
            "avg_speed_kmh": 50.0,
        },
    )
    assert iso_resp.status_code == 422
    assert "No route exists" in iso_resp.get_json()["error"]

    # Traversing a one-way road backwards is unreachable.
    backwards = client.post(
        "/api/routes/point",
        json={
            "origin_id": locs["OW_DST"]["id"],
            "destination_id": locs["OW_SRC"]["id"],
            "avg_speed_kmh": 50.0,
        },
    )
    assert backwards.status_code == 422


def test_delivery_run_worked_example_and_partial_unreachable(worked_network):
    client = worked_network["client"]
    locs = worked_network["locations"]

    resp = client.post(
        "/api/routes/run",
        json={
            "depot_id": locs["D"]["id"],
            "stop_ids": [locs["E"]["id"], locs["B"]["id"], locs["C"]["id"]],
            "avg_speed_kmh": 60.0,
            "return_to_depot": False,
        },
    )
    assert resp.status_code == 200
    route = resp.get_json()["route"]
    assert route["mode"] == "RUN"
    assert route["method"] == "heuristic"
    assert route["label"] == "heuristic, not guaranteed optimal"
    assert route["ordered_stops"] == [
        locs["B"]["id"],
        locs["C"]["id"],
        locs["E"]["id"],
    ]
    assert route["total_km"] == 10.0
    assert route["eta_minutes"] == 10.0
    # Pass-through node A is not marked as a delivery stop.
    assert [(leg["to_id"], leg["is_delivery_stop"]) for leg in route["legs"]] == [
        (locs["B"]["id"], True),
        (locs["A"]["id"], False),
        (locs["C"]["id"], True),
        (locs["E"]["id"], True),
    ]
    assert [leg["cumulative_km"] for leg in route["legs"]] == [2.0, 3.0, 8.0, 10.0]

    # Include unreachable stop alongside reachable stop + return_to_depot.
    partial_resp = client.post(
        "/api/routes/run",
        json={
            "depot_id": locs["D"]["id"],
            "stop_ids": [locs["B"]["id"], locs["ISOLATED"]["id"]],
            "avg_speed_kmh": 40.0,
            "return_to_depot": True,
        },
    )
    assert partial_resp.status_code == 200
    partial = partial_resp.get_json()["route"]
    assert partial["ordered_stops"] == [locs["B"]["id"]]
    assert partial["unreachable_stops"] == [locs["ISOLATED"]["id"]]
    assert partial["returned_to_depot"] is True
    assert partial["total_km"] == 4.0
    assert partial["warnings"]

    # All stops unreachable -> 422.
    all_unreachable = client.post(
        "/api/routes/run",
        json={
            "depot_id": locs["D"]["id"],
            "stop_ids": [locs["ISOLATED"]["id"]],
            "avg_speed_kmh": 40.0,
        },
    )
    assert all_unreachable.status_code == 422
    assert all_unreachable.get_json()["unreachable_stops"] == [locs["ISOLATED"]["id"]]


def test_route_validation_rejects_invalid_inputs(worked_network):
    client = worked_network["client"]
    locs = worked_network["locations"]

    # Invalid speeds (zero, negative, bool, string).
    for bad_speed in (0, -10, True, "fast"):
        resp = client.post(
            "/api/routes/point",
            json={
                "origin_id": locs["D"]["id"],
                "destination_id": locs["E"]["id"],
                "avg_speed_kmh": bad_speed,
            },
        )
        assert resp.status_code == 400

    # Nonexistent origin/destination.
    assert (
        client.post(
            "/api/routes/point",
            json={
                "origin_id": 9999,
                "destination_id": locs["E"]["id"],
                "avg_speed_kmh": 50.0,
            },
        ).status_code
        == 400
    )

    # Out-of-range SQLite ID.
    assert (
        client.post(
            "/api/routes/point",
            json={
                "origin_id": 2**63,
                "destination_id": locs["E"]["id"],
                "avg_speed_kmh": 50.0,
            },
        ).status_code
        == 400
    )

    # Non-DEPOT used as depot_id.
    non_depot = client.post(
        "/api/routes/run",
        json={
            "depot_id": locs["A"]["id"],
            "stop_ids": [locs["B"]["id"]],
            "avg_speed_kmh": 50.0,
        },
    )
    assert non_depot.status_code == 400

    # Too few stops (only depot) or > 8 stops.
    only_depot = client.post(
        "/api/routes/run",
        json={
            "depot_id": locs["D"]["id"],
            "stop_ids": [locs["D"]["id"]],
            "avg_speed_kmh": 50.0,
        },
    )
    assert only_depot.status_code == 400

    extra_ids = []
    for i in range(9):
        loc = client.post(
            "/api/locations",
            json={"code": f"EX_{i}", "name": f"Extra {i}", "kind": "CUSTOMER", "x": 10, "y": 10},
        ).get_json()["location"]
        extra_ids.append(loc["id"])

    too_many = client.post(
        "/api/routes/run",
        json={
            "depot_id": locs["D"]["id"],
            "stop_ids": extra_ids,
            "avg_speed_kmh": 50.0,
        },
    )
    assert too_many.status_code == 400

    # Invalid save mode and missing route detail ID.
    assert client.post("/api/routes", json={"mode": "INVALID"}).status_code == 400
    assert client.get("/api/routes/99999").status_code == 404
    assert client.get(f"/api/routes/{2**63}").status_code == 400


def test_saved_routes_survive_restart_and_road_changes(worked_network, db_path):
    client = worked_network["client"]
    locs = worked_network["locations"]
    roads = worked_network["roads"]

    # Save a POINT route via POST /api/routes and a RUN route via save=True.
    save_point = client.post(
        "/api/routes",
        json={
            "mode": "POINT",
            "origin_id": locs["D"]["id"],
            "destination_id": locs["E"]["id"],
            "avg_speed_kmh": 50.0,
        },
    )
    assert save_point.status_code == 201
    point_id = save_point.get_json()["route"]["id"]

    save_run = client.post(
        "/api/routes/run",
        json={
            "depot_id": locs["D"]["id"],
            "stop_ids": [locs["B"]["id"], locs["C"]["id"], locs["E"]["id"]],
            "avg_speed_kmh": 60.0,
            "return_to_depot": True,
            "save": True,
        },
    )
    assert save_run.status_code == 201
    run_id = save_run.get_json()["route"]["id"]

    # Mutate and delete roads after saving routes.
    assert client.patch(f"/api/roads/{roads['A-C']['id']}", json={"is_closed": True}).status_code == 200
    assert client.patch(f"/api/roads/{roads['D-B']['id']}", json={"distance_km": 99.0}).status_code == 200
    assert client.delete(f"/api/roads/{roads['C-E']['id']}").status_code == 200

    # Restart app on the same SQLite file and verify snapshots are unchanged.
    restarted_app = create_app({"TESTING": True, "DB_PATH": db_path})
    with restarted_app.test_client() as new_client:
        history = new_client.get("/api/routes")
        assert history.status_code == 200
        routes = history.get_json()["routes"]
        assert [r["id"] for r in routes] == [run_id, point_id]

        point_detail = new_client.get(f"/api/routes/{point_id}")
        assert point_detail.status_code == 200
        loaded_point = point_detail.get_json()["route"]
        assert loaded_point["total_km"] == 10.0
        assert loaded_point["eta_minutes"] == 12.0
        assert loaded_point["path"] == [
            locs["D"]["id"],
            locs["B"]["id"],
            locs["A"]["id"],
            locs["C"]["id"],
            locs["E"]["id"],
        ]
        assert [leg["cumulative_km"] for leg in loaded_point["legs"]] == [
            2.0,
            3.0,
            8.0,
            10.0,
        ]

        run_detail = new_client.get(f"/api/routes/{run_id}")
        assert run_detail.status_code == 200
        loaded_run = run_detail.get_json()["route"]
        assert loaded_run["returned_to_depot"] is True
        assert loaded_run["ordered_stops"] == [
            locs["B"]["id"],
            locs["C"]["id"],
            locs["E"]["id"],
        ]
        assert loaded_run["total_km"] == 20.0


def test_route_save_rolls_back_atomically_on_leg_insert_failure(worked_network, db_path):
    client = worked_network["client"]
    locs = worked_network["locations"]

    with closing(sqlite3.connect(db_path)) as conn:
        conn.execute(
            "CREATE TRIGGER fail_second_leg BEFORE INSERT ON route_legs "
            "WHEN NEW.seq = 2 "
            "BEGIN SELECT RAISE(ABORT, 'simulated leg failure'); END"
        )
        conn.commit()

    response = client.post(
        "/api/routes",
        json={
            "mode": "POINT",
            "origin_id": locs["D"]["id"],
            "destination_id": locs["E"]["id"],
            "avg_speed_kmh": 50.0,
        },
    )
    assert response.status_code == 500
    assert response.get_json() == {"error": "Internal server error."}

    # Neither the route header nor the first leg may remain committed.
    with closing(sqlite3.connect(db_path)) as conn:
        assert conn.execute("SELECT COUNT(*) FROM routes").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM route_legs").fetchone()[0] == 0


def test_tiny_positive_distance_preserves_precision_across_preview_save_and_reload(client):
    depot = client.post(
        "/api/locations",
        json={"code": "TINY_D", "name": "Tiny Depot", "kind": "DEPOT", "x": 10, "y": 10},
    ).get_json()["location"]
    cust = client.post(
        "/api/locations",
        json={"code": "TINY_C", "name": "Tiny Customer", "kind": "CUSTOMER", "x": 20, "y": 20},
    ).get_json()["location"]

    tiny_km = 1e-11
    road_resp = client.post(
        "/api/roads",
        json={
            "from_id": depot["id"],
            "to_id": cust["id"],
            "distance_km": tiny_km,
            "is_one_way": False,
            "is_closed": False,
        },
    )
    assert road_resp.status_code == 201

    # Point-to-point preview must preserve positive 1e-11 precision.
    preview_resp = client.post(
        "/api/routes/point",
        json={
            "origin_id": depot["id"],
            "destination_id": cust["id"],
            "avg_speed_kmh": 1.0,
        },
    )
    assert preview_resp.status_code == 200
    preview = preview_resp.get_json()["route"]
    assert preview["total_km"] == pytest.approx(tiny_km)
    assert preview["legs"][0]["km"] == pytest.approx(tiny_km)
    assert preview["legs"][0]["cumulative_km"] == pytest.approx(tiny_km)

    # Save and reload via detail and history endpoints without losing precision.
    save_resp = client.post(
        "/api/routes/point",
        json={
            "origin_id": depot["id"],
            "destination_id": cust["id"],
            "avg_speed_kmh": 1.0,
            "save": True,
        },
    )
    assert save_resp.status_code == 201
    saved = save_resp.get_json()["route"]
    assert saved["total_km"] == pytest.approx(tiny_km)
    assert saved["legs"][0]["km"] == pytest.approx(tiny_km)

    detail = client.get(f"/api/routes/{saved['id']}").get_json()["route"]
    assert detail["total_km"] == pytest.approx(tiny_km)
    assert detail["legs"][0]["km"] == pytest.approx(tiny_km)
    assert detail["legs"][0]["cumulative_km"] == pytest.approx(tiny_km)

    # Multi-stop run preview & save with 1e-11 road.
    run_save = client.post(
        "/api/routes/run",
        json={
            "depot_id": depot["id"],
            "stop_ids": [cust["id"]],
            "avg_speed_kmh": 1.0,
            "save": True,
        },
    )
    assert run_save.status_code == 201
    run_route = run_save.get_json()["route"]
    assert run_route["total_km"] == pytest.approx(tiny_km)
    assert run_route["legs"][0]["km"] == pytest.approx(tiny_km)


def test_non_finite_eta_rejected_with_field_400_before_any_write(worked_network, db_path):
    client = worked_network["client"]
    locs = worked_network["locations"]

    # 3 km road (OW_SRC -> OW_DST) at 1e-310 km/h would produce Infinity ETA.
    for endpoint, payload in [
        (
            "/api/routes/point",
            {
                "origin_id": locs["OW_SRC"]["id"],
                "destination_id": locs["OW_DST"]["id"],
                "avg_speed_kmh": 1e-310,
                "save": False,
            },
        ),
        (
            "/api/routes/point",
            {
                "origin_id": locs["OW_SRC"]["id"],
                "destination_id": locs["OW_DST"]["id"],
                "avg_speed_kmh": 1e-310,
                "save": True,
            },
        ),
        (
            "/api/routes",
            {
                "mode": "POINT",
                "origin_id": locs["OW_SRC"]["id"],
                "destination_id": locs["OW_DST"]["id"],
                "avg_speed_kmh": 1e-310,
            },
        ),
        (
            "/api/routes/run",
            {
                "depot_id": locs["D"]["id"],
                "stop_ids": [locs["B"]["id"]],
                "avg_speed_kmh": 1e-310,
                "save": True,
            },
        ),
    ]:
        resp = client.post(endpoint, json=payload)
        assert resp.status_code == 400
        body = resp.get_json()
        assert "avg_speed_kmh" in body.get("fields", {})

    with closing(sqlite3.connect(db_path)) as conn:
        assert conn.execute("SELECT COUNT(*) FROM routes").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM route_legs").fetchone()[0] == 0


def test_skipped_stops_omitted_on_reload_when_not_persisted(worked_network):
    client = worked_network["client"]
    locs = worked_network["locations"]

    save_resp = client.post(
        "/api/routes",
        json={
            "mode": "RUN",
            "depot_id": locs["D"]["id"],
            "stop_ids": [locs["B"]["id"], locs["ISOLATED"]["id"]],
            "avg_speed_kmh": 40.0,
        },
    )
    assert save_resp.status_code == 201
    saved = save_resp.get_json()["route"]
    assert saved["unreachable_stops"] == [locs["ISOLATED"]["id"]]

    detail = client.get(f"/api/routes/{saved['id']}").get_json()["route"]
    assert "unreachable_stops" not in detail

    history = client.get("/api/routes").get_json()["routes"]
    assert len(history) == 1
    assert "unreachable_stops" not in history[0]
