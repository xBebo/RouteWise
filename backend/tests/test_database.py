# Verifies Database schema and constraints.

import sqlite3
from pathlib import Path

import pytest


SCHEMA_PATH = (
    Path(__file__).resolve().parents[1]
    / "database"
    / "schema.sql"
)


@pytest.fixture
def db():
    connection = sqlite3.connect(":memory:")
    connection.execute("PRAGMA foreign_keys = ON")

    schema = SCHEMA_PATH.read_text(encoding="utf-8")
    connection.executescript(schema)

    yield connection
    connection.close()


def add_location(db, code, kind="DEPOT"):
    cursor = db.execute(
        """
        INSERT INTO locations (code, name, kind, x, y)
        VALUES (?, ?, ?, ?, ?)
        """,
        (code, f"Location {code}", kind, 100, 200),
    )
    return cursor.lastrowid


def test_tables_created(db):
    rows = db.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'"
    ).fetchall()

    names = {row[0] for row in rows}

    assert {"locations", "roads", "routes", "route_legs"} <= names


def test_duplicate_location_rejected(db):
    add_location(db, "DEPOT1")

    with pytest.raises(sqlite3.IntegrityError):
        add_location(db, "depot1")


def test_invalid_road_distance_rejected(db):
    a = add_location(db, "A")
    b = add_location(db, "B", "CUSTOMER")

    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO roads (from_id, to_id, distance_km) "
            "VALUES (?, ?, ?)",
            (a, b, -5),
        )


def test_road_cannot_connect_to_itself(db):
    a = add_location(db, "A")

    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO roads (from_id, to_id, distance_km) "
            "VALUES (?, ?, ?)",
            (a, a, 10),
        )


def test_unknown_location_rejected(db):
    a = add_location(db, "A")

    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO roads (from_id, to_id, distance_km) "
            "VALUES (?, ?, ?)",
            (a, 9999, 10),
        )


def test_duplicate_road_rejected(db):
    a = add_location(db, "A")
    b = add_location(db, "B", "CUSTOMER")

    sql = (
        "INSERT INTO roads (from_id, to_id, distance_km) "
        "VALUES (?, ?, ?)"
    )

    db.execute(sql, (a, b, 5))

    with pytest.raises(sqlite3.IntegrityError):
        db.execute(sql, (a, b, 5))


def test_referenced_location_cannot_be_deleted(db):
    a = add_location(db, "A")
    b = add_location(db, "B", "CUSTOMER")

    db.execute(
        "INSERT INTO roads (from_id, to_id, distance_km) "
        "VALUES (?, ?, ?)",
        (a, b, 5),
    )

    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "DELETE FROM locations WHERE id = ?",
            (a,),
        )
