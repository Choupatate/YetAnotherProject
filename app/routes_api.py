import zipfile
from datetime import date as date_cls
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request, url_for

from . import kinship, people, storage
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


def _people_dir():
    return current_app.config["STORIES_DIR"] / "people"


def _validate_person_photo(data, slug):
    """Resolve and validate the optional 'photo' field on person update.
    Same rules as a story's `cover` (FEATURES.md F14)."""
    if "photo" not in data:
        return None, None
    photo = data.get("photo")
    if not photo:
        return "", None
    if not storage.is_valid_filename(photo):
        return None, _error("Invalid photo filename.", 400)
    if not (_people_dir() / slug / photo).is_file():
        return None, _error("Photo not found.", 400)
    return photo, None


def _person_name(data):
    """The person's name, sent as `name` per the documented API — also
    accepts `title`, since the shared editor.js (FEATURES.md F14: "do not
    fork editor.js") always posts a `title` field regardless of whether the
    form is editing a story or a person."""
    return (data.get("name") or data.get("title") or "").strip()


_FAMILY_FIELD_LABELS = {"parents": "parent", "partners": "partner", "friend_of": "friend"}


def _validate_slug_list(data, field_name, valid_slugs, self_slug, max_len=None):
    """Resolve and validate one of `parents`/`partners`/`friend_of`
    (FEATURES.md F18): a list of other people's slugs. Returns (list-or-None,
    error_response). None means the field was absent from the payload
    ("leave unchanged" on update)."""
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


def _validate_gender(data):
    """Resolve and validate the optional 'gender' field. None means the
    field was absent ("leave unchanged" on update); "" clears it."""
    if "gender" not in data:
        return None, None
    gender = (data.get("gender") or "").strip()
    if gender not in ("m", "f", ""):
        return None, _error("Gender must be 'm', 'f', or empty.", 400)
    return gender, None


def _validate_person_family(data, self_slug):
    """Resolve and validate parents/partners/friend_of/gender together
    (FEATURES.md F18). `self_slug` is None on create (a not-yet-existing
    person can't self-reference or cycle). Returns a dict of the four
    resolved values (each None if absent from the payload) plus the
    all-people list and graph already built (so callers can reuse them for
    partner symmetry), or (None, None, error_response)."""
    people_dir = _people_dir()
    all_people = people.list_people(people_dir)
    valid_slugs = {p.slug for p in all_people}

    parents, error = _validate_slug_list(data, "parents", valid_slugs, self_slug, max_len=2)
    if error:
        return None, None, error
    partners, error = _validate_slug_list(data, "partners", valid_slugs, self_slug)
    if error:
        return None, None, error
    friend_of, error = _validate_slug_list(data, "friend_of", valid_slugs, self_slug)
    if error:
        return None, None, error
    gender, error = _validate_gender(data)
    if error:
        return None, None, error

    if parents and self_slug is not None:
        graph = kinship.build_graph(all_people)
        for parent_slug in parents:
            if kinship.would_create_cycle(graph, self_slug, parent_slug):
                return None, None, _error("That would create a family-tree cycle.", 400)

    fields = {"parents": parents, "partners": partners, "friend_of": friend_of, "gender": gender}
    return fields, all_people, None


def _sync_partner_symmetry(people_dir, slug, old_partners, new_partners):
    """Partner links are symmetric on disk: when `slug`'s partners change,
    add/remove the reverse link on the other side too (FEATURES.md F18).
    The other person's `updated` timestamp changing as a result is
    expected."""
    if new_partners is None:
        return
    added = set(new_partners) - set(old_partners)
    removed = set(old_partners) - set(new_partners)
    for other_slug in added | removed:
        other = people.get_person(people_dir, other_slug)
        if other is None:
            continue
        other_partners = set(other.partners)
        if other_slug in added:
            other_partners.add(slug)
        else:
            other_partners.discard(slug)
        people.update_person(
            people_dir, other_slug, other.name, relation=other.relation,
            body=other.body or "", partners=sorted(other_partners),
        )


