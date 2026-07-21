import hmac
import random
import tempfile
import time
import zipfile
from datetime import date, datetime

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    send_from_directory,
    session,
    url_for,
)

from . import accounts, epub, kinship, people, prompts, storage, write_links
from .auth import admin_required, delegate_required, login_required, set_session_for_account
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
    (CLAUDE.md: validate, then check existence, then serve). Falls back to
    the full-size photo when a `.thumb.` filename doesn't exist on disk yet
    (photos uploaded before thumbnails existed)."""
    if not storage.is_valid_story_id(id_value) or not storage.is_valid_filename(filename):
        abort(404)
    media_dir = root_dir / id_value
    if not (media_dir / filename).is_file():
        fallback = storage.original_filename_from_thumb(filename)
        if not fallback or not (media_dir / fallback).is_file():
            abort(404)
        filename = fallback
    return send_from_directory(media_dir, filename, max_age=_media_max_age(filename))


# Fallback color for an account-mode author who hasn't picked their own
# yet (person.author_color unset) — every entry _authors_and_colors hands
# to timeline.html's legend/dots needs a real value, since that template
# (shared with F1) renders `--author-color: {{ a.color }}` unconditionally
# for legend chips, unlike the per-story byline lookups which already
# guard on the color being present.
DEFAULT_AUTHOR_COLOR = "#9c8a6a"


def _authors_and_colors():
    """The (authors, author_colors) pair every timeline/book/story render
    needs for bylines and the legend. Two sources depending on mode
    (FEATURES.md F19 Phase 4): in accounts mode, every Person with a bound
    account — real identity, not config; otherwise the original
    STORYBOOK_AUTHORS list, untouched."""
    if current_app.config["ACCOUNTS_ENABLED"]:
        people_dir = storage.people_dir(current_app.config["STORIES_DIR"])
        people_by_slug = {p.slug: p for p in people.list_people(people_dir)}
        authors = []
        for account in accounts.list_accounts(people_dir):
            person = people_by_slug.get(account.person_slug)
            if person:
                authors.append(
                    {"name": person.name, "color": person.author_color or DEFAULT_AUTHOR_COLOR}
                )
    else:
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
    people_by_slug = {p.slug: p for p in people.list_people(_people_dir())}
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
        people_by_slug=people_by_slug,
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
    people_by_slug = {p.slug: p for p in people.list_people(_people_dir())}
    return render_template(
        "book.html",
        entries=entries,
        authors=authors,
        birthdate=current_app.config.get("BIRTHDATE"),
        min_year=readable[0].date.year if readable else None,
        max_year=readable[-1].date.year if readable else None,
        people_by_slug=people_by_slug,
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
    people_by_slug = {p.slug: p for p in people.list_people(_people_dir())}
    return render_template(
        "story.html", story=s, body_html=body_html, authors=authors, author_color=author_color,
        prev_story=prev_story, next_story=next_story, memos=memos,
        birthdate=current_app.config.get("BIRTHDATE"), people_by_slug=people_by_slug,
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
        all_people=_other_people_refs(),
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
    return render_template(
        "editor.html", story=s, today=date.today(), authors=authors, memos=memos,
        all_people=_other_people_refs(),
    )


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
    photo_url = (
        url_for("pages.person_media", slug=p.slug, filename=storage.thumb_filename(p.photo))
        if p.photo else None
    )
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

    stories_dir = current_app.config["STORIES_DIR"]
    appears_in = storage.readable_stories(storage.stories_featuring(stories_dir, slug))

    return render_template(
        "person.html", person=p, body_html=body_html,
        kinship_line=kinship_line, friend_of_line=friend_of_line, family=family,
        appears_in=appears_in,
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
    return render_template(
        "person_editor.html", person=None, other_people=_other_people_refs(),
        default_author_color=DEFAULT_AUTHOR_COLOR,
    )


@bp.route("/edit-person/<slug>")
@login_required
def edit_person(slug):
    p = _get_person_or_404(_people_dir(), slug)
    return render_template(
        "person_editor.html", person=p, other_people=_other_people_refs(exclude_slug=slug),
        default_author_color=DEFAULT_AUTHOR_COLOR,
    )


@bp.route("/request-account", methods=["GET", "POST"])
def request_account():
    """Public, unauthenticated (FEATURES.md F19 Phase 2): anyone who knows
    the invite code (STORYBOOK_PASSWORD, repurposed once accounts mode is
    on — it no longer logs anyone in) can queue a request. The very first
    request ever submitted auto-approves as admin, bound to a brand-new
    Person from its display name — there's no admin yet to review it, and
    already knowing the invite code is the only proof of ownership this
    self-hosted app has."""
    if not current_app.config["ACCOUNTS_ENABLED"]:
        abort(404)
    stories_dir = current_app.config["STORIES_DIR"]

    if request.method == "POST":
        invite_code = request.form.get("invite_code", "")
        display_name = (request.form.get("display_name") or "").strip()
        username = (request.form.get("username") or "").strip().lower()
        password = request.form.get("password") or ""
        note = request.form.get("note") or ""

        if not hmac.compare_digest(invite_code, current_app.config["PASSWORD"]):
            time.sleep(1)
            flash("Incorrect invite code.", "error")
        else:
            try:
                pending = accounts.create_pending_request(
                    stories_dir, username, password, display_name, note
                )
            except ValueError as exc:
                flash(str(exc), "error")
            else:
                auto_approved = accounts.approve_if_first(stories_dir, pending.username)
                return render_template(
                    "request_account.html", submitted=True, auto_approved=auto_approved
                )

    return render_template("request_account.html", submitted=False)


@bp.route("/admin/accounts")
@admin_required
def admin_accounts():
    stories_dir = current_app.config["STORIES_DIR"]
    people_dir = storage.people_dir(stories_dir)
    people_by_slug = {p.slug: p for p in people.list_people(people_dir)}
    unbound_people = [p for p in people_by_slug.values() if accounts.get_account(people_dir, p.slug) is None]
    rows = [
        {"account": a, "person": people_by_slug.get(a.person_slug)}
        for a in accounts.list_accounts(people_dir)
    ]
    link_rows = [
        {"link": link, "person": people_by_slug.get(link.person_slug)}
        for link in write_links.list_all_active(people_dir)
    ]
    return render_template(
        "admin_accounts.html", rows=rows, pending=accounts.list_pending(stories_dir),
        link_rows=link_rows, roles=accounts.ROLES, unbound_people=unbound_people,
    )


def _admin_mutate_account(person_slug, mutator, *args, on_success=None):
    """Shared shape for a POST-only admin account action: call `mutator`
    as `mutator(people_dir, person_slug, *args)`, flash and redirect on
    ValueError/FileNotFoundError (a bad slug, an invalid value, or a
    guard like the last-admin lockout) exactly like every other admin
    action here, then redirect to the accounts list either way. Optional
    `on_success` runs only after a real mutation, for the one route
    (link-person) that also needs to touch the caller's own session."""
    try:
        mutator(_people_dir(), person_slug, *args)
    except (ValueError, FileNotFoundError) as exc:
        flash(str(exc), "error")
    else:
        if on_success:
            on_success()
    return redirect(url_for("pages.admin_accounts"))


