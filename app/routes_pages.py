import tempfile
import zipfile
from datetime import date, datetime

from flask import (
    Blueprint,
    abort,
    current_app,
    jsonify,
    render_template,
    send_file,
    send_from_directory,
    url_for,
)

from . import epub, storage
from .auth import login_required
from .rendering import render_markdown

bp = Blueprint("pages", __name__)


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
    authors = current_app.config.get("AUTHORS") or []
    author_colors = {a["name"]: a["color"] for a in authors}
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
    authors = current_app.config.get("AUTHORS") or []
    author_colors = {a["name"]: a["color"] for a in authors}
    entries = []
    for s in readable:
        full = storage.get_story(stories_dir, s.id)
        body_html = render_markdown(full.body, full.id)
        author_color = author_colors.get(full.author) if (authors and full.author) else None
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
        body_html = render_markdown(full.body, full.id)
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


@bp.route("/drafts")
@login_required
def drafts():
    all_stories = storage.list_stories(current_app.config["STORIES_DIR"])
    draft_stories = [s for s in all_stories if s.draft and not s.archived]
    draft_stories.sort(key=lambda s: s.updated or datetime.min, reverse=True)
    authors = current_app.config.get("AUTHORS") or []
    author_colors = {a["name"]: a["color"] for a in authors}
    return render_template(
        "drafts.html", stories=draft_stories, authors=authors, author_colors=author_colors
    )


@bp.route("/archived")
@login_required
def archived():
    all_stories = storage.list_stories(current_app.config["STORIES_DIR"])
    archived_stories = [s for s in all_stories if s.archived]
    archived_stories.sort(key=lambda s: s.updated or datetime.min, reverse=True)
    authors = current_app.config.get("AUTHORS") or []
    author_colors = {a["name"]: a["color"] for a in authors}
    return render_template(
        "archived.html", stories=archived_stories, authors=authors, author_colors=author_colors
    )


@bp.route("/story/<story_id>")
@login_required
def story(story_id):
    s = storage.get_story(current_app.config["STORIES_DIR"], story_id)
    if s is None:
        abort(404)
    authors = current_app.config.get("AUTHORS") or []
    author_colors = {a["name"]: a["color"] for a in authors}
    author_color = author_colors.get(s.author) if (authors and s.author) else None
    if storage.is_sealed(s):
        return render_template("sealed.html", story=s, author_color=author_color)
    body_html = render_markdown(s.body, story_id)
    prev_story, next_story = _reading_order_neighbors(current_app.config["STORIES_DIR"], s)
    return render_template(
        "story.html", story=s, body_html=body_html, authors=authors, author_color=author_color,
        prev_story=prev_story, next_story=next_story,
        birthdate=current_app.config.get("BIRTHDATE"),
    )


def _reading_order_neighbors(stories_dir, current):
    """Previous/next readable story either side of `current` (F2). None/None
    when `current` isn't itself readable (e.g. a draft or archived) or at
    either end."""
    if current.draft or current.archived:
        return None, None
    readable = storage.readable_stories(storage.list_stories(stories_dir))
    for i, r in enumerate(readable):
        if r.id == current.id:
            prev_story = readable[i - 1] if i > 0 else None
            next_story = readable[i + 1] if i < len(readable) - 1 else None
            return prev_story, next_story
    return None, None


@bp.route("/story/<story_id>/history")
@login_required
def story_history(story_id):
    s = storage.get_story(current_app.config["STORIES_DIR"], story_id)
    if s is None:
        abort(404)
    versions = storage.list_versions(current_app.config["STORIES_DIR"], story_id)
    return render_template("history.html", story=s, versions=versions)


@bp.route("/story/<story_id>/media/<filename>")
@login_required
def story_media(story_id, filename):
    if not storage.is_valid_story_id(story_id) or not storage.is_valid_filename(filename):
        abort(404)
    story_dir = current_app.config["STORIES_DIR"] / story_id
    if not (story_dir / filename).is_file():
        abort(404)
    return send_from_directory(story_dir, filename)


@bp.route("/new")
@login_required
def new_story():
    authors = current_app.config.get("AUTHORS") or []
    return render_template("editor.html", story=None, today=date.today(), authors=authors)


@bp.route("/edit/<story_id>")
@login_required
def edit_story(story_id):
    s = storage.get_story(current_app.config["STORIES_DIR"], story_id)
    if s is None:
        abort(404)
    authors = current_app.config.get("AUTHORS") or []
    return render_template("editor.html", story=s, today=date.today(), authors=authors)
