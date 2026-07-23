"""Core story JSON API routes: create/update/restore a story, image/memo
uploads, and backup import.

Person/family API routes live in `routes_api_people.py` — it registers
onto the `bp` object defined here rather than declaring its own
blueprint, so every `url_for("api.xxx")` reference keeps working
unchanged regardless of which file a route's code actually lives in.
It's imported at the bottom of this file (after `bp` and the handful of
helpers it needs — `_error`, `_parse_date`, `_people_dir`,
`_validate_media_filename`, `_validate_slug_list`, `_validate_sources` —
already exist) purely for that side effect: registering its routes.
"""

import zipfile
from datetime import date as date_cls
from pathlib import Path
from urllib.parse import urlparse

from flask import Blueprint, current_app, jsonify, request, session

from . import people, storage
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


def _people_dir():
    return storage.people_dir(current_app.config["STORIES_DIR"])


def _validate_author(data):
    """Resolve and validate the optional 'author' field (FEATURES.md F1).

    Returns (author, error_response). `author` is None when absent (create:
    no author; update: leave unchanged) or empty string when explicitly
    cleared. Unconfigured deployments ignore the field entirely.

    In accounts mode (FEATURES.md F19 Phase 4) this always returns
    (None, None): authorship is never taken from the client there — see
    _author_name_for_current_account, which create_story uses instead to
    derive it from the session, and update_story leaving it None (i.e.
    unchanged) so editing a story never silently reassigns who wrote it.
    """
    if current_app.config.get("ACCOUNTS_ENABLED"):
        return None, None
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


def _author_name_for_current_account():
    """The display name to auto-attribute a newly created story/instant to,
    when accounts mode is on and the current session is a real (non-
    delegate) account bound to a Person. None otherwise — accounts mode
    off, or a session somehow missing its person_slug — in which case the
    story is simply created with no author, same as today."""
    if not current_app.config.get("ACCOUNTS_ENABLED"):
        return None
    person_slug = session.get("person_slug")
    if not person_slug:
        return None
    person = people.get_person(storage.people_dir(current_app.config["STORIES_DIR"]), person_slug)
    return person.name if person else None


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


def _validate_media_filename(data, field_name, media_dir, noun, not_found_msg):
    """Resolve and validate an optional filename field referring to a file
    already uploaded into `media_dir` — a story's `cover`, a person's
    `photo` (FEATURES.md F14). Absent means "leave unchanged"; empty
    string clears it; a non-empty value must be a safe filename that
    already exists there."""
    if field_name not in data:
        return None, None
    value = data.get(field_name)
    if not value:
        return "", None
    if not storage.is_valid_filename(value):
        return None, _error(f"Invalid {noun} filename.", 400)
    if not (media_dir / value).is_file():
        return None, _error(not_found_msg, 400)
    return value, None


def _validate_cover(data, stories_dir, story_id):
    """Resolve and validate the optional 'cover' field on update.

    Absent means "leave unchanged"; empty string clears it; a non-empty
    value must be a safe filename that already exists in the story folder.
    """
    return _validate_media_filename(
        data, "cover", Path(stories_dir) / story_id, "cover", "Cover image not found."
    )


_SOURCE_MAX = 20
_SOURCE_NOTE_MAX = 200
_SOURCE_URL_MAX = 500

_FAMILY_FIELD_LABELS = {"parents": "parent", "partners": "partner", "friend_of": "friend"}


def _validate_slug_list(data, field_name, valid_slugs, self_slug, max_len=None):
    """Resolve and validate a list of other people's slugs — `parents`/
    `partners`/`friend_of` (FEATURES.md F18) on a person, or `people`
    (F20) on a story. Returns (list-or-None, error_response). None means
    the field was absent from the payload ("leave unchanged" on update).
    Shared between story and person validation (routes_api_people.py),
    so it lives in this core module rather than either split-out file.
    """
    if field_name not in data:
        return None, None
    raw = data.get(field_name)
    if not isinstance(raw, list):
        raw = []
    cleaned = []
    seen = set()
    for item in raw:
        if not isinstance(item, str):
            continue
        item = item.strip()
        if not item or item in seen:
            continue
        seen.add(item)
        if self_slug is not None and item == self_slug:
            label = _FAMILY_FIELD_LABELS[field_name]
            return None, _error(f"A person cannot be their own {label}.", 400)
        if item not in valid_slugs:
            return None, _error(f"Unknown person: {item}.", 400)
        cleaned.append(item)
    if max_len is not None and len(cleaned) > max_len:
        return None, _error(f"A person can have at most {max_len} parents.", 400)
    return cleaned, None


def _validate_story_people(data):
    """Resolve and validate the optional 'people' field: person slugs
    appearing in the story. None means absent ('leave unchanged' on
    update)."""
    valid_slugs = {p.slug for p in people.list_people(_people_dir())}
    return _validate_slug_list(data, "people", valid_slugs, self_slug=None)


def _validate_tags(data):
    """Resolve and validate the optional 'tags' field: free-form event
    tags on a story. None means absent ('leave unchanged' on update)."""
    if "tags" not in data:
        return None, None
    raw = data.get("tags")
    if not isinstance(raw, list):
        return None, _error("Tags must be a list.", 400)
    cleaned = []
    seen = set()
    for item in raw:
        if not isinstance(item, str):
            continue
        item = item.strip()[: storage.MAX_TAG_LENGTH]
        if not item or item in seen:
            continue
        seen.add(item)
        cleaned.append(item)
    if len(cleaned) > storage.MAX_TAGS:
        return None, _error(f"At most {storage.MAX_TAGS} tags allowed.", 400)
    return cleaned, None


