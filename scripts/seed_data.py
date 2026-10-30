import csv
import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
LOCATIONS_CSV = os.path.join(DATA_DIR, "locations.csv")
ROADS_CSV = os.path.join(DATA_DIR, "roads.csv")

# مسار قاعدة البيانات
DB_PATH = os.path.join(BASE_DIR, "backend", "routewise.db")
if not os.path.exists(os.path.join(BASE_DIR, "backend")):
    DB_PATH = os.path.join(BASE_DIR, "routewise.db")


def get_connection(db_path=DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_schema(conn):
    schema_sql = """
    CREATE TABLE IF NOT EXISTS locations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        kind TEXT NOT NULL CHECK(kind IN ('DEPOT', 'HUB', 'CUSTOMER')),
        x REAL NOT NULL CHECK(x BETWEEN 0 AND 1000),
        y REAL NOT NULL CHECK(y BETWEEN 0 AND 1000)
    );

    CREATE TABLE IF NOT EXISTS roads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        from_id INTEGER NOT NULL,
        to_id INTEGER NOT NULL,
        distance_km REAL NOT NULL CHECK(distance_km > 0),
        is_one_way INTEGER NOT NULL DEFAULT 0,
        is_closed INTEGER NOT NULL DEFAULT 0,
        FOREIGN KEY (from_id) REFERENCES locations(id) ON DELETE RESTRICT,
        FOREIGN KEY (to_id) REFERENCES locations(id) ON DELETE RESTRICT,
        CHECK(from_id <> to_id),
        UNIQUE(from_id, to_id)
    );

    CREATE TABLE IF NOT EXISTS routes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT NOT NULL,
        mode TEXT NOT NULL CHECK(mode IN ('POINT', 'RUN')),
        origin_id INTEGER NOT NULL,
        total_km REAL NOT NULL,
        avg_speed_kmh REAL NOT NULL,
        FOREIGN KEY (origin_id) REFERENCES locations(id)
    );

    CREATE TABLE IF NOT EXISTS route_legs (
        route_id INTEGER NOT NULL,
        seq INTEGER NOT NULL,
        from_id INTEGER NOT NULL,
        to_id INTEGER NOT NULL,
        km REAL NOT NULL,
        PRIMARY KEY (route_id, seq),
        FOREIGN KEY (route_id) REFERENCES routes(id) ON DELETE CASCADE
    );
    """
    conn.executescript(schema_sql)
    conn.commit()


def seed_database(db_path=DB_PATH):
    conn = get_connection(db_path)
    init_schema(conn)
    cursor = conn.cursor()

    # تفريغ البيانات القديمة
    cursor.execute("DELETE FROM route_legs;")
    cursor.execute("DELETE FROM routes;")
    cursor.execute("DELETE FROM roads;")
    cursor.execute("DELETE FROM locations;")
    conn.commit()

    # 1. إدخال المواقع
    loc_code_to_id = {}
    with open(LOCATIONS_CSV, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            cursor.execute(
                """
                INSERT INTO locations (code, name, kind, x, y)
                VALUES (?, ?, ?, ?, ?)
                """,
                (row["code"], row["name"], row["kind"], float(row["x"]), float(row["y"]))
            )
            loc_code_to_id[row["code"]] = cursor.lastrowid

    print(f"✓ Inserted {len(loc_code_to_id)} locations.")

    # 2. إدخال الطرق
    inserted_roads = 0
    with open(ROADS_CSV, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            from_code = row["from_code"]
            to_code = row["to_code"]

            if from_code not in loc_code_to_id or to_code not in loc_code_to_id:
                continue

            u = loc_code_to_id[from_code]
            v = loc_code_to_id[to_code]
            is_one_way = int(row["is_one_way"])
            is_closed = int(row["is_closed"])
            dist = float(row["distance_km"])

            if is_one_way == 0 and u > v:
                u, v = v, u

            try:
                cursor.execute(
                    """
                    INSERT INTO roads (from_id, to_id, distance_km, is_one_way, is_closed)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (u, v, dist, is_one_way, is_closed)
                )
                inserted_roads += 1
            except sqlite3.IntegrityError:
                pass

    conn.commit()
    print(f"✓ Inserted {inserted_roads} roads.")
    conn.close()
    print("Database seeding completed successfully.")


if __name__ == "__main__":
    seed_database()