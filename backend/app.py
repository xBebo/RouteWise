"""Flask application entry point for RouteWise."""

import sys
from pathlib import Path
from typing import Any

from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException

# Support running `python backend/app.py` as well as `python -m backend.app`.
BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from backend.api.network_routes import network_bp
from backend.database.connection import DB_PATH, initialize_database


def create_app(test_config: dict[str, Any] | None = None) -> Flask:
    """Create and configure the Flask application."""
    app = Flask(__name__)
    app.config["DB_PATH"] = DB_PATH

    if test_config is not None:
        app.config.update(test_config)

    initialize_database(app.config["DB_PATH"])
    app.register_blueprint(network_bp)

    @app.after_request
    def add_cors_headers(response):
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = (
            "GET, POST, PATCH, DELETE, OPTIONS"
        )
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        return response

    @app.errorhandler(404)
    def handle_not_found(_error):
        return jsonify({"error": "Endpoint or resource not found."}), 404

    @app.errorhandler(405)
    def handle_method_not_allowed(_error):
        return jsonify({"error": "Method not allowed."}), 405

    @app.errorhandler(Exception)
    def handle_unexpected_error(error: Exception):
        if isinstance(error, HTTPException):
            return jsonify({"error": error.description}), error.code
        app.logger.exception("Unhandled backend error: %s", error)
        return jsonify({"error": "Internal server error."}), 500

    return app


if __name__ == "__main__":
    application = create_app()
    application.run(host="127.0.0.1", port=5000, debug=True)
