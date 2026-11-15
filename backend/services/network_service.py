"""Business logic and validation for managing locations and roads."""

import math
import sqlite3
from pathlib import Path
from typing import Any

from backend.database.repositories import LocationRepository, RoadRepository

VALID_LOCATION_KINDS = ("DEPOT", "HUB", "CUSTOMER")
MIN_COORDINATE = 0.0
MAX_COORDINATE = 1000.0
MAX_DISTANCE_KM = 500.0


class ServiceError(Exception):
    """Base exception for network service failures."""

    def __init__(
        self,
        message: str,
        *,
        fields: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.fields = fields or {}


class ValidationError(ServiceError):
    """Raised when input values fail domain or schema validation."""


class NotFoundError(ServiceError):
    """Raised when a requested resource does not exist."""


class ConflictError(ServiceError):
    """Raised when an operation violates uniqueness or reference rules."""


def _require_text(
    value: Any,
    field: str,
    errors: dict[str, str],
) -> str | None:
    if not isinstance(value, str) or not value.strip():
        errors[field] = f"{field} must be a non-empty string."
        return None
    return value.strip()


def _require_kind(value: Any, errors: dict[str, str]) -> str | None:
    if not isinstance(value, str) or value.strip() not in VALID_LOCATION_KINDS:
        errors["kind"] = (
            f"kind must be one of {', '.join(VALID_LOCATION_KINDS)}."
        )
        return None
    return value.strip()


def _require_number(
    value: Any,
    field: str,
    minimum: float,
    maximum: float,
    errors: dict[str, str],
    *,
    strict_min: bool = False,
) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        errors[field] = f"{field} must be a finite number."
        return None
    try:
        number = float(value)
    except OverflowError:
        errors[field] = f"{field} is out of numeric range."
        return None
    if not math.isfinite(number):
        errors[field] = f"{field} must be a finite number."
        return None
    too_small = number <= minimum if strict_min else number < minimum
    if too_small or number > maximum:
        op = ">" if strict_min else ">="
        errors[field] = f"{field} must be {op} {minimum:g} and <= {maximum:g}."
        return None
    return number


def _require_positive_int(
    value: Any,
    field: str,
    errors: dict[str, str],
) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        errors[field] = f"{field} must be a positive integer."
        return None
    return value


def _require_flag(
    value: Any,
    field: str,
    errors: dict[str, str],
) -> int | None:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int) and value in (0, 1):
        return value
    errors[field] = f"{field} must be a boolean or 0/1."
    return None


