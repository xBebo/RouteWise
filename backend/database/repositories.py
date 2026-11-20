"""SQLite repositories for locations and roads."""

from contextlib import closing
from pathlib import Path
from typing import Any

from .connection import get_connection


def _escape_like(term: str) -> str:
    """Escape SQL LIKE wildcards so literal % and _ match literally."""
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class LocationRepository:
    """Data-access layer for the ``locations`` table."""

    def __init__(self, db_path: Path | str | None = None) -> None:
        self._db_path = db_path

    def list_all(
        self,
        *,
        search: str | None = None,
        kind: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return locations optionally filtered by search text and kind."""
        clauses: list[str] = []
        params: list[Any] = []

        if kind is not None:
            clauses.append("kind = ?")
            params.append(kind)

        if search is not None and search != "":
            pattern = f"%{_escape_like(search)}%"
            clauses.append("(code LIKE ? ESCAPE '\\' OR name LIKE ? ESCAPE '\\')")
            params.extend([pattern, pattern])

        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = (
            "SELECT id, code, name, kind, x, y "
            f"FROM locations {where_sql} ORDER BY id ASC"
        )

        with closing(get_connection(self._db_path)) as conn:
            rows = conn.execute(sql, params).fetchall()
            return [dict(row) for row in rows]

    def get_by_id(self, location_id: int) -> dict[str, Any] | None:
        """Return a single location by primary key, or None."""
        sql = "SELECT id, code, name, kind, x, y FROM locations WHERE id = ?"
        with closing(get_connection(self._db_path)) as conn:
            row = conn.execute(sql, (location_id,)).fetchone()
            return dict(row) if row is not None else None

    def get_by_code(self, code: str) -> dict[str, Any] | None:
        """Return a location matching ``code`` (case-insensitive), or None."""
        sql = (
            "SELECT id, code, name, kind, x, y "
            "FROM locations WHERE code = ? COLLATE NOCASE"
        )
        with closing(get_connection(self._db_path)) as conn:
            row = conn.execute(sql, (code,)).fetchone()
            return dict(row) if row is not None else None

    def create(
        self,
        *,
        code: str,
        name: str,
        kind: str,
        x: float,
        y: float,
    ) -> dict[str, Any]:
        """Insert a new location and return the stored record."""
        sql = (
            "INSERT INTO locations (code, name, kind, x, y) "
            "VALUES (?, ?, ?, ?, ?)"
        )
        with closing(get_connection(self._db_path)) as conn:
            with conn:
                cursor = conn.execute(sql, (code, name, kind, x, y))
                new_id = cursor.lastrowid
            row = conn.execute(
                "SELECT id, code, name, kind, x, y FROM locations WHERE id = ?",
                (new_id,),
            ).fetchone()
            return dict(row)

    def update(
        self,
        location_id: int,
        *,
        code: str,
        name: str,
        kind: str,
        x: float,
        y: float,
    ) -> dict[str, Any] | None:
        """Update an existing location and return the updated record."""
        sql = (
            "UPDATE locations "
            "SET code = ?, name = ?, kind = ?, x = ?, y = ? "
            "WHERE id = ?"
        )
        with closing(get_connection(self._db_path)) as conn:
            with conn:
                cursor = conn.execute(sql, (code, name, kind, x, y, location_id))
                if cursor.rowcount == 0:
                    return None
            row = conn.execute(
                "SELECT id, code, name, kind, x, y FROM locations WHERE id = ?",
                (location_id,),
            ).fetchone()
            return dict(row) if row is not None else None

    def is_referenced(self, location_id: int) -> bool:
        """Return True if the location is referenced by any road or saved route."""
        with closing(get_connection(self._db_path)) as conn:
            road_ref = conn.execute(
                "SELECT 1 FROM roads WHERE from_id = ? OR to_id = ? LIMIT 1",
                (location_id, location_id),
            ).fetchone()
            if road_ref is not None:
                return True

            route_ref = conn.execute(
                "SELECT 1 FROM routes WHERE origin_id = ? LIMIT 1",
                (location_id,),
            ).fetchone()
            if route_ref is not None:
                return True

            leg_ref = conn.execute(
                "SELECT 1 FROM route_legs WHERE from_id = ? OR to_id = ? LIMIT 1",
                (location_id, location_id),
            ).fetchone()
            return leg_ref is not None

    def delete(self, location_id: int) -> bool:
        """Delete a location by id and return True if a row was removed."""
        with closing(get_connection(self._db_path)) as conn:
            with conn:
                cursor = conn.execute(
                    "DELETE FROM locations WHERE id = ?",
                    (location_id,),
                )
                return cursor.rowcount > 0


class RoadRepository:
    """Data-access layer for the ``roads`` table."""

    def __init__(self, db_path: Path | str | None = None) -> None:
        self._db_path = db_path

    def list_all(
        self,
        *,
        location_id: int | None = None,
        is_closed: int | None = None,
        is_one_way: int | None = None,
    ) -> list[dict[str, Any]]:
        """Return roads optionally filtered by endpoint or road flags."""
        clauses: list[str] = []
        params: list[Any] = []

        if location_id is not None:
            clauses.append("(from_id = ? OR to_id = ?)")
            params.extend([location_id, location_id])

        if is_closed is not None:
            clauses.append("is_closed = ?")
            params.append(is_closed)

        if is_one_way is not None:
            clauses.append("is_one_way = ?")
            params.append(is_one_way)

        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = (
            "SELECT id, from_id, to_id, distance_km, is_one_way, is_closed "
            f"FROM roads {where_sql} ORDER BY id ASC"
        )

        with closing(get_connection(self._db_path)) as conn:
            rows = conn.execute(sql, params).fetchall()
            return [dict(row) for row in rows]

    def get_by_id(self, road_id: int) -> dict[str, Any] | None:
        """Return a single road by primary key, or None."""
        sql = (
            "SELECT id, from_id, to_id, distance_km, is_one_way, is_closed "
            "FROM roads WHERE id = ?"
        )
        with closing(get_connection(self._db_path)) as conn:
            row = conn.execute(sql, (road_id,)).fetchone()
            return dict(row) if row is not None else None

    def find_between(
        self,
        location_a: int,
        location_b: int,
        *,
        exclude_road_id: int | None = None,
    ) -> list[dict[str, Any]]:
        """Return existing roads connecting ``location_a`` and ``location_b``."""
        sql = (
            "SELECT id, from_id, to_id, distance_km, is_one_way, is_closed "
            "FROM roads "
            "WHERE ((from_id = ? AND to_id = ?) OR (from_id = ? AND to_id = ?))"
        )
        params: list[Any] = [location_a, location_b, location_b, location_a]

        if exclude_road_id is not None:
            sql += " AND id != ?"
            params.append(exclude_road_id)

        with closing(get_connection(self._db_path)) as conn:
            rows = conn.execute(sql, params).fetchall()
            return [dict(row) for row in rows]

    def create(
        self,
        *,
        from_id: int,
        to_id: int,
        distance_km: float,
        is_one_way: int,
        is_closed: int,
    ) -> dict[str, Any]:
        """Insert a new road and return the stored record."""
        sql = (
            "INSERT INTO roads (from_id, to_id, distance_km, is_one_way, is_closed) "
            "VALUES (?, ?, ?, ?, ?)"
        )
        with closing(get_connection(self._db_path)) as conn:
            with conn:
                cursor = conn.execute(
                    sql,
                    (from_id, to_id, distance_km, is_one_way, is_closed),
                )
                new_id = cursor.lastrowid
            row = conn.execute(
                "SELECT id, from_id, to_id, distance_km, is_one_way, is_closed "
                "FROM roads WHERE id = ?",
                (new_id,),
            ).fetchone()
            return dict(row)

    def update(
        self,
        road_id: int,
        *,
        from_id: int,
        to_id: int,
        distance_km: float,
        is_one_way: int,
        is_closed: int,
    ) -> dict[str, Any] | None:
        """Update an existing road and return the updated record."""
        sql = (
            "UPDATE roads "
            "SET from_id = ?, to_id = ?, distance_km = ?, is_one_way = ?, is_closed = ? "
            "WHERE id = ?"
        )
        with closing(get_connection(self._db_path)) as conn:
            with conn:
                cursor = conn.execute(
                    sql,
                    (from_id, to_id, distance_km, is_one_way, is_closed, road_id),
                )
                if cursor.rowcount == 0:
                    return None
            row = conn.execute(
                "SELECT id, from_id, to_id, distance_km, is_one_way, is_closed "
                "FROM roads WHERE id = ?",
                (road_id,),
            ).fetchone()
            return dict(row) if row is not None else None

    def delete(self, road_id: int) -> bool:
        """Delete a road by id and return True if a row was removed."""
        with closing(get_connection(self._db_path)) as conn:
            with conn:
                cursor = conn.execute(
                    "DELETE FROM roads WHERE id = ?",
                    (road_id,),
                )
                return cursor.rowcount > 0
