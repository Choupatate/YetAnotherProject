import os
import secrets
from pathlib import Path

from flask import Flask


def create_app(test_config=None):
    app = Flask(__name__)

    stories_dir = os.environ.get("STORYBOOK_STORIES_DIR", "./stories")
    password = os.environ.get("STORYBOOK_PASSWORD")
    secret_key = os.environ.get("STORYBOOK_SECRET_KEY")

    app.config.update(
        STORIES_DIR=Path(stories_dir).resolve(),
        PASSWORD=password or "dev",
        SECRET_KEY=secret_key or secrets.token_hex(32),
        DEV_MODE=password is None,
    )

    if test_config:
        app.config.update(test_config)

    app.config["STORIES_DIR"] = Path(app.config["STORIES_DIR"])
    app.config["STORIES_DIR"].mkdir(parents=True, exist_ok=True)

    from . import auth, routes_api, routes_pages

    app.register_blueprint(auth.bp)
    app.register_blueprint(routes_pages.bp)
    app.register_blueprint(routes_api.bp)

    return app