@bp.route("/people", methods=["POST"])
@login_required
def create_person():
    data = request.get_json(silent=True) or {}
    name = _person_name(data)
    if not name:
        return _error("Name is required.", 400)
    relation = (data.get("relation") or "").strip() or None
    markdown = data.get("markdown") or ""

    fields, _all_people, error = _validate_person_family(data, self_slug=None)
    if error:
        return error

    people_dir = _people_dir()
    slug = people.create_person(
        people_dir, name, relation=relation, body=markdown,
        parents=fields["parents"], partners=fields["partners"],
        friend_of=fields["friend_of"], gender=fields["gender"],
    )
    _sync_partner_symmetry(people_dir, slug, [], fields["partners"] or [])
    return jsonify({"id": slug, "title": name})


@bp.route("/people/<slug>", methods=["PUT"])
@login_required
def update_person(slug):
    if not storage.is_valid_story_id(slug):
        return _error("Person not found.", 404)

    data = request.get_json(silent=True) or {}
    name = _person_name(data)
    if not name:
        return _error("Name is required.", 400)
    relation = (data.get("relation") or "").strip() or None
    markdown = data.get("markdown") or ""

    photo, error = _validate_person_photo(data, slug)
    if error:
        return error

    fields, all_people, error = _validate_person_family(data, self_slug=slug)
    if error:
        return error

    people_dir = _people_dir()
    existing = people.get_person(people_dir, slug)
    if existing is None:
        return _error("Person not found.", 404)

    try:
        people.update_person(
            people_dir, slug, name, relation=relation, body=markdown, photo=photo,
            parents=fields["parents"], partners=fields["partners"],
            friend_of=fields["friend_of"], gender=fields["gender"],
        )
    except FileNotFoundError:
        return _error("Person not found.", 404)

    _sync_partner_symmetry(people_dir, slug, existing.partners, fields["partners"])

    return jsonify({"id": slug})


@bp.route("/people/<slug>/images", methods=["POST"])
@login_required
def upload_person_image(slug):
    if not storage.is_valid_story_id(slug):
        return _error("Person not found.", 404)
    person_dir = _people_dir() / slug
    if not person_dir.is_dir():
        return _error("Person not found.", 404)

    file_storage = request.files.get("file")
    if file_storage is None or not file_storage.filename:
        return _error("No image file provided.", 400)

    try:
        filename = storage.save_image_to(person_dir, file_storage)
    except Exception:
        return _error("Could not process image.", 400)

    existing = people.get_person(_people_dir(), slug)
    if existing is not None and not existing.photo:
        people.update_person(
            _people_dir(), slug, existing.name, relation=existing.relation,
            body=existing.body or "", photo=filename,
        )

    return jsonify({"filename": filename})


@bp.route("/tree")
@login_required
def api_tree():
    """The Layer-2/3 contract for FEATURES.md F18 — the seam future
    renderers plug into. See README.md for the documented shape."""
    people_dir = _people_dir()
    all_people = people.list_people(people_dir)
    graph = kinship.build_graph(all_people)

    anchor = current_app.config.get("CHILD_SLUG")
    if anchor not in graph.nodes:
        anchor = None

    entries = []
    for p in all_people:
        in_family = bool(
            graph.parents.get(p.slug)
            or graph.partners.get(p.slug)
            or kinship.children_of(graph, p.slug)
        )
        entry = {
            "id": p.slug,
            "name": p.name,
            "gender": p.gender,
            "photo": (
                url_for("pages.person_media", slug=p.slug, filename=p.photo)
                if p.photo else None
            ),
            "url": url_for("pages.person_page", slug=p.slug),
        }
        if in_family:
            entry["kinship"] = kinship.kinship_label(graph, anchor, p.slug) if anchor else None
            entry["rels"] = {
                "parents": list(graph.parents.get(p.slug, [])),
                "partners": kinship.partners_of(graph, p.slug),
                "children": kinship.children_of(graph, p.slug),
            }
        else:
            entry["friend_of"] = list(graph.friend_of.get(p.slug, []))
        entries.append(entry)

    return jsonify({"anchor": anchor, "people": entries})