@bp.route("/admin/accounts/<person_slug>/disable", methods=["POST"])
@admin_required
def admin_disable_account(person_slug):
    return _admin_mutate_account(person_slug, accounts.set_status, "disabled")


@bp.route("/admin/accounts/<person_slug>/enable", methods=["POST"])
@admin_required
def admin_enable_account(person_slug):
    return _admin_mutate_account(person_slug, accounts.set_status, "active")


@bp.route("/admin/accounts/<person_slug>/role", methods=["POST"])
@admin_required
def admin_set_role(person_slug):
    role = request.form.get("role") or ""
    return _admin_mutate_account(person_slug, accounts.set_role, role)


@bp.route("/admin/accounts/<person_slug>/link-person", methods=["POST"])
@admin_required
def admin_set_account_person(person_slug):
    """Re-bind an account to a different (unbound) Person — the fix for an
    account that ended up attached to the wrong Person, most commonly the
    very first account auto-creating a brand-new Person instead of
    reusing one that already existed (see accounts.set_person)."""
    target_slug = request.form.get("target_person_slug") or ""

    def _sync_own_session():
        if session.get("person_slug") == person_slug:
            session["person_slug"] = target_slug

    return _admin_mutate_account(
        person_slug, accounts.set_person, target_slug, on_success=_sync_own_session
    )


