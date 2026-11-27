"""Flask REST endpoints for point-to-point, multi-stop, and saved routes."""

from flask import Blueprint, current_app, jsonify

from backend.api.common import (
    parse_json_object,
    register_error_handlers,
    validate_id,
)
from backend.services.route_service import RouteService

route_bp = Blueprint("routes", __name__, url_prefix="/api")
register_error_handlers(route_bp)


def _get_route_service() -> RouteService:
    return RouteService(db_path=current_app.config.get("DB_PATH"))


@route_bp.post("/routes/point")
def plan_point_route():
    payload = parse_json_object()
    route = _get_route_service().plan_point_route(payload)
    status = 201 if route["id"] is not None else 200
    return jsonify({"route": route}), status


@route_bp.post("/routes/run")
def plan_delivery_run():
    payload = parse_json_object()
    route = _get_route_service().plan_delivery_run(payload)
    status = 201 if route["id"] is not None else 200
    return jsonify({"route": route}), status


@route_bp.get("/routes")
def list_routes():
    routes = _get_route_service().list_routes()
    return jsonify({"routes": routes}), 200


@route_bp.post("/routes")
def save_route():
    payload = parse_json_object()
    route = _get_route_service().save_route(payload)
    return jsonify({"route": route}), 201


@route_bp.get("/routes/<int:route_id>")
def get_route(route_id: int):
    validate_id(route_id, "route_id")
    route = _get_route_service().get_route(route_id)
    return jsonify({"route": route}), 200
