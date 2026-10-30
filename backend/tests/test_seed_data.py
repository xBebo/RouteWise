import csv
import sqlite3
from contextlib import closing

import pytest

from backend.database import connection
from scripts import seed_data as seed


def snapshot(path):
    with closing(sqlite3.connect(path)) as conn:
        return list(conn.iterdump())


def write_csv(path, header, rows):
    with path.open("w", newline="", encoding="utf-8") as target:
        writer = csv.writer(target)
        writer.writerow(header)
        writer.writerows(rows)
    return path


def test_seed_uses_application_path_and_schema(tmp_path):
    assert seed.DB_PATH == connection.DB_PATH
    path = tmp_path / "sample.db"
    seed.seed_database(path)
    with closing(sqlite3.connect(path)) as actual, closing(sqlite3.connect(":memory:")) as expected:
        expected.executescript(connection.SCHEMA_PATH.read_text(encoding="utf-8"))
        query = "SELECT name, sql FROM sqlite_master WHERE type = 'table' ORDER BY name"
        assert actual.execute(query).fetchall() == expected.execute(query).fetchall()
        assert actual.execute("SELECT COUNT(*) FROM roads").fetchone()[0] == 36


def test_reseed_and_reconnect_preserve_demo_content(tmp_path):
    path = tmp_path / "sample.db"
    seed.seed_database(path)
    with closing(sqlite3.connect(path)) as conn:
        before = conn.execute("SELECT code, name, kind, x, y FROM locations ORDER BY code").fetchall()
    seed.seed_database(path)
    with closing(sqlite3.connect(path)) as conn:
        assert conn.execute("SELECT code, name, kind, x, y FROM locations ORDER BY code").fetchall() == before
        assert conn.execute("SELECT COUNT(*) FROM roads").fetchone()[0] == 36


def test_missing_csv_preserves_existing_database(tmp_path):
    path = tmp_path / "sample.db"
    seed.seed_database(path)
    before = snapshot(path)
    with pytest.raises(FileNotFoundError):
        seed.seed_database(path, locations_csv=tmp_path / "missing.csv")
    assert snapshot(path) == before


@pytest.mark.parametrize("values, message", [
    (("UNKNOWN", "CUST_01", "2", "0", "0"), "unknown location"),
    (("DEPOT_MAIN", "DEPOT_MAIN", "2", "0", "0"), "itself"),
    (("DEPOT_MAIN", "CUST_01", "501", "0", "0"), "distance_km"),
    (("DEPOT_MAIN", "CUST_01", "0", "0", "0"), "distance_km"),
    (("DEPOT_MAIN", "CUST_01", "nan", "0", "0"), "distance_km"),
    (("DEPOT_MAIN", "CUST_01", "2", "false", "0"), "flags"),
])
def test_invalid_roads_report_row_and_preserve_data(tmp_path, values, message):
    path = tmp_path / "sample.db"
    seed.seed_database(path)
    before = snapshot(path)
    roads = write_csv(tmp_path / "bad.csv", ("from_code", "to_code", "distance_km", "is_one_way", "is_closed"), [values])
    with pytest.raises(ValueError, match=f"bad.csv: row 2: .*{message}"):
        seed.seed_database(path, roads_csv=roads)
    assert snapshot(path) == before


def test_missing_columns_report_error_before_database_creation(tmp_path):
    locations = write_csv(tmp_path / "bad.csv", ["code"], [["A"]])
    path = tmp_path / "sample.db"
    with pytest.raises(ValueError, match="missing columns"):
        seed.seed_database(path, locations_csv=locations)
    assert not path.exists()


def test_conflicting_two_way_and_one_way_roads_are_rejected(tmp_path):
    roads = write_csv(tmp_path / "bad.csv", ("from_code", "to_code", "distance_km", "is_one_way", "is_closed"), [
        ("DEPOT_MAIN", "CUST_01", "2", "0", "0"),
        ("CUST_01", "DEPOT_MAIN", "3", "1", "0"),
    ])
    with pytest.raises(ValueError, match="row 3: duplicate or conflicting road"):
        seed.seed_database(tmp_path / "sample.db", roads_csv=roads)


def test_database_write_failure_rolls_back_deletions_and_closes_connection(tmp_path):
    path = tmp_path / "sample.db"
    seed.seed_database(path)
    with closing(sqlite3.connect(path)) as conn:
        conn.execute("CREATE TRIGGER reject_roads BEFORE INSERT ON roads BEGIN SELECT RAISE(ABORT, 'test failure'); END")
        conn.commit()
    before = snapshot(path)
    with pytest.raises(ValueError, match="row 2: test failure"):
        seed.seed_database(path)
    assert snapshot(path) == before
    # An open failed transaction must not leave the file locked on Windows.
    path.rename(tmp_path / "renamed.db")


def test_unrelated_database_is_untouched(tmp_path):
    unrelated = tmp_path / "unrelated.db"
    with closing(sqlite3.connect(unrelated)) as conn:
        conn.execute("CREATE TABLE keep (value TEXT)")
        conn.execute("INSERT INTO keep VALUES ('unchanged')")
        conn.commit()
    before = snapshot(unrelated)
    seed.seed_database(tmp_path / "sample.db")
    assert snapshot(unrelated) == before
