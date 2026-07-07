import os
import secrets
from datetime import timedelta
from pathlib import Path

from flask import Flask, jsonify, render_template, request

MAX_CONTENT_LENGTH = 32 * 1024 * 1024


def create_app(test_config=None):
    app = Flask(__name__)

    stories_dir = os.environ.get("STORYBOOK_STORIES_DIR", "./stories")
    password = os.environ.get("STORYBOOK_PASSWORD")
    secret_key = os.environ.get("STORYBOOK_SECRET_KEY")
    cookie_secure = os.environ.get("STORYBOOK_COOKIE_SECURE") == "1"

    if password and not secret_key and not test_config:
        raise RuntimeError(
            "STORYBOOK_SECRET_KEY must be set when STORYBOOK_PASSWORD is set. "
            "Generate one with: python -c 'import secrets; print(secrets.token_hex(32))'"
        )

    app.config.update(
        STORIES_DIR=Path(stories_dir).resolve(),
        PASSWORD=password or "dev",
        SECRET_KEY=secret_key or secrets.token_hex(32),
        DEV_MODE=password is None,
        PERMANENT_SESSION_LIFETIME=timedelta(days=90),
        MAX_CONTENT_LENGTH=MAX_CONTENT_LENGTH,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=cookie_secure,
    )

    if test_config:
        app.config.update(test_config)

    app.config["STORIES_DIR"] = Path(app.config["STORIES_DIR"])
    app.config["STORIES_DIR"].mkdir(parents=True, exist_ok=True)

    from . import auth, routes_api, routes_pages

    app.register_blueprint(auth.bp)
    app.register_blueprint(routes_pages.bp)
    app.register_blueprint(routes_api.bp)

    @app.errorhandler(404)
    def not_found(error):
        return render_template("404.html"), 404

    @app.errorhandler(413)
    def too_large(error):
        if request.path.startswith("/api/"):
            return jsonify({"error": "File too large (max 32 MB)."}), 413
        return render_template("404.html"), 413

    return app
