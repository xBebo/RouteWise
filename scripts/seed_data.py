"""Load the demo network using the application's schema and database path."""

import argparse
import csv
import math
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

# Support both python scripts/seed_data.py and python -m scripts.seed_data.
BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from backend.database.connection import DB_PATH, SCHEMA_PATH

LOCATIONS_CSV = BASE_DIR / "data" / "locations.csv"
ROADS_CSV = BASE_DIR / "data" / "roads.csv"


def get_connection(db_path=DB_PATH):
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_schema(conn):
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))


def _read_rows(path, columns):
    with Path(path).open(newline="", encoding="utf-8-sig") as source:
        reader = csv.DictReader(source)
        missing = set(columns) - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"{path}: missing columns: {', '.join(sorted(missing))}")
        for row in reader:
            line = reader.line_num
            if None in row or any(not (row.get(key) or "").strip() for key in columns):
                raise ValueError(f"{path}: row {line}: missing values or extra fields")
            yield line, {key: row[key].strip() for key in columns}


def _number(value, minimum, maximum, field):
    number = float(value)
    if not math.isfinite(number) or not minimum <= number <= maximum:
        raise ValueError(f"{field} must be finite and between {minimum} and {maximum}")
    return number


def _load_sample(locations_csv, roads_csv):
    locations, roads, codes, pairs = [], [], set(), {}
    for line, row in _read_rows(locations_csv, ("code", "name", "kind", "x", "y")):
        try:
            code = row["code"]
            # Match SQLite's ASCII-only NOCASE collation.
            key = code.translate(str.maketrans("ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"))
            if key in codes:
                raise ValueError(f"duplicate location code: {code}")
            if row["kind"] not in {"DEPOT", "HUB", "CUSTOMER"}:
                raise ValueError("kind must be DEPOT, HUB or CUSTOMER")
            x = _number(row["x"], 0, 1000, "x")
            y = _number(row["y"], 0, 1000, "y")
            locations.append((code, row["name"], row["kind"], x, y))
            codes.add(key)
        except ValueError as exc:
            raise ValueError(f"{locations_csv}: row {line}: {exc}") from exc
    known_codes = {location[0] for location in locations}
    for line, row in _read_rows(roads_csv, ("from_code", "to_code", "distance_km", "is_one_way", "is_closed")):
        try:
            start, end = row["from_code"], row["to_code"]
            if start not in known_codes or end not in known_codes:
                raise ValueError(f"unknown location code: {start} -> {end}")
            if start == end:
                raise ValueError("a road cannot connect a location to itself")
            if row["is_one_way"] not in {"0", "1"} or row["is_closed"] not in {"0", "1"}:
                raise ValueError("road flags must be 0 or 1")
            distance = _number(row["distance_km"], 0, 500, "distance_km")
            if distance == 0:
                raise ValueError("distance_km must be greater than zero")
            one_way, closed = int(row["is_one_way"]), int(row["is_closed"])
            pair = tuple(sorted((start, end)))
            directions = pairs.setdefault(pair, set())
            direction = (start, end)
            if directions and (not one_way or None in directions or direction in directions):
                raise ValueError(f"duplicate or conflicting road: {start} -> {end}")
            directions.add(direction if one_way else None)
            roads.append((line, start, end, distance, one_way, closed))
        except ValueError as exc:
            raise ValueError(f"{roads_csv}: row {line}: {exc}") from exc
    if not locations or not roads:
        raise ValueError("Sample CSV files must contain locations and roads")
    return locations, roads


def seed_database(db_path=DB_PATH, *, locations_csv=None, roads_csv=None):
    locations_csv = LOCATIONS_CSV if locations_csv is None else locations_csv
    roads_csv = ROADS_CSV if roads_csv is None else roads_csv
    # Validate all input before opening or changing the target database.
    locations, roads = _load_sample(locations_csv, roads_csv)
    with closing(get_connection(db_path)) as conn:
        init_schema(conn)
        with conn:
            conn.execute("DELETE FROM route_legs")
            conn.execute("DELETE FROM routes")
            conn.execute("DELETE FROM roads")
            conn.execute("DELETE FROM locations")
            ids = {}
            for location in locations:
                cursor = conn.execute(
                    "INSERT INTO locations (code, name, kind, x, y) VALUES (?, ?, ?, ?, ?)", location
                )
                ids[location[0]] = cursor.lastrowid
            for line, start, end, distance, one_way, closed in roads:
                u, v = ids[start], ids[end]
                if not one_way and u > v:
                    u, v = v, u
                try:
                    conn.execute(
                        "INSERT INTO roads (from_id, to_id, distance_km, is_one_way, is_closed) VALUES (?, ?, ?, ?, ?)",
                        (u, v, distance, one_way, closed),
                    )
                except sqlite3.IntegrityError as exc:
                    raise ValueError(f"{roads_csv}: row {line}: {exc}") from exc
    print(f"Inserted {len(locations)} locations and {len(roads)} roads into {db_path}.")


def main():
    parser = argparse.ArgumentParser(description="Reset the selected database to the sample network.")
    parser.add_argument("--db", type=Path, default=DB_PATH, help="Target SQLite file")
    parser.add_argument("--reset", action="store_true", help="Confirm replacement of existing locations, roads and route history")
    args = parser.parse_args()
    if not args.reset:
        parser.error("--reset is required; this replaces data in the selected database")
    try:
        seed_database(args.db)
    except (OSError, ValueError, sqlite3.Error) as exc:
        parser.exit(1, f"Seed failed: {exc}\n")


if __name__ == "__main__":
    main()
