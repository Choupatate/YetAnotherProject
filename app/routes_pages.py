from datetime import date

from flask import Blueprint, abort, current_app, render_template, send_from_directory

from . import storage
from .auth import login_required
from .rendering import render_markdown

bp = Blueprint("pages", __name__)


@bp.route("/")
@login_required
def timeline():
    stories = storage.list_stories(current_app.config["STORIES_DIR"])
    years = {}
    for story in stories:
        years.setdefault(story.date.year, []).append(story)
    return render_template("timeline.html", years=sorted(years.items()), stories=stories)


@bp.route("/story/<story_id>")
@login_required
def story(story_id):
    s = storage.get_story(current_app.config["STORIES_DIR"], story_id)
    if s is None:
        abort(404)
    body_html = render_markdown(s.body, story_id)
    return render_template("story.html", story=s, body_html=body_html)


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
    return render_template("editor.html", story=None, today=date.today())


@bp.route("/edit/<story_id>")
@login_required
def edit_story(story_id):
    s = storage.get_story(current_app.config["STORIES_DIR"], story_id)
    if s is None:
        abort(404)
    return render_template("editor.html", story=s, today=date.today())
