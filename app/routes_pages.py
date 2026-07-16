import random
import tempfile
import zipfile
from datetime import date, datetime

from flask import (
    Blueprint,
    abort,
    current_app,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    send_from_directory,
    url_for,
)

from . import epub, kinship, people, prompts, storage
from .auth import login_required
from .rendering import render_markdown

bp = Blueprint("pages", __name__)

# Re-encoded photos (storage.save_image_to always writes .jpg or .png) are
# never overwritten or reused under a different number, so they're safe to
# cache for a long time. Voice memos are excluded: delete_memo can free up a
# number that a later upload then reuses for different audio, so their
# filename isn't a stable cache key.
_LONG_CACHE_EXTENSIONS = {"jpg", "png"}
_LONG_CACHE_MAX_AGE = 31536000  # 1 year


def _media_max_age(filename):
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return _LONG_CACHE_MAX_AGE if ext in _LONG_CACHE_EXTENSIONS else None


def _get_story_or_404(stories_dir, story_id):
    s = storage.get_story(stories_dir, story_id)
    if s is None:
        abort(404)
    return s


def _serve_media(root_dir, id_value, filename):
    """Validate `id_value`/`filename`, then serve `filename` from
    `root_dir/id_value` — the shared story_media/person_media pattern
    (CLAUDE.md: validate, then check existence, then serve)."""
    if not storage.is_valid_story_id(id_value) or not storage.is_valid_filename(filename):
        abort(404)
    media_dir = root_dir / id_value
    if not (media_dir / filename).is_file():
        abort(404)
    return send_from_directory(media_dir, filename, max_age=_media_max_age(filename))


def _authors_and_colors():
    authors = current_app.config.get("AUTHORS") or []
    author_colors = {a["name"]: a["color"] for a in authors}
    return authors, author_colors


def _author_color(authors, author_colors, name):
    return author_colors.get(name) if (authors and name) else None


@bp.route("/")
@login_required
def timeline():
    all_stories = storage.list_stories(current_app.config["STORIES_DIR"])
    stories = [s for s in all_stories if not s.draft and not s.archived]
    draft_count = sum(1 for s in all_stories if s.draft and not s.archived)
    archived_count = sum(1 for s in all_stories if s.archived)
    today = date.today()
    years = {}
    for story in stories:
        years.setdefault(story.date.year, []).append(story)
    authors, author_colors = _authors_and_colors()
    return render_template(
        "timeline.html",
        years=sorted(years.items()),
        stories=stories,
        authors=authors,
        author_colors=author_colors,
        draft_count=draft_count,
        archived_count=archived_count,
        today=today,
        birthdate=current_app.config.get("BIRTHDATE"),
        on_this_day=storage.on_this_day(all_stories, today),
    )


@bp.route("/random")
@login_required
def random_page():
    """Open a random readable story (FEATURES.md F15). Drafts, sealed
    letters, and instants (page-turning is for stories) are never chosen;
    `?not=<id>` excludes one story id (e.g. the one you're already on)."""
    stories_dir = current_app.config["STORIES_DIR"]
    candidates = storage.readable_page_stories(stories_dir)
    exclude_id = request.args.get("not")
    if exclude_id:
        candidates = [s for s in candidates if s.id != exclude_id]
    if not candidates:
        return redirect(url_for("pages.timeline"))
    choice = random.choice(candidates)
    return redirect(url_for("pages.story", story_id=choice.id))


@bp.route("/manifest.webmanifest")
def manifest():
    """Web app manifest for home-screen install (FEATURES.md F9). No login
    required — the manifest and icons must be fetchable before install."""
    title = current_app.config["TITLE"]
    data = {
        "name": title,
        "short_name": title,
        "start_url": "/",
        "display": "standalone",
        "background_color": "#141210",
        "theme_color": "#141210",
        "icons": [
            {
                "src": url_for("static", filename="icons/icon-192.png"),
                "sizes": "192x192",
                "type": "image/png",
            },
            {
                "src": url_for("static", filename="icons/icon-512.png"),
                "sizes": "512x512",
                "type": "image/png",
            },
        ],
    }
    response = jsonify(data)
    response.mimetype = "application/manifest+json"
    return response


