from datetime import date, datetime

from flask import Blueprint, abort, current_app, render_template, send_from_directory

from . import storage
from .auth import login_required
from .rendering import render_markdown

bp = Blueprint("pages", __name__)


@bp.route("/")
@login_required
def timeline():
    all_stories = storage.list_stories(current_app.config["STORIES_DIR"])
    stories = [s for s in all_stories if not s.draft]
    draft_count = sum(1 for s in all_stories if s.draft)
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
        today=date.today(),
    )


@bp.route("/drafts")
@login_required
def drafts():
    all_stories = storage.list_stories(current_app.config["STORIES_DIR"])
    draft_stories = [s for s in all_stories if s.draft]
    draft_stories.sort(key=lambda s: s.updated or datetime.min, reverse=True)
    authors = current_app.config.get("AUTHORS") or []
    author_colors = {a["name"]: a["color"] for a in authors}
    return render_template(
        "drafts.html", stories=draft_stories, authors=authors, author_colors=author_colors
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
    return render_template(
        "story.html", story=s, body_html=body_html, authors=authors, author_color=author_color
    )


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
