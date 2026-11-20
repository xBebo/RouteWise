import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
DB_PATH = BASE_DIR / "data" / "routewise.db"
MAX_SQLITE_ID = 2**63 - 1
SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def get_connection(db_path: Path | str | None = None) -> sqlite3.Connection:
    """Open a SQLite connection with Row factory and foreign keys enabled."""
    if db_path == ":memory:":
        target: str | Path = ":memory:"
    else:
        target = DB_PATH if db_path is None else Path(db_path)
        target.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(target)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")

    return connection


def initialize_database(db_path: Path | str | None = None) -> None:
    """Create database tables from schema.sql if they do not exist."""
    connection = get_connection(db_path)

    try:
        schema = SCHEMA_PATH.read_text(encoding="utf-8")
        connection.executescript(schema)
        connection.commit()
    finally:
        connection.close()