@bp.route("/book")
@login_required
def book():
    """The whole book on one page, for reading and printing (FEATURES.md F10)."""
    stories_dir = current_app.config["STORIES_DIR"]
    readable = storage.readable_stories(storage.list_stories(stories_dir))
    authors, author_colors = _authors_and_colors()
    entries = []
    for s in readable:
        full = storage.get_story(stories_dir, s.id)
        body_html = render_markdown(full.body, f"/story/{full.id}/media")
        author_color = _author_color(authors, author_colors, full.author)
        entries.append({"story": full, "body_html": body_html, "author_color": author_color})
    return render_template(
        "book.html",
        entries=entries,
        authors=authors,
        birthdate=current_app.config.get("BIRTHDATE"),
        min_year=readable[0].date.year if readable else None,
        max_year=readable[-1].date.year if readable else None,
    )


@bp.route("/book.epub")
@login_required
def book_epub():
    """The whole book as a downloadable EPUB (readable in any e-reader app,
    unlike the browser-print PDF flow at /book)."""
    stories_dir = current_app.config["STORIES_DIR"]
    readable = storage.readable_stories(storage.list_stories(stories_dir))
    authors = current_app.config.get("AUTHORS") or []
    entries = []
    for s in readable:
        full = storage.get_story(stories_dir, s.id)
        body_html = render_markdown(full.body, f"/story/{full.id}/media")
        entries.append({"story": full, "body_html": body_html})

    def image_loader(story_id, filename):
        if not storage.is_valid_story_id(story_id) or not storage.is_valid_filename(filename):
            return None
        path = stories_dir / story_id / filename
        return path.read_bytes() if path.is_file() else None

    title = current_app.config["TITLE"]
    buf = epub.build_epub(
        title,
        readable[0].date.year if readable else None,
        readable[-1].date.year if readable else None,
        authors,
        entries,
        image_loader,
    )
    filename = f"{storage.slugify(title)}.epub"
    return send_file(buf, mimetype=epub.MIMETYPE, as_attachment=True, download_name=filename)


@bp.route("/export")
@login_required
def export():
    """Stream a zip of the entire stories directory (FEATURES.md F8)."""
    stories_dir = current_app.config["STORIES_DIR"]
    tmp = tempfile.TemporaryFile()
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_STORED) as zf:
        for path in sorted(stories_dir.rglob("*")):
            if path.is_dir() or path.name.endswith(".tmp"):
                continue
            zf.write(path, path.relative_to(stories_dir))
    tmp.seek(0)
    filename = f"storybook-backup-{date.today().isoformat()}.zip"
    return send_file(tmp, mimetype="application/zip", as_attachment=True, download_name=filename)


@bp.route("/import")
@login_required
def import_page():
    return render_template("import.html")


@bp.route("/drafts")
@login_required
def drafts():
    all_stories = storage.list_stories(current_app.config["STORIES_DIR"])
    draft_stories = [s for s in all_stories if s.draft and not s.archived]
    draft_stories.sort(key=lambda s: s.updated or datetime.min, reverse=True)
    authors, author_colors = _authors_and_colors()
    return render_template(
        "drafts.html", stories=draft_stories, authors=authors, author_colors=author_colors
    )


@bp.route("/archived")
@login_required
def archived():
    all_stories = storage.list_stories(current_app.config["STORIES_DIR"])
    archived_stories = [s for s in all_stories if s.archived]
    archived_stories.sort(key=lambda s: s.updated or datetime.min, reverse=True)
    authors, author_colors = _authors_and_colors()
    return render_template(
        "archived.html", stories=archived_stories, authors=authors, author_colors=author_colors
    )


