"""Flask REST endpoints for managing locations, roads, and network validation."""

from typing import Any

from flask import Blueprint, current_app, jsonify, request

from backend.algorithms.graph import build_graph
from backend.algorithms.network_validation import validate_network
from backend.api.common import (
    parse_json_object,
    register_error_handlers,
    validate_id,
)
from backend.services.network_service import NetworkService, ValidationError

network_bp = Blueprint("network", __name__, url_prefix="/api")
register_error_handlers(network_bp)


def _get_service() -> NetworkService:
    return NetworkService(db_path=current_app.config.get("DB_PATH"))


def _parse_optional_int_param(name: str) -> int | None:
    raw = request.args.get(name)
    if raw is None or raw.strip() == "":
        return None
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValidationError(
            f"Query parameter '{name}' must be an integer.",
            fields={name: "Must be a positive integer."},
        ) from exc
    return validate_id(value, name)


def _parse_optional_bool_param(name: str) -> int | None:
    raw = request.args.get(name)
    if raw is None or raw.strip() == "":
        return None
    normalized = raw.strip().lower()
    if normalized in {"1", "true"}:
        return 1
    if normalized in {"0", "false"}:
        return 0
    raise ValidationError(
        f"Query parameter '{name}' must be true/false or 0/1.",
        fields={name: "Must be true/false or 0/1."},
    )


def _serialize_location(location: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": location["id"],
        "code": location["code"],
        "name": location["name"],
        "kind": location["kind"],
        "x": float(location["x"]),
        "y": float(location["y"]),
    }


def _serialize_road(road: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": road["id"],
        "from_id": road["from_id"],
        "to_id": road["to_id"],
        "distance_km": float(road["distance_km"]),
        "is_one_way": bool(road["is_one_way"]),
        "is_closed": bool(road["is_closed"]),
    }


@network_bp.get("/health")
def health_check():
    return jsonify({"status": "ok"}), 200


@network_bp.get("/locations")
def list_locations():
    search = request.args.get("search")
    if search is None:
        search = request.args.get("q")
    kind = request.args.get("kind")

    locations = _get_service().list_locations(search=search, kind=kind)
    return jsonify({"locations": [_serialize_location(loc) for loc in locations]}), 200


@network_bp.post("/locations")
def create_location():
    payload = parse_json_object()
    created = _get_service().create_location(payload)
    return jsonify({"location": _serialize_location(created)}), 201


@network_bp.patch("/locations/<int:location_id>")
def update_location(location_id: int):
    validate_id(location_id, "location_id")
    payload = parse_json_object()
    updated = _get_service().update_location(location_id, payload)
    return jsonify({"location": _serialize_location(updated)}), 200


@network_bp.delete("/locations/<int:location_id>")
def delete_location(location_id: int):
    validate_id(location_id, "location_id")
    _get_service().delete_location(location_id)
    return jsonify({"deleted": True, "id": location_id}), 200


@network_bp.get("/roads")
def list_roads():
    location_id = _parse_optional_int_param("location_id")
    is_closed = _parse_optional_bool_param("is_closed")
    is_one_way = _parse_optional_bool_param("is_one_way")

    roads = _get_service().list_roads(
        location_id=location_id,
        is_closed=is_closed,
        is_one_way=is_one_way,
    )
    return jsonify({"roads": [_serialize_road(road) for road in roads]}), 200


@network_bp.post("/roads")
def create_road():
    payload = parse_json_object()
    created = _get_service().create_road(payload)
    return jsonify({"road": _serialize_road(created)}), 201


@network_bp.patch("/roads/<int:road_id>")
def update_road(road_id: int):
    validate_id(road_id, "road_id")
    payload = parse_json_object()
    updated = _get_service().update_road(road_id, payload)
    return jsonify({"road": _serialize_road(updated)}), 200


@network_bp.delete("/roads/<int:road_id>")
def delete_road(road_id: int):
    validate_id(road_id, "road_id")
    _get_service().delete_road(road_id)
    return jsonify({"deleted": True, "id": road_id}), 200


@network_bp.get("/network/validation")
def network_validation():
    depot_id = _parse_optional_int_param("depot_id")
    service = _get_service()
    locations = service.list_locations()
    if not any(loc["id"] == depot_id and loc["kind"] == "DEPOT" for loc in locations):
        raise ValidationError(
            "Select an existing depot.",
            fields={"depot_id": "Select an existing depot."},
        )
    return jsonify(
        validate_network(build_graph(locations, service.list_roads()), depot_id)
    )
