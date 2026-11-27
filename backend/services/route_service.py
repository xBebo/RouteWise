"""Route planning and saved-route history service."""

import math
from pathlib import Path
from typing import Any

from backend.algorithms.dijkstra import shortest_path
from backend.algorithms.graph import Graph, build_graph, get_neighbors
from backend.algorithms.nearest_neighbor import plan_route
from backend.database.connection import MAX_SQLITE_ID
from backend.database.repositories import (
    LocationRepository,
    RoadRepository,
    RouteRepository,
)
from backend.services.network_service import (
    NotFoundError,
    ServiceError,
    ValidationError,
    _require_flag,
    _require_positive_int,
)

VALID_ROUTE_MODES = ("POINT", "RUN")
HEURISTIC_LABEL = "heuristic, not guaranteed optimal"
OPTIMAL_LABEL = "Shortest path (Dijkstra)"


class NoRouteError(ServiceError):
    """Raised when no valid open path reaches the requested target or stops."""

    def __init__(
        self,
        message: str,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.details = details or {}


def _require_positive_speed(
    value: Any,
    field: str,
    errors: dict[str, str],
) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        errors[field] = f"{field} must be a positive number."
        return None
    try:
        speed = float(value)
    except OverflowError:
        errors[field] = f"{field} is out of numeric range."
        return None
    if not math.isfinite(speed) or speed <= 0:
        errors[field] = f"{field} must be greater than 0."
        return None
    return speed


def _compute_eta(total_km: float, avg_speed_kmh: float) -> tuple[float, float]:
    """Compute rounded ETA values or raise field-level ValidationError on overflow."""
    try:
        raw_hours = total_km / avg_speed_kmh
        raw_minutes = raw_hours * 60.0
        if not (math.isfinite(raw_hours) and math.isfinite(raw_minutes)):
            raise OverflowError("non-finite ETA")
        eta_hours = round(raw_hours, 4)
        eta_minutes = round(raw_minutes, 2)
    except OverflowError as exc:
        raise ValidationError(
            "Estimated travel time is out of numeric range for the given speed.",
            fields={
                "avg_speed_kmh": (
                    "avg_speed_kmh is too small for the route distance (ETA is not finite)."
                )
            },
        ) from exc
    if not (math.isfinite(eta_hours) and math.isfinite(eta_minutes)):
        raise ValidationError(
            "Estimated travel time is out of numeric range for the given speed.",
            fields={
                "avg_speed_kmh": (
                    "avg_speed_kmh is too small for the route distance (ETA is not finite)."
                )
            },
        )
    return eta_hours, eta_minutes


def _edge_distance(graph: Graph, u: int, v: int) -> float:
    for neighbor, weight in get_neighbors(graph, u):
        if neighbor == v:
            return float(weight)
    raise ValueError(f"Missing edge {u} -> {v} in graph.")


def _enrich_legs(
    raw_steps: list[dict[str, Any]],
    loc_by_id: dict[int, dict[str, Any]],
) -> tuple[list[dict[str, Any]], float]:
    """Attach location metadata and cumulative distances to road-step legs."""
    cumulative = 0.0
    enriched: list[dict[str, Any]] = []
    for seq, step in enumerate(raw_steps, start=1):
        km = float(step["km"])
        cumulative = cumulative + km
        origin = loc_by_id[step["from_id"]]
        dest = loc_by_id[step["to_id"]]
        enriched.append(
            {
                "seq": seq,
                "from_id": step["from_id"],
                "from_code": origin["code"],
                "from_name": origin["name"],
                "to_id": step["to_id"],
                "to_code": dest["code"],
                "to_name": dest["name"],
                "km": km,
                "cumulative_km": cumulative,
                "is_delivery_stop": bool(step["is_delivery_stop"]),
            }
        )
    return enriched, cumulative


def _format_route_payload(
    *,
    route_id: int | None,
    created_at: str | None,
    mode: str,
    origin: dict[str, Any],
    total_km: float,
    avg_speed_kmh: float,
    legs: list[dict[str, Any]],
    eta_hours: float | None = None,
    eta_minutes: float | None = None,
    unreachable_stops: list[int] | None = None,
    returned_to_depot: bool = False,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    if eta_hours is None or eta_minutes is None:
        eta_hours, eta_minutes = _compute_eta(total_km, avg_speed_kmh)
    path = [origin["id"]] + [leg["to_id"] for leg in legs]
    ordered_stops = [leg["to_id"] for leg in legs if leg["is_delivery_stop"]]

    payload: dict[str, Any] = {
        "id": route_id,
        "created_at": created_at,
        "mode": mode,
        "origin_id": origin["id"],
        "origin_code": origin["code"],
        "origin_name": origin["name"],
        "destination_id": path[-1],
        "total_km": float(total_km),
        "avg_speed_kmh": float(avg_speed_kmh),
        "eta_minutes": eta_minutes,
        "eta_hours": eta_hours,
        "path": path,
        "ordered_stops": ordered_stops,
        "returned_to_depot": bool(returned_to_depot),
        "method": "optimal" if mode == "POINT" else "heuristic",
        "label": OPTIMAL_LABEL if mode == "POINT" else HEURISTIC_LABEL,
        "warnings": list(warnings or []),
        "legs": legs,
    }
    if unreachable_stops is not None:
        payload["unreachable_stops"] = list(unreachable_stops)
    return payload


def _hydrate_saved_route(saved: dict[str, Any]) -> dict[str, Any]:
    """Build API route payload from a persisted route and leg snapshots."""
    cumulative = 0.0
    legs: list[dict[str, Any]] = []
    for leg in saved["legs"]:
        km = float(leg["km"])
        cumulative = cumulative + km
        legs.append(
            {
                "seq": leg["seq"],
                "from_id": leg["from_id"],
                "from_code": leg["from_code"],
                "from_name": leg["from_name"],
                "to_id": leg["to_id"],
                "to_code": leg["to_code"],
                "to_name": leg["to_name"],
                "km": km,
                "cumulative_km": cumulative,
                "is_delivery_stop": bool(leg["is_delivery_stop"]),
            }
        )

    returned_to_depot = (
        saved["mode"] == "RUN"
        and bool(legs)
        and legs[-1]["to_id"] == saved["origin_id"]
        and not legs[-1]["is_delivery_stop"]
    )
    return _format_route_payload(
        route_id=saved["id"],
        created_at=saved["created_at"],
        mode=saved["mode"],
        origin={
            "id": saved["origin_id"],
            "code": saved["origin_code"],
            "name": saved["origin_name"],
        },
        total_km=float(saved["total_km"]),
        avg_speed_kmh=float(saved["avg_speed_kmh"]),
        legs=legs,
        returned_to_depot=returned_to_depot,
    )


class RouteService:
    """Application service for shortest-path, delivery-run, and saved routes."""

    def __init__(
        self,
        db_path: Path | str | None = None,
        *,
        location_repo: LocationRepository | None = None,
        road_repo: RoadRepository | None = None,
        route_repo: RouteRepository | None = None,
    ) -> None:
        self._locations = location_repo or LocationRepository(db_path)
        self._roads = road_repo or RoadRepository(db_path)
        self._routes = route_repo or RouteRepository(db_path)

    def _load_network(
        self,
    ) -> tuple[Graph, dict[int, dict[str, Any]], dict[int, str]]:
        locations = self._locations.list_all()
        roads = self._roads.list_all()
        graph = build_graph(locations, roads)
        loc_by_id = {loc["id"]: loc for loc in locations}
        codes = {loc["id"]: loc["code"] for loc in locations}
        return graph, loc_by_id, codes

    def plan_point_route(
        self,
        data: dict[str, Any],
        *,
        force_save: bool = False,
    ) -> dict[str, Any]:
        """Compute (and optionally save) the shortest point-to-point route."""
        errors: dict[str, str] = {}
        origin_id = _require_positive_int(data.get("origin_id"), "origin_id", errors)
        dest_id = _require_positive_int(
            data.get("destination_id"), "destination_id", errors
        )
        speed = _require_positive_speed(
            data.get("avg_speed_kmh"), "avg_speed_kmh", errors
        )
        save_flag = (
            1
            if force_save
            else _require_flag(data.get("save", 0), "save", errors)
        )
        if errors:
            raise ValidationError("Invalid point-to-point route request.", fields=errors)

        assert origin_id is not None and dest_id is not None
        assert speed is not None and save_flag is not None

        graph, loc_by_id, codes = self._load_network()
        if origin_id not in loc_by_id:
            raise ValidationError(
                f"Origin location {origin_id} does not exist.",
                fields={"origin_id": "Location does not exist."},
            )
        if dest_id not in loc_by_id:
            raise ValidationError(
                f"Destination location {dest_id} does not exist.",
                fields={"destination_id": "Location does not exist."},
            )

        result = shortest_path(graph, origin_id, dest_id, codes=codes)
        if not result["found"]:
            raise NoRouteError(
                f"No route exists from {loc_by_id[origin_id]['code']} to "
                f"{loc_by_id[dest_id]['code']}.",
                details={"reachable": False, "path": [], "legs": []},
            )

        path: list[int] = result["path"]
        raw_steps = [
            {
                "from_id": u,
                "to_id": v,
                "km": _edge_distance(graph, u, v),
                "is_delivery_stop": False,
            }
            for u, v in zip(path, path[1:])
        ]
        legs, total_km = _enrich_legs(raw_steps, loc_by_id)
        eta_hours, eta_minutes = _compute_eta(total_km, speed)

        if save_flag:
            saved = self._routes.create(
                mode="POINT",
                origin_id=origin_id,
                total_km=total_km,
                avg_speed_kmh=speed,
                legs=legs,
            )
            return _hydrate_saved_route(saved)

        return _format_route_payload(
            route_id=None,
            created_at=None,
            mode="POINT",
            origin=loc_by_id[origin_id],
            total_km=total_km,
            avg_speed_kmh=speed,
            legs=legs,
            eta_hours=eta_hours,
            eta_minutes=eta_minutes,
            unreachable_stops=[],
        )

    def plan_delivery_run(
        self,
        data: dict[str, Any],
        *,
        force_save: bool = False,
    ) -> dict[str, Any]:
        """Compute (and optionally save) a multi-stop nearest-neighbor delivery run."""
        errors: dict[str, str] = {}
        depot_id = _require_positive_int(data.get("depot_id"), "depot_id", errors)
        speed = _require_positive_speed(
            data.get("avg_speed_kmh"), "avg_speed_kmh", errors
        )
        return_flag = _require_flag(
            data.get("return_to_depot", 0), "return_to_depot", errors
        )
        save_flag = (
            1
            if force_save
            else _require_flag(data.get("save", 0), "save", errors)
        )

        raw_stops = data.get("stop_ids")
        stop_ids: list[int] = []
        if not isinstance(raw_stops, list) or not raw_stops:
            errors["stop_ids"] = "stop_ids must be a non-empty list of location IDs."
        else:
            for item in raw_stops:
                if (
                    isinstance(item, bool)
                    or not isinstance(item, int)
                    or not 1 <= item <= MAX_SQLITE_ID
                ):
                    errors["stop_ids"] = (
                        "All stop_ids must be positive SQLite integers."
                    )
                    break
                stop_ids.append(item)

        if errors:
            raise ValidationError("Invalid delivery run request.", fields=errors)

        assert depot_id is not None and speed is not None
        assert return_flag is not None and save_flag is not None

        graph, loc_by_id, codes = self._load_network()
        if depot_id not in loc_by_id:
            raise ValidationError(
                f"Depot {depot_id} does not exist.",
                fields={"depot_id": "Location does not exist."},
            )
        if loc_by_id[depot_id]["kind"] != "DEPOT":
            raise ValidationError(
                "Selected depot_id must refer to a location with kind DEPOT.",
                fields={"depot_id": "Origin must be a DEPOT."},
            )

        missing_stops = [sid for sid in stop_ids if sid not in loc_by_id]
        if missing_stops:
            raise ValidationError(
                f"Unknown stop location ID(s): {missing_stops}.",
                fields={"stop_ids": "All stop_ids must refer to existing locations."},
            )

        try:
            run_result = plan_route(
                graph,
                depot_id,
                stop_ids,
                return_to_depot=bool(return_flag),
                codes=codes,
            )
        except ValueError as exc:
            raise ValidationError(str(exc), fields={"stop_ids": str(exc)}) from exc

        if not run_result["ordered_stops"]:
            raise NoRouteError(
                "No route exists to any of the selected delivery stops.",
                details={
                    "reachable": False,
                    "ordered_stops": [],
                    "unreachable_stops": run_result["unreachable_stops"],
                    "warnings": run_result["warnings"],
                    "legs": [],
                },
            )

        raw_steps: list[dict[str, Any]] = []
        segments = run_result["legs"]
        returned_to_depot = bool(run_result["returned_to_depot"])
        for seg_idx, segment in enumerate(segments):
            seg_path: list[int] = segment["path"]
            is_return_segment = (
                returned_to_depot
                and seg_idx == len(segments) - 1
                and segment["to_id"] == depot_id
            )
            step_pairs = list(zip(seg_path, seg_path[1:]))
            for step_idx, (u, v) in enumerate(step_pairs):
                is_delivery_stop = (not is_return_segment) and (
                    step_idx == len(step_pairs) - 1
                )
                raw_steps.append(
                    {
                        "from_id": u,
                        "to_id": v,
                        "km": _edge_distance(graph, u, v),
                        "is_delivery_stop": is_delivery_stop,
                    }
                )

        legs, total_km = _enrich_legs(raw_steps, loc_by_id)
        eta_hours, eta_minutes = _compute_eta(total_km, speed)

        if save_flag:
            saved = self._routes.create(
                mode="RUN",
                origin_id=depot_id,
                total_km=total_km,
                avg_speed_kmh=speed,
                legs=legs,
            )
            payload = _hydrate_saved_route(saved)
            payload["unreachable_stops"] = run_result["unreachable_stops"]
            payload["warnings"] = run_result["warnings"]
            return payload

        return _format_route_payload(
            route_id=None,
            created_at=None,
            mode="RUN",
            origin=loc_by_id[depot_id],
            total_km=total_km,
            avg_speed_kmh=speed,
            legs=legs,
            eta_hours=eta_hours,
            eta_minutes=eta_minutes,
            unreachable_stops=run_result["unreachable_stops"],
            returned_to_depot=returned_to_depot,
            warnings=run_result["warnings"],
        )

    def save_route(self, data: dict[str, Any]) -> dict[str, Any]:
        """Compute and atomically save a POINT or RUN route."""
        mode = data.get("mode")
        if not isinstance(mode, str) or mode.strip() not in VALID_ROUTE_MODES:
            raise ValidationError(
                "mode must be 'POINT' or 'RUN'.",
                fields={"mode": "mode must be 'POINT' or 'RUN'."},
            )
        normalized_mode = mode.strip()
        if normalized_mode == "POINT":
            return self.plan_point_route(data, force_save=True)
        return self.plan_delivery_run(data, force_save=True)

    def list_routes(self) -> list[dict[str, Any]]:
        """Return saved routes history (newest first)."""
        return [_hydrate_saved_route(row) for row in self._routes.list_all()]

    def get_route(self, route_id: int) -> dict[str, Any]:
        """Return a saved route with all leg snapshots or raise NotFoundError."""
        saved = self._routes.get_by_id(route_id)
        if saved is None:
            raise NotFoundError(f"Route {route_id} not found.")
        return _hydrate_saved_route(saved)