@bp.route("/story/<story_id>")
@login_required
def story(story_id):
    s = _get_story_or_404(current_app.config["STORIES_DIR"], story_id)
    authors, author_colors = _authors_and_colors()
    author_color = _author_color(authors, author_colors, s.author)
    if storage.is_sealed(s):
        return render_template("sealed.html", story=s, author_color=author_color)
    body_html = render_markdown(s.body, f"/story/{story_id}/media")
    prev_story, next_story = _reading_order_neighbors(current_app.config["STORIES_DIR"], s)
    memos = storage.list_memos(current_app.config["STORIES_DIR"] / story_id)
    return render_template(
        "story.html", story=s, body_html=body_html, authors=authors, author_color=author_color,
        prev_story=prev_story, next_story=next_story, memos=memos,
        birthdate=current_app.config.get("BIRTHDATE"),
    )


def _reading_order_neighbors(stories_dir, current):
    """Previous/next readable story either side of `current` (F2). None/None
    when `current` isn't itself readable (e.g. a draft, archived, or an
    instant) or at either end. Instants are also skipped as candidate
    neighbors for a real story (FEATURES.md F13: page-turning is for
    stories)."""
    if current.draft or current.archived or current.kind != "story":
        return None, None
    readable = storage.readable_page_stories(stories_dir)
    for i, r in enumerate(readable):
        if r.id == current.id:
            prev_story = readable[i - 1] if i > 0 else None
            next_story = readable[i + 1] if i < len(readable) - 1 else None
            return prev_story, next_story
    return None, None


@bp.route("/story/<story_id>/history")
@login_required
def story_history(story_id):
    s = _get_story_or_404(current_app.config["STORIES_DIR"], story_id)
    versions = storage.list_versions(current_app.config["STORIES_DIR"], story_id)
    return render_template("history.html", story=s, versions=versions)


@bp.route("/story/<story_id>/media/<filename>")
@login_required
def story_media(story_id, filename):
    return _serve_media(current_app.config["STORIES_DIR"], story_id, filename)


@bp.route("/new")
@login_required
def new_story():
    authors = current_app.config.get("AUTHORS") or []
    prompt_list = prompts.load_prompts(current_app.config["STORIES_DIR"])
    initial_prompt = random.choice(prompt_list) if prompt_list else None
    return render_template(
        "editor.html", story=None, today=date.today(), authors=authors,
        prompts=prompt_list, initial_prompt=initial_prompt, memos=[],
    )


@bp.route("/new-instant")
@login_required
def new_instant():
    authors = current_app.config.get("AUTHORS") or []
    return render_template("instant.html", today=date.today(), authors=authors)


@bp.route("/edit/<story_id>")
@login_required
def edit_story(story_id):
    s = _get_story_or_404(current_app.config["STORIES_DIR"], story_id)
    authors = current_app.config.get("AUTHORS") or []
    memos = storage.list_memos(current_app.config["STORIES_DIR"] / story_id)
    return render_template("editor.html", story=s, today=date.today(), authors=authors, memos=memos)


def _people_dir():
    return storage.people_dir(current_app.config["STORIES_DIR"])


def _get_person_or_404(people_dir, slug):
    p = people.get_person(people_dir, slug)
    if p is None:
        abort(404)
    return p


def _has_family_links(graph):
    """True when at least one person has a parent or partner — the shared
    condition for showing the "Family tree" link on /people and showing the
    chart (vs. a gentle empty state) on /tree (FEATURES.md F18)."""
    return any(graph.parents.get(slug) or graph.partners.get(slug) for slug in graph.nodes)


@bp.route("/people")
@login_required
def people_page():
    all_people = people.list_people(_people_dir())
    graph = kinship.build_graph(all_people)
    return render_template(
        "people.html", people=all_people, show_tree_link=_has_family_links(graph)
    )


def _person_ref(people_by_slug, slug):
    """A lightweight {slug, name, photo_url, photo_sepia} dict for linking
    to another person in a template — None when the slug isn't a real
    person."""
    p = people_by_slug.get(slug)
    if p is None:
        return None
    photo_url = url_for("pages.person_media", slug=p.slug, filename=p.photo) if p.photo else None
    return {"slug": p.slug, "name": p.name, "photo_url": photo_url, "photo_sepia": p.photo_sepia}


