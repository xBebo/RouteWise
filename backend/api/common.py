"""Shared Flask request parsing and error-response helpers."""

from typing import Any

from flask import Blueprint, jsonify, request

from backend.database.connection import MAX_SQLITE_ID
from backend.services.network_service import (
    ConflictError,
    NotFoundError,
    ServiceError,
    ValidationError,
)
from backend.services.route_service import NoRouteError


def parse_json_object() -> dict[str, Any]:
    """Parse and require a JSON object request body."""
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        raise ValidationError("Request body must be a valid JSON object.")
    return payload


def validate_id(value: int, name: str) -> int:
    """Validate that an ID falls inside signed 64-bit SQLite integer bounds."""
    if not 1 <= value <= MAX_SQLITE_ID:
        raise ValidationError(
            f"'{name}' must be a positive SQLite integer.",
            fields={name: "Must be a positive integer."},
        )
    return value


def error_response(error: ServiceError, status_code: int):
    """Format a service exception into a consistent JSON error payload."""
    body: dict[str, Any] = {"error": error.message}
    if error.fields:
        body["fields"] = error.fields
    details = getattr(error, "details", None)
    if details:
        body.update(details)
    return jsonify(body), status_code


def register_error_handlers(bp: Blueprint) -> None:
    """Attach domain-exception error handlers onto a Blueprint."""

    @bp.errorhandler(ValidationError)
    def handle_validation_error(error: ValidationError):
        return error_response(error, 400)

    @bp.errorhandler(NotFoundError)
    def handle_not_found_error(error: NotFoundError):
        return error_response(error, 404)

    @bp.errorhandler(ConflictError)
    def handle_conflict_error(error: ConflictError):
        return error_response(error, 409)

    @bp.errorhandler(NoRouteError)
    def handle_no_route_error(error: NoRouteError):
        return error_response(error, 422)
