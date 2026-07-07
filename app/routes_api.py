from datetime import date as date_cls

from flask import Blueprint, current_app, jsonify, request

from . import storage
from .auth import login_required

bp = Blueprint("api", __name__, url_prefix="/api")


def _error(message, status):
    response = jsonify({"error": message})
    response.status_code = status
    return response


def _parse_date(value):
    try:
        return date_cls.fromisoformat(value)
    except (TypeError, ValueError):
        return None


@bp.route("/stories", methods=["POST"])
@login_required
def create_story():
    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()
    story_date = _parse_date(data.get("date"))
    markdown = data.get("markdown") or ""

    if not title:
        return _error("Title is required.", 400)
    if story_date is None:
        return _error("Date must be an ISO date (YYYY-MM-DD).", 400)

    story_id = storage.create_story(current_app.config["STORIES_DIR"], title, story_date, markdown)
    return jsonify({"id": story_id})


@bp.route("/stories/<story_id>", methods=["PUT"])
@login_required
def update_story(story_id):
    if not storage.is_valid_story_id(story_id):
        return _error("Story not found.", 404)

    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()
    story_date = _parse_date(data.get("date"))
    markdown = data.get("markdown") or ""
    cover = data.get("cover")

    if not title:
        return _error("Title is required.", 400)
    if story_date is None:
        return _error("Date must be an ISO date (YYYY-MM-DD).", 400)

    try:
        storage.save_story(
            current_app.config["STORIES_DIR"], story_id, title, story_date, markdown, cover=cover
        )
    except FileNotFoundError:
        return _error("Story not found.", 404)

    return jsonify({"id": story_id})


@bp.route("/stories/<story_id>/images", methods=["POST"])
@login_required
def upload_image(story_id):
    if not storage.is_valid_story_id(story_id):
        return _error("Story not found.", 404)

    file_storage = request.files.get("file")
    if file_storage is None or not file_storage.filename:
        return _error("No image file provided.", 400)

    try:
        filename = storage.save_image(current_app.config["STORIES_DIR"], story_id, file_storage)
    except FileNotFoundError:
        return _error("Story not found.", 404)
    except Exception:
        return _error("Could not process image.", 400)

    return jsonify({"filename": filename})
