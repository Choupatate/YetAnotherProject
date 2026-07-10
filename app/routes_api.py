import zipfile
from datetime import date as date_cls
from pathlib import Path

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


def _validate_author(data):
    """Resolve and validate the optional 'author' field (FEATURES.md F1).

    Returns (author, error_response). `author` is None when absent (create:
    no author; update: leave unchanged) or empty string when explicitly
    cleared. Unconfigured deployments ignore the field entirely.
    """
    configured = current_app.config.get("AUTHORS") or []
    if not configured:
        return None, None
    author = data.get("author")
    if author is not None:
        author = author.strip()
    if author:
        names = {a["name"] for a in configured}
        if author not in names:
            return None, _error("Unknown author.", 400)
    return author, None


def _validate_unlock(data):
    """Resolve and validate the optional 'unlock' field (FEATURES.md F0).

    Missing or empty means "no seal"; anything else must be an ISO date.
    """
    value = data.get("unlock")
    if not value:
        return None, None
    unlock = _parse_date(value)
    if unlock is None:
        return None, _error("Seal date must be an ISO date (YYYY-MM-DD).", 400)
    return unlock, None


def _validate_kind(data):
    """Resolve and validate the optional 'kind' field on create (FEATURES.md
    F13). Defaults to "story"; PUT never accepts this — kind is set once at
    creation and preserved on every later save."""
    kind = data.get("kind") or "story"
    if kind not in ("story", "instant"):
        return None, _error("Invalid kind.", 400)
    return kind, None


def _validate_cover(data, stories_dir, story_id):
    """Resolve and validate the optional 'cover' field on update.

    Absent means "leave unchanged"; empty string clears it; a non-empty
    value must be a safe filename that already exists in the story folder.
    """
    if "cover" not in data:
        return None, None
    cover = data.get("cover")
    if not cover:
        return "", None
    if not storage.is_valid_filename(cover):
        return None, _error("Invalid cover filename.", 400)
    if not (Path(stories_dir) / story_id / cover).is_file():
        return None, _error("Cover image not found.", 400)
    return cover, None


@bp.route("/stories", methods=["POST"])
@login_required
def create_story():
    data = request.get_json(silent=True) or {}
    kind, error = _validate_kind(data)
    if error:
        return error

    title = (data.get("title") or "").strip()
    story_date = _parse_date(data.get("date"))
    markdown = data.get("markdown") or ""
    draft = bool(data.get("draft"))
    archived = bool(data.get("archived"))

    if kind == "instant":
        # FEATURES.md F13: the "line" is optional, so an instant never fails
        # on a blank title — it just defaults, truncated to a sane length.
        title = title[:60] if title else "Instant"
    elif not title:
        return _error("Title is required.", 400)
    if story_date is None:
        return _error("Date must be an ISO date (YYYY-MM-DD).", 400)

    author, error = _validate_author(data)
    if error:
        return error
    unlock, error = _validate_unlock(data)
    if error:
        return error

    story_id = storage.create_story(
        current_app.config["STORIES_DIR"], title, story_date, markdown, author=author,
        draft=draft, unlock=unlock, archived=archived, kind=kind,
    )
    return jsonify({"id": story_id, "title": title})


@bp.route("/stories/<story_id>", methods=["PUT"])
@login_required
def update_story(story_id):
    if not storage.is_valid_story_id(story_id):
        return _error("Story not found.", 404)

    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()
    story_date = _parse_date(data.get("date"))
    markdown = data.get("markdown") or ""
    draft = bool(data.get("draft"))
    archived = bool(data.get("archived"))

    if not title:
        return _error("Title is required.", 400)
    if story_date is None:
        return _error("Date must be an ISO date (YYYY-MM-DD).", 400)

    author, error = _validate_author(data)
    if error:
        return error
    unlock, error = _validate_unlock(data)
    if error:
        return error
    cover, error = _validate_cover(data, current_app.config["STORIES_DIR"], story_id)
    if error:
        return error

    try:
        storage.save_story(
            current_app.config["STORIES_DIR"], story_id, title, story_date, markdown,
            cover=cover, author=author, draft=draft, unlock=unlock, archived=archived,
        )
    except FileNotFoundError:
        return _error("Story not found.", 404)

    return jsonify({"id": story_id})


@bp.route("/stories/<story_id>/versions/<version_id>/restore", methods=["POST"])
@login_required
def restore_version(story_id, version_id):
    try:
        storage.restore_version(current_app.config["STORIES_DIR"], story_id, version_id)
    except (storage.InvalidStoryId, storage.InvalidVersionId, FileNotFoundError):
        return _error("Version not found.", 404)
    return jsonify({"id": story_id})


@bp.route("/import", methods=["POST"])
@login_required
def import_backup():
    file_storage = request.files.get("file")
    if file_storage is None or not file_storage.filename:
        return _error("No backup file provided.", 400)

    try:
        count = storage.import_backup(current_app.config["STORIES_DIR"], file_storage.stream)
    except storage.ImportCollision as e:
        shown = ", ".join(e.colliding_ids[:5])
        more = f" and {len(e.colliding_ids) - 5} more" if len(e.colliding_ids) > 5 else ""
        return _error(
            f"Import aborted, nothing was changed: {len(e.colliding_ids)} "
            f"already exist here ({shown}{more}).",
            409,
        )
    except zipfile.BadZipFile:
        return _error("That doesn't look like a valid zip file.", 400)
    except ValueError as e:
        return _error(str(e), 400)

    return jsonify({"imported": count})


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