@bp.route("/admin/accounts/<person_slug>/reset-password", methods=["GET", "POST"])
@admin_required
def admin_reset_password(person_slug):
    """An admin setting a new password directly — the only recovery path
    for a family member who's forgotten theirs, since this app has no
    email and therefore no self-service reset flow. Unlike a self-service
    change, this never needs the old password."""
    people_dir = _people_dir()
    account = accounts.get_account(people_dir, person_slug)
    if account is None:
        abort(404)
    person = people.get_person(people_dir, person_slug)

    if request.method == "POST":
        new_password = request.form.get("new_password") or ""
        confirm_password = request.form.get("confirm_password") or ""
        error = None
        if new_password != confirm_password:
            error = "Passwords don't match."
        else:
            try:
                accounts.set_password(people_dir, person_slug, new_password)
            except ValueError as exc:
                error = str(exc)
        if error:
            flash(error, "error")
        else:
            return redirect(url_for("pages.admin_accounts"))

    return render_template(
        "admin_reset_password.html", account=account,
        person_name=person.name if person else account.username,
    )


def _bind_and_create(people_dir, person_slug, new_person_name):
    """Shared validation for admin_new_account/admin_review_pending: pick
    an existing unbound Person or create a new one from a name. Returns
    (resolved_person_slug, error_message_or_None)."""
    unbound_slugs = {
        p.slug for p in people.list_people(people_dir) if accounts.get_account(people_dir, p.slug) is None
    }
    if not person_slug and not new_person_name:
        return None, "Pick an existing family member, or enter a name for a new one."
    if person_slug and person_slug not in unbound_slugs:
        return None, "That family member already has an account."
    if not person_slug:
        person_slug = people.create_person(people_dir, new_person_name)
    return person_slug, None


@bp.route("/admin/accounts/new", methods=["GET", "POST"])
@admin_required
def admin_new_account():
    """Admin-direct account creation, bypassing the request queue entirely
    — for a family member who won't submit their own request."""
    people_dir = _people_dir()
    unbound_people = [
        p for p in people.list_people(people_dir) if accounts.get_account(people_dir, p.slug) is None
    ]

    if request.method == "POST":
        person_slug = request.form.get("person_slug") or None
        new_person_name = (request.form.get("new_person_name") or "").strip()
        username = (request.form.get("username") or "").strip().lower()
        password = request.form.get("password") or ""
        role = request.form.get("role") or "family"

        error = None
        if role not in accounts.ROLES:
            error = "Invalid role."
        else:
            person_slug, error = _bind_and_create(people_dir, person_slug, new_person_name)

        if error is None:
            try:
                accounts.create_account(
                    people_dir, person_slug, username, password, role,
                    approved_by=session.get("account_username"),
                )
            except (ValueError, FileNotFoundError) as exc:
                error = str(exc)

        if error:
            flash(error, "error")
        else:
            return redirect(url_for("pages.admin_accounts"))

    return render_template(
        "admin_new_account.html", unbound_people=unbound_people, roles=accounts.ROLES
    )