@bp.route("/people/<slug>")
@login_required
def person_page(slug):
    p = _get_person_or_404(_people_dir(), slug)
    body_html = render_markdown(p.body, f"/people/{slug}/media")

    all_people = people.list_people(_people_dir())
    people_by_slug = {person.slug: person for person in all_people}
    graph = kinship.build_graph(all_people)
    anchor = kinship.resolve_anchor(current_app.config.get("CHILD_SLUG"), graph)

    kinship_line = None
    friend_of_line = None
    if not p.relation:
        if anchor:
            kinship_line = kinship.kinship_label(graph, anchor, slug)
        if kinship_line is None and p.friend_of:
            friend_of_line = _person_ref(people_by_slug, p.friend_of[0])

    family = {
        "parents": [_person_ref(people_by_slug, s) for s in graph.parents.get(slug, [])],
        "partners": [_person_ref(people_by_slug, s) for s in kinship.partners_of(graph, slug)],
        "children": [_person_ref(people_by_slug, s) for s in kinship.children_of(graph, slug)],
        "siblings": [_person_ref(people_by_slug, s) for s in kinship.siblings_of(graph, slug)],
    }
    family = {key: [ref for ref in refs if ref] for key, refs in family.items()}

    return render_template(
        "person.html", person=p, body_html=body_html,
        kinship_line=kinship_line, friend_of_line=friend_of_line, family=family,
    )


@bp.route("/people/<slug>/media/<filename>")
@login_required
def person_media(slug, filename):
    return _serve_media(_people_dir(), slug, filename)


@bp.route("/tree")
@login_required
def tree_page():
    all_people = people.list_people(_people_dir())
    people_by_slug = {p.slug: p for p in all_people}
    graph = kinship.build_graph(all_people)

    has_family_links = _has_family_links(graph)
    anchor = kinship.resolve_anchor(current_app.config.get("CHILD_SLUG"), graph)

    others = []
    generations = []
    if has_family_links:
        # Buckets the printable outline groups by: real generation offsets
        # when an anchor is set, one fixed key otherwise (kinship labels
        # — and so per-person generation — don't exist without an
        # anchor; everyone just lands in a single "Family" bucket).
        buckets = {}
        for p in all_people:
            if kinship.is_in_family(graph, p.slug):
                ref = _person_ref(people_by_slug, p.slug)
                if ref is None:
                    continue
                key = None
                if anchor:
                    ref["kinship"] = kinship.kinship_label(graph, anchor, p.slug)
                    key = kinship.generation_offset(graph, anchor, p.slug)
                buckets.setdefault(key, []).append(ref)
                continue
            friend_refs = [_person_ref(people_by_slug, s) for s in graph.friend_of.get(p.slug, [])]
            others.append({
                "slug": p.slug,
                "name": p.name,
                "friend_of": [ref for ref in friend_refs if ref],
            })

        if anchor:
            anchor_name = people_by_slug[anchor].name
            for offset in sorted((k for k in buckets if k is not None), reverse=True):
                generations.append({
                    "heading": kinship.generation_group_label(offset, anchor_name),
                    "people": buckets[offset],
                })
            if None in buckets:
                generations.append({"heading": "Other family", "people": buckets[None]})
        elif buckets:
            generations.append({"heading": "Family", "people": buckets[None]})

    return render_template(
        "tree.html", has_family_links=has_family_links, others=others, generations=generations,
    )


def _other_people_refs(exclude_slug=None):
    all_people = people.list_people(_people_dir())
    people_by_slug = {p.slug: p for p in all_people}
    return [
        _person_ref(people_by_slug, p.slug) for p in all_people if p.slug != exclude_slug
    ]


@bp.route("/new-person")
@login_required
def new_person():
    return render_template("person_editor.html", person=None, other_people=_other_people_refs())


@bp.route("/edit-person/<slug>")
@login_required
def edit_person(slug):
    p = _get_person_or_404(_people_dir(), slug)
    return render_template(
        "person_editor.html", person=p, other_people=_other_people_refs(exclude_slug=slug)
    )
