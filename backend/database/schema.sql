
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS locations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL COLLATE NOCASE UNIQUE,
    name TEXT NOT NULL,
    kind TEXT NOT NULL CHECK (
        kind IN ('DEPOT', 'HUB', 'CUSTOMER')
    ),
    x REAL NOT NULL CHECK (x BETWEEN 0 AND 1000),
    y REAL NOT NULL CHECK (y BETWEEN 0 AND 1000)
);

CREATE TABLE IF NOT EXISTS roads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_id INTEGER NOT NULL,
    to_id INTEGER NOT NULL,
    distance_km REAL NOT NULL CHECK (
        distance_km > 0 AND distance_km <= 500
    ),
    is_one_way INTEGER NOT NULL DEFAULT 0
        CHECK (is_one_way IN (0, 1)),
    is_closed INTEGER NOT NULL DEFAULT 0
        CHECK (is_closed IN (0, 1)),

    FOREIGN KEY (from_id) REFERENCES locations(id)
        ON DELETE RESTRICT,
    FOREIGN KEY (to_id) REFERENCES locations(id)
        ON DELETE RESTRICT,

    CHECK (from_id != to_id),
    CHECK (is_one_way = 1 OR from_id < to_id),
    UNIQUE (from_id, to_id)
);

CREATE TABLE IF NOT EXISTS routes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL DEFAULT (
        strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
    ),
    mode TEXT NOT NULL CHECK (
        mode IN ('POINT', 'RUN')
    ),
    origin_id INTEGER NOT NULL,
    total_km REAL NOT NULL CHECK (total_km >= 0),
    avg_speed_kmh REAL NOT NULL CHECK (avg_speed_kmh > 0),

    FOREIGN KEY (origin_id) REFERENCES locations(id)
        ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS route_legs (
    route_id INTEGER NOT NULL,
    seq INTEGER NOT NULL CHECK (seq >= 1),
    from_id INTEGER NOT NULL,
    to_id INTEGER NOT NULL,
    km REAL NOT NULL CHECK (km > 0),
    is_delivery_stop INTEGER NOT NULL DEFAULT 0
        CHECK (is_delivery_stop IN (0, 1)),

    PRIMARY KEY (route_id, seq),

    FOREIGN KEY (route_id) REFERENCES routes(id)
        ON DELETE CASCADE,
    FOREIGN KEY (from_id) REFERENCES locations(id)
        ON DELETE RESTRICT,
    FOREIGN KEY (to_id) REFERENCES locations(id)
        ON DELETE RESTRICT,

    CHECK (from_id != to_id)
);