@bp.route("/admin/accounts/pending/<username>", methods=["GET", "POST"])
@admin_required
def admin_review_pending(username):
    stories_dir = current_app.config["STORIES_DIR"]
    people_dir = storage.people_dir(stories_dir)
    pending = accounts.get_pending(stories_dir, username)
    if pending is None:
        abort(404)
    unbound_people = [
        p for p in people.list_people(people_dir) if accounts.get_account(people_dir, p.slug) is None
    ]

    if request.method == "POST":
        person_slug = request.form.get("person_slug") or None
        new_person_name = (request.form.get("new_person_name") or "").strip()
        role = request.form.get("role") or "family"

        error = None
        if role not in accounts.ROLES:
            error = "Invalid role."
        else:
            person_slug, error = _bind_and_create(people_dir, person_slug, new_person_name)

        if error is None:
            try:
                accounts.approve_pending(
                    stories_dir, username, role, person_slug=person_slug,
                    approved_by=session.get("account_username"),
                )
            except (ValueError, FileNotFoundError) as exc:
                error = str(exc)

        if error:
            flash(error, "error")
        else:
            return redirect(url_for("pages.admin_accounts"))

    return render_template(
        "admin_review_pending.html", pending=pending, unbound_people=unbound_people,
        roles=accounts.ROLES,
    )


@bp.route("/admin/accounts/pending/<username>/reject", methods=["POST"])
@admin_required
def admin_reject_pending(username):
    accounts.reject_pending(current_app.config["STORIES_DIR"], username)
    return redirect(url_for("pages.admin_accounts"))


# --- Account self-service (password change) ---------------------------------


def _own_account_or_404():
    """Guard shared by every /account/* route: accounts mode on and a real
    (non-delegate) account logged in — session["person_slug"] is only ever
    set by those. Returns the people_dir for convenience."""
    if not current_app.config["ACCOUNTS_ENABLED"] or not session.get("person_slug"):
        abort(404)
    return _people_dir()


@bp.route("/account")
@login_required
def account_home():
    _own_account_or_404()
    return render_template("account_home.html")


@bp.route("/account/password", methods=["GET", "POST"])
@login_required
def account_password():
    people_dir = _own_account_or_404()
    success = False

    if request.method == "POST":
        current_password = request.form.get("current_password") or ""
        new_password = request.form.get("new_password") or ""
        confirm_password = request.form.get("confirm_password") or ""

        error = None
        if accounts.verify_login(people_dir, session["account_username"], current_password) is None:
            error = "Current password is incorrect."
        elif new_password != confirm_password:
            error = "New passwords don't match."
        else:
            try:
                accounts.set_password(people_dir, session["person_slug"], new_password)
            except ValueError as exc:
                error = str(exc)

        if error:
            flash(error, "error")
        else:
            # Refresh this session's own session_version — set_password just
            # bumped it, and without this the very next request would lock
            # out the person who just successfully changed their password,
            # not only (as intended) every other already-open session.
            account = accounts.get_account_by_username(people_dir, session["account_username"])
            set_session_for_account(account)
            success = True

    return render_template("account_password.html", success=success)


# --- Delegated write-links (FEATURES.md F19 Phase 3) ------------------------


def _link_status(link):
    """The one-word status account_write_links.html/admin_accounts.html
    show — computed here rather than with date math in Jinja."""
    if link.revoked:
        return "revoked"
    if link.single_use and link.used_at:
        return "used"
    if link.expires_at and datetime.now() > link.expires_at:
        return "expired"
    return "active"