class NetworkService:
    """Application service coordinating locations and roads."""

    def __init__(
        self,
        db_path: Path | str | None = None,
        *,
        location_repo: LocationRepository | None = None,
        road_repo: RoadRepository | None = None,
    ) -> None:
        self._locations = location_repo or LocationRepository(db_path)
        self._roads = road_repo or RoadRepository(db_path)

    # ------------------------------------------------------------------
    # Locations
    # ------------------------------------------------------------------

    def list_locations(
        self,
        *,
        search: str | None = None,
        kind: str | None = None,
    ) -> list[dict[str, Any]]:
        """List locations with optional search text and kind filter."""
        normalized_kind: str | None = None
        if kind is not None and kind.strip() != "":
            errors: dict[str, str] = {}
            normalized_kind = _require_kind(kind, errors)
            if errors:
                raise ValidationError("Invalid location filter.", fields=errors)

        normalized_search = search.strip() if isinstance(search, str) else None
        return self._locations.list_all(
            search=normalized_search or None,
            kind=normalized_kind,
        )

    def get_location(self, location_id: int) -> dict[str, Any]:
        """Return a single location or raise NotFoundError."""
        location = self._locations.get_by_id(location_id)
        if location is None:
            raise NotFoundError(f"Location {location_id} not found.")
        return location

    def create_location(self, data: dict[str, Any]) -> dict[str, Any]:
        """Validate and store a new location."""
        validated = self._validate_location_fields(data)
        if self._locations.get_by_code(validated["code"]) is not None:
            raise ConflictError(
                f"Location code '{validated['code']}' already exists.",
                fields={"code": "Location code must be unique."},
            )
        try:
            return self._locations.create(**validated)
        except sqlite3.IntegrityError as exc:
            raise ConflictError(f"Could not create location: {exc}") from exc

    def update_location(
        self,
        location_id: int,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        """Partially update an existing location after validation."""
        existing = self.get_location(location_id)
        updatable_keys = {"code", "name", "kind", "x", "y"}
        if not any(key in data for key in updatable_keys):
            raise ValidationError("No valid location fields provided for update.")

        merged = {
            "code": data.get("code", existing["code"]),
            "name": data.get("name", existing["name"]),
            "kind": data.get("kind", existing["kind"]),
            "x": data.get("x", existing["x"]),
            "y": data.get("y", existing["y"]),
        }
        validated = self._validate_location_fields(merged)

        other = self._locations.get_by_code(validated["code"])
        if other is not None and other["id"] != location_id:
            raise ConflictError(
                f"Location code '{validated['code']}' already exists.",
                fields={"code": "Location code must be unique."},
            )

        try:
            updated = self._locations.update(location_id, **validated)
        except sqlite3.IntegrityError as exc:
            raise ConflictError(f"Could not update location: {exc}") from exc

        if updated is None:
            raise NotFoundError(f"Location {location_id} not found.")
        return updated

    def delete_location(self, location_id: int) -> None:
        """Delete a location unless referenced by roads or saved routes."""
        self.get_location(location_id)
        if self._locations.is_referenced(location_id):
            raise ConflictError(
                "Cannot delete location because it is referenced by roads or saved routes."
            )
        try:
            deleted = self._locations.delete(location_id)
        except sqlite3.IntegrityError as exc:
            raise ConflictError(
                "Cannot delete location because it is referenced by roads or saved routes."
            ) from exc
        if not deleted:
            raise NotFoundError(f"Location {location_id} not found.")

    def _validate_location_fields(self, data: dict[str, Any]) -> dict[str, Any]:
        errors: dict[str, str] = {}
        code = _require_text(data.get("code"), "code", errors)
        name = _require_text(data.get("name"), "name", errors)
        kind = _require_kind(data.get("kind"), errors)
        x = _require_number(
            data.get("x"), "x", MIN_COORDINATE, MAX_COORDINATE, errors
        )
        y = _require_number(
            data.get("y"), "y", MIN_COORDINATE, MAX_COORDINATE, errors
        )

        if errors:
            raise ValidationError("Invalid location data.", fields=errors)

        return {
            "code": code,
            "name": name,
            "kind": kind,
            "x": x,
            "y": y,
        }

    # ------------------------------------------------------------------
    # Roads
    # ------------------------------------------------------------------

    def list_roads(
        self,
        *,
        location_id: int | None = None,
        is_closed: int | None = None,
        is_one_way: int | None = None,
    ) -> list[dict[str, Any]]:
        """List roads with optional endpoint and status filters."""
        return self._roads.list_all(
            location_id=location_id,
            is_closed=is_closed,
            is_one_way=is_one_way,
        )

    def get_road(self, road_id: int) -> dict[str, Any]:
        """Return a single road or raise NotFoundError."""
        road = self._roads.get_by_id(road_id)
        if road is None:
            raise NotFoundError(f"Road {road_id} not found.")
        return road

    def create_road(self, data: dict[str, Any]) -> dict[str, Any]:
        """Validate, normalize direction, and store a new road."""
        validated = self._validate_and_prepare_road(data)
        try:
            return self._roads.create(**validated)
        except sqlite3.IntegrityError as exc:
            raise ConflictError(f"Could not create road: {exc}") from exc

    def update_road(
        self,
        road_id: int,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        """Partially update an existing road after validation."""
        existing = self.get_road(road_id)
        updatable_keys = {
            "from_id",
            "to_id",
            "distance_km",
            "is_one_way",
            "is_closed",
        }
        if not any(key in data for key in updatable_keys):
            raise ValidationError("No valid road fields provided for update.")

        merged = {
            "from_id": data.get("from_id", existing["from_id"]),
            "to_id": data.get("to_id", existing["to_id"]),
            "distance_km": data.get("distance_km", existing["distance_km"]),
            "is_one_way": data.get("is_one_way", existing["is_one_way"]),
            "is_closed": data.get("is_closed", existing["is_closed"]),
        }
        validated = self._validate_and_prepare_road(
            merged,
            exclude_road_id=road_id,
        )

        try:
            updated = self._roads.update(road_id, **validated)
        except sqlite3.IntegrityError as exc:
            raise ConflictError(f"Could not update road: {exc}") from exc

        if updated is None:
            raise NotFoundError(f"Road {road_id} not found.")
        return updated

    def delete_road(self, road_id: int) -> None:
        """Delete a road by id."""
        self.get_road(road_id)
        if not self._roads.delete(road_id):
            raise NotFoundError(f"Road {road_id} not found.")

    def _validate_and_prepare_road(
        self,
        data: dict[str, Any],
        *,
        exclude_road_id: int | None = None,
    ) -> dict[str, Any]:
        errors: dict[str, str] = {}
        from_id = _require_positive_int(data.get("from_id"), "from_id", errors)
        to_id = _require_positive_int(data.get("to_id"), "to_id", errors)
        distance_km = _require_number(
            data.get("distance_km"),
            "distance_km",
            0.0,
            MAX_DISTANCE_KM,
            errors,
            strict_min=True,
        )
        is_one_way = _require_flag(
            data.get("is_one_way", 0), "is_one_way", errors
        )
        is_closed = _require_flag(
            data.get("is_closed", 0), "is_closed", errors
        )

        if errors:
            raise ValidationError("Invalid road data.", fields=errors)

        assert from_id is not None and to_id is not None
        assert distance_km is not None
        assert is_one_way is not None and is_closed is not None

        if from_id == to_id:
            raise ValidationError(
                "A road cannot connect a location to itself.",
                fields={"to_id": "to_id must differ from from_id."},
            )

        if self._locations.get_by_id(from_id) is None:
            raise ValidationError(
                f"Origin location {from_id} does not exist.",
                fields={"from_id": "Location does not exist."},
            )
        if self._locations.get_by_id(to_id) is None:
            raise ValidationError(
                f"Destination location {to_id} does not exist.",
                fields={"to_id": "Location does not exist."},
            )

        # Enforce schema rule: two-way roads are always stored with from_id < to_id.
        if not is_one_way and from_id > to_id:
            from_id, to_id = to_id, from_id

        existing_roads = self._roads.find_between(
            from_id,
            to_id,
            exclude_road_id=exclude_road_id,
        )
        for existing in existing_roads:
            if not is_one_way:
                raise ConflictError(
                    "A road already exists between these two locations."
                )
            if not existing["is_one_way"]:
                raise ConflictError(
                    "A two-way road already exists between these two locations."
                )
            if existing["from_id"] == from_id and existing["to_id"] == to_id:
                raise ConflictError(
                    "A one-way road in this direction already exists."
                )

        return {
            "from_id": from_id,
            "to_id": to_id,
            "distance_km": distance_km,
            "is_one_way": is_one_way,
            "is_closed": is_closed,
        }
