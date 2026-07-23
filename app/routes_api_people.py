"""Person/family JSON API routes (FEATURES.md F14/F18): person CRUD, the
parents/partners/friend_of/gender validators, photo uploads, and the
/api/tree contract. Registers onto the same `api` blueprint
`routes_api.py` defines — see that module's docstring/bottom-of-file
import for why these live in a separate file without a separate
blueprint.
"""

from flask import current_app, jsonify, request, url_for

from . import kinship, people, storage
from .auth import login_required
from .routes_api import (
    _error,
    _people_dir,
    _validate_media_filename,
    _validate_slug_list,
    _validate_sources,
    bp,
)


def _validate_person_photo(data, slug):
    """Resolve and validate the optional 'photo' field on person update.
    Same rules as a story's `cover` (FEATURES.md F14)."""
    return _validate_media_filename(
        data, "photo", _people_dir() / slug, "photo", "Photo not found."
    )


def _validate_person_photo_sepia(data):
    """Resolve and validate the optional 'photo_sepia' field: a 0-100
    percentage. None means the field was absent ("leave unchanged" on
    update); there is no "clear" value — 0 is a legitimate, meaningful
    setting (no sepia at all), so it must not be treated as absent."""
    if "photo_sepia" not in data:
        return None, None
    value = data.get("photo_sepia")
    if isinstance(value, str):
        try:
            value = int(value)
        except ValueError:
            return None, _error("Photo sepia must be a number from 0 to 100.", 400)
    if not people.is_valid_photo_sepia(value):
        return None, _error("Photo sepia must be a whole number from 0 to 100.", 400)
    return value, None


def _person_name(data):
    """The person's name, sent as `name` per the documented API — also
    accepts `title`, since the shared editor.js (FEATURES.md F14: "do not
    fork editor.js") always posts a `title` field regardless of whether the
    form is editing a story or a person."""
    return (data.get("name") or data.get("title") or "").strip()


def _validate_gender(data):
    """Resolve and validate the optional 'gender' field. None means the
    field was absent ("leave unchanged" on update); "" clears it."""
    if "gender" not in data:
        return None, None
    gender = (data.get("gender") or "").strip()
    if gender not in ("m", "f", ""):
        return None, _error("Gender must be 'm', 'f', or empty.", 400)
    return gender, None


def _validate_author_color(data):
    """Resolve and validate the optional 'author_color' field (FEATURES.md
    F19 Phase 4). None means the field was absent ("leave unchanged" on
    update); "" clears it. Only meaningful in accounts mode, but validated
    the same regardless — a person's color isn't harmful to store even
    when unused."""
    if "author_color" not in data:
        return None, None
    author_color = (data.get("author_color") or "").strip()
    if author_color and not people.is_valid_author_color(author_color):
        return None, _error("Color must be a hex value like #d9a441.", 400)
    return author_color, None


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
    author_color, error = _validate_author_color(data)
    if error:
        return error
    sources, error = _validate_sources(data)
    if error:
        return error

    people_dir = _people_dir()
    slug = people.create_person(
        people_dir, name, relation=relation, body=markdown,
        parents=fields["parents"], partners=fields["partners"],
        friend_of=fields["friend_of"], gender=fields["gender"],
        author_color=author_color, sources=sources,
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

    photo_sepia, error = _validate_person_photo_sepia(data)
    if error:
        return error

    author_color, error = _validate_author_color(data)
    if error:
        return error

    fields, all_people, error = _validate_person_family(data, self_slug=slug)
    if error:
        return error
    sources, error = _validate_sources(data)
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
            photo_sepia=photo_sepia, author_color=author_color, sources=sources,
        )
    except FileNotFoundError:
        return _error("Person not found.", 404)

    _sync_partner_symmetry(people_dir, slug, existing.partners, fields["partners"])

    return jsonify({"id": slug})


@bp.route("/people/<slug>/images", methods=["POST"])
@login_required
def upload_person_image(slug):
    """Images inserted into the body text via the WYSIWYG editor. These are
    always just body images — they never become the person's cover photo;
    that is the dedicated /photo endpoint's job only (FEATURES.md F18 photo
    styling round)."""
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

    return jsonify({"filename": filename})


@bp.route("/people/<slug>/photo", methods=["POST"])
@login_required
def upload_person_photo(slug):
    """The dedicated cover-photo upload (FEATURES.md F18 photo styling
    round): uploads and resizes the file exactly like the body-image
    endpoint, then sets it as the person's photo and resets photo_sepia to
    its default, since a brand-new photo needs a fresh tone rather than
    inheriting the previous photo's. The uploaded file is expected to
    already be cropped client-side (the editor's pan/zoom crop tool bakes
    the crop into the image before it ever reaches this endpoint) — the
    server does not perform or store any separate crop/focus data."""
    if not storage.is_valid_story_id(slug):
        return _error("Person not found.", 404)
    existing = people.get_person(_people_dir(), slug)
    if existing is None:
        return _error("Person not found.", 404)

    file_storage = request.files.get("file")
    if file_storage is None or not file_storage.filename:
        return _error("No image file provided.", 400)

    try:
        filename = storage.save_image_to(_people_dir() / slug, file_storage)
    except Exception:
        return _error("Could not process image.", 400)

    people.update_person(
        _people_dir(), slug, existing.name, relation=existing.relation,
        body=existing.body or "", photo=filename,
        photo_sepia=people.DEFAULT_PHOTO_SEPIA,
    )

    return jsonify({
        "filename": filename,
        "photo_sepia": people.DEFAULT_PHOTO_SEPIA,
    })


@bp.route("/tree")
@login_required
def api_tree():
    """The Layer-2/3 contract for FEATURES.md F18 — the seam future
    renderers plug into. See README.md for the documented shape."""
    people_dir = _people_dir()
    all_people = people.list_people(people_dir)
    graph = kinship.build_graph(all_people)
    anchor = kinship.resolve_anchor(current_app.config.get("CHILD_SLUG"), graph)

    entries = []
    for p in all_people:
        in_family = kinship.is_in_family(graph, p.slug)
        entry = {
            "id": p.slug,
            "name": p.name,
            "gender": p.gender,
            "photo": (
                url_for("pages.person_media", slug=p.slug, filename=p.photo)
                if p.photo else None
            ),
            "photo_sepia": p.photo_sepia,
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