@bp.route("/account/write-links", methods=["GET", "POST"])
@login_required
def account_write_links():
    """A logged-in account holder's own share-to-write links: create one,
    see history, revoke."""
    people_dir = _own_account_or_404()
    person_slug = session["person_slug"]
    new_link_url = None

    if request.method == "POST":
        label = (request.form.get("label") or "").strip() or None
        single_use = "single_use" in request.form
        expires_raw = (request.form.get("expires_days") or "").strip()
        expires_in_days = int(expires_raw) if expires_raw.isdigit() else None
        link, token = write_links.create_link(
            people_dir, person_slug, label=label,
            expires_in_days=expires_in_days, single_use=single_use,
        )
        new_link_url = url_for("pages.use_write_link", token=token, _external=True)

    link_rows = [
        {"link": link, "status": _link_status(link)}
        for link in write_links.list_links(people_dir, person_slug)
    ]
    return render_template(
        "account_write_links.html", link_rows=link_rows, new_link_url=new_link_url
    )


@bp.route("/account/write-links/<person_slug>/<link_id>/revoke", methods=["POST"])
@login_required
def revoke_write_link(person_slug, link_id):
    if session.get("role") != "admin" and session.get("person_slug") != person_slug:
        abort(404)
    try:
        write_links.revoke_link(_people_dir(), person_slug, link_id)
    except FileNotFoundError:
        abort(404)
    if session.get("person_slug") == person_slug:
        return redirect(url_for("pages.account_write_links"))
    return redirect(url_for("pages.admin_accounts"))


@bp.route("/w/<token>")
def use_write_link(token):
    """Opening a valid link always starts a fresh delegate session,
    discarding whatever session (if any) was there before — never lets a
    logged-in account holder's own session bleed into a scoped delegate
    one, or vice versa."""
    if not current_app.config["ACCOUNTS_ENABLED"]:
        abort(404)
    link = write_links.find_by_token(_people_dir(), token)
    if link is None or not write_links.is_link_valid(link):
        return render_template("write_link_invalid.html"), 404
    session.clear()
    session["delegate_person_slug"] = link.person_slug
    session["delegate_link_id"] = link.id
    return redirect(url_for("pages.delegate_write"))


def _neutralize_html(text):
    """Escape raw `<`/`>` so a delegate write-link submission can never
    inject a `<script>` (or any other tag) that later renders unescaped —
    render_markdown() passes raw HTML straight through and every template
    renders the result with `|safe`, which REVIEW.md accepted only because
    "the only author is the trusted password-holder." A write-link
    (FEATURES.md F19 Phase 3) is deliberately handed to someone who is NOT
    an account holder, so that assumption doesn't hold on this path —
    unlike every other place a story is created. Markdown syntax itself
    never needs a literal `<`/`>`, so this can't break normal formatting."""
    return text.replace("<", "&lt;").replace(">", "&gt;")


@bp.route("/w/write", methods=["GET", "POST"])
@delegate_required
def delegate_write():
    """The delegate's entire world: write one story, submit, done. No
    photos (kept deliberately text-only to avoid the multi-step upload
    flow the real editor needs), no nav into the rest of the book, no
    editing anything after submission — a multi-use link lets someone
    come back and submit another new story, not revise a previous one."""
    people_dir = _people_dir()
    person_slug = session["delegate_person_slug"]
    link_id = session["delegate_link_id"]
    person = people.get_person(people_dir, person_slug)
    if person is None:
        abort(404)

    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        date_raw = request.form.get("date") or ""
        body = _neutralize_html(request.form.get("markdown") or "")

        error = None
        try:
            story_date = date.fromisoformat(date_raw)
        except ValueError:
            error = "Enter a valid date."
        if not title:
            error = "Enter a title."

        if error:
            flash(error, "error")
        else:
            story_id = storage.create_story(
                current_app.config["STORIES_DIR"], title, story_date, body, author=person.name
            )
            write_links.mark_used(people_dir, person_slug, link_id, story_id)
            link = write_links.get_link(people_dir, person_slug, link_id)
            if link.single_use:
                session.clear()
            return render_template("delegate_thanks.html", person_name=person.name)

    return render_template("delegate_write.html", person_name=person.name, today=date.today())