def _validate_milestone(data):
    """Resolve and validate the optional 'milestone' field (FEATURES.md
    F28): a short free-text label like "First steps". None means absent
    ('leave unchanged' on update); '' clears it. No format constraint —
    just trimmed and capped, same tolerant treatment as tags."""
    if "milestone" not in data:
        return None, None
    value = (data.get("milestone") or "").strip()
    return value[: storage.MAX_MILESTONE_LENGTH], None


def _validate_sources(data):
    """Resolve and validate the optional 'sources' field: a list of
    {"url": ..., "note": ...} citation links, pasted in manually and never
    fetched by the app. None means absent ('leave unchanged' on update).

    Only http(s) URLs are accepted — these render back as `<a href>`, so a
    `javascript:`/`data:` scheme here would be a stored-XSS vector.
    """
    if "sources" not in data:
        return None, None
    raw = data.get("sources")
    if not isinstance(raw, list):
        return None, _error("Sources must be a list.", 400)
    cleaned = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        url = (item.get("url") or "").strip()
        if not url:
            continue
        if urlparse(url).scheme.lower() not in ("http", "https"):
            return None, _error("Source links must be http:// or https:// URLs.", 400)
        note = (item.get("note") or "").strip()
        cleaned.append({"url": url[:_SOURCE_URL_MAX], "note": note[:_SOURCE_NOTE_MAX]})
    if len(cleaned) > _SOURCE_MAX:
        return None, _error(f"At most {_SOURCE_MAX} sources allowed.", 400)
    return cleaned, None


def _parse_story_fields(data):
    """The raw title/date/markdown/draft/archived fields shared by
    create/update, plus the one validation rule both apply identically
    (a valid date is always required). Title is validated separately by
    each caller — create's rule depends on `kind`, update's doesn't."""
    title = (data.get("title") or "").strip()
    story_date = _parse_date(data.get("date"))
    markdown = data.get("markdown") or ""
    draft = bool(data.get("draft"))
    archived = bool(data.get("archived"))
    if story_date is None:
        return None, _error("Date must be an ISO date (YYYY-MM-DD).", 400)
    return (title, story_date, markdown, draft, archived), None


@bp.route("/stories", methods=["POST"])
@login_required
def create_story():
    data = request.get_json(silent=True) or {}
    kind, error = _validate_kind(data)
    if error:
        return error

    fields, error = _parse_story_fields(data)
    if error:
        return error
    title, story_date, markdown, draft, archived = fields

    if kind == "instant":
        # FEATURES.md F13: the "line" is optional, so an instant never fails
        # on a blank title — it just defaults, truncated to a sane length.
        title = title[:60] if title else "Instant"
    elif not title:
        return _error("Title is required.", 400)

    author, error = _validate_author(data)
    if error:
        return error
    author = _author_name_for_current_account() or author
    unlock, error = _validate_unlock(data)
    if error:
        return error
    story_people, error = _validate_story_people(data)
    if error:
        return error
    tags, error = _validate_tags(data)
    if error:
        return error
    sources, error = _validate_sources(data)
    if error:
        return error
    milestone, error = _validate_milestone(data)
    if error:
        return error

    story_id = storage.create_story(
        current_app.config["STORIES_DIR"], title, story_date, markdown, author=author,
        draft=draft, unlock=unlock, archived=archived, kind=kind,
        people=story_people, tags=tags, sources=sources, milestone=milestone,
    )
    return jsonify({"id": story_id, "title": title})


@bp.route("/stories/<story_id>", methods=["PUT"])
@login_required
def update_story(story_id):
    if not storage.is_valid_story_id(story_id):
        return _error("Story not found.", 404)

    data = request.get_json(silent=True) or {}
    fields, error = _parse_story_fields(data)
    if error:
        return error
    title, story_date, markdown, draft, archived = fields
    if not title:
        return _error("Title is required.", 400)

    author, error = _validate_author(data)
    if error:
        return error
    unlock, error = _validate_unlock(data)
    if error:
        return error
    cover, error = _validate_cover(data, current_app.config["STORIES_DIR"], story_id)
    if error:
        return error
    story_people, error = _validate_story_people(data)
    if error:
        return error
    tags, error = _validate_tags(data)
    if error:
        return error
    sources, error = _validate_sources(data)
    if error:
        return error
    milestone, error = _validate_milestone(data)
    if error:
        return error

    try:
        storage.save_story(
            current_app.config["STORIES_DIR"], story_id, title, story_date, markdown,
            cover=cover, author=author, draft=draft, unlock=unlock, archived=archived,
            people=story_people, tags=tags, sources=sources, milestone=milestone,
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


@bp.route("/stories/<story_id>/memos", methods=["POST"])
@login_required
def upload_memo(story_id):
    if not storage.is_valid_story_id(story_id):
        return _error("Story not found.", 404)

    file_storage = request.files.get("file")
    if file_storage is None or not file_storage.filename:
        return _error("No audio file provided.", 400)

    try:
        filename = storage.save_memo(current_app.config["STORIES_DIR"], story_id, file_storage)
    except FileNotFoundError:
        return _error("Story not found.", 404)
    except ValueError as e:
        return _error(str(e), 400)

    response = jsonify({"filename": filename})
    response.status_code = 201
    return response


@bp.route("/stories/<story_id>/memos/<filename>", methods=["DELETE"])
@login_required
def delete_memo(story_id, filename):
    if not storage.is_valid_story_id(story_id):
        return _error("Memo not found.", 404)

    deleted = storage.delete_memo(current_app.config["STORIES_DIR"], story_id, filename)
    if not deleted:
        return _error("Memo not found.", 404)

    return "", 204


# Registers routes_api_people.py's routes onto `bp` (see module docstring)
# — must come after every helper it imports above.
from . import routes_api_people  # noqa: E402,F401
