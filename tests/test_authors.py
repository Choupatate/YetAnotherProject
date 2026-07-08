"""Tests for FEATURES.md F1: multi-author shared timeline."""

import re
from datetime import date

import pytest

from app import create_app, storage

AUTHORS_CONFIG = [
    {"name": "Papa", "color": "#d9a441"},
    {"name": "Maman", "color": "#7ba7d9"},
]


@pytest.fixture
def authored_app(tmp_path):
    stories_dir = tmp_path / "stories"
    stories_dir.mkdir()
    return create_app(
        test_config={
            "STORIES_DIR": stories_dir,
            "TESTING": True,
            "PASSWORD": "test-password",
            "SECRET_KEY": "test-secret-key",
            "AUTHORS": AUTHORS_CONFIG,
        }
    )


@pytest.fixture
def authored_stories_dir(authored_app):
    return authored_app.config["STORIES_DIR"]


@pytest.fixture
def authored_client(authored_app):
    return authored_app.test_client()


@pytest.fixture
def authored_auth_client(authored_client):
    authored_client.post("/login", data={"password": "test-password"})
    return authored_client


# --- Config parsing --------------------------------------------------------


def test_authors_unset_disables_feature(monkeypatch, tmp_path):
    monkeypatch.delenv("STORYBOOK_AUTHORS", raising=False)
    monkeypatch.setenv("STORYBOOK_STORIES_DIR", str(tmp_path))

    app = create_app()
    assert app.config["AUTHORS"] == []


def test_authors_valid_config_parses_in_order(monkeypatch, tmp_path):
    monkeypatch.setenv("STORYBOOK_AUTHORS", "Papa:#d9a441,Maman:#7ba7d9")
    monkeypatch.setenv("STORYBOOK_STORIES_DIR", str(tmp_path))

    app = create_app()
    assert app.config["AUTHORS"] == [
        {"name": "Papa", "color": "#d9a441"},
        {"name": "Maman", "color": "#7ba7d9"},
    ]


@pytest.mark.parametrize(
    "value",
    [
        "Papa",
        "Papa-nocolor",
        "Papa:notahexcolor",
        "Papa:#zzzzzz",
        ":#d9a441",
        "Papa:#d9a441,Papa:#7ba7d9",
    ],
)
def test_authors_malformed_config_raises(monkeypatch, tmp_path, value):
    monkeypatch.setenv("STORYBOOK_AUTHORS", value)
    monkeypatch.setenv("STORYBOOK_STORIES_DIR", str(tmp_path))

    with pytest.raises(RuntimeError):
        create_app()


# --- Storage round-trip ------------------------------------------------------


def test_create_story_with_author_round_trips(authored_stories_dir):
    story_id = storage.create_story(
        authored_stories_dir, "Story", date(2026, 1, 1), "body", author="Papa"
    )
    story = storage.get_story(authored_stories_dir, story_id)
    assert story.author == "Papa"
    raw = (authored_stories_dir / story_id / "index.md").read_text()
    assert "author: Papa" in raw


def test_create_story_without_author_omits_field(authored_stories_dir):
    story_id = storage.create_story(authored_stories_dir, "Story", date(2026, 1, 1), "body")
    story = storage.get_story(authored_stories_dir, story_id)
    assert story.author is None
    raw = (authored_stories_dir / story_id / "index.md").read_text()
    assert "author:" not in raw


def test_save_story_omitting_author_keeps_existing(authored_stories_dir):
    story_id = storage.create_story(
        authored_stories_dir, "Story", date(2026, 1, 1), "body", author="Papa"
    )
    storage.save_story(authored_stories_dir, story_id, "Story", date(2026, 1, 1), "new body")
    story = storage.get_story(authored_stories_dir, story_id)
    assert story.author == "Papa"


def test_save_story_empty_author_clears_it(authored_stories_dir):
    story_id = storage.create_story(
        authored_stories_dir, "Story", date(2026, 1, 1), "body", author="Papa"
    )
    storage.save_story(
        authored_stories_dir, story_id, "Story", date(2026, 1, 1), "new body", author=""
    )
    story = storage.get_story(authored_stories_dir, story_id)
    assert story.author is None


# --- API validation ----------------------------------------------------------


def test_api_create_with_valid_author(authored_auth_client, authored_stories_dir):
    resp = authored_auth_client.post(
        "/api/stories",
        json={"title": "Story", "date": "2026-01-01", "markdown": "", "author": "Papa"},
    )
    assert resp.status_code == 200
    story_id = resp.get_json()["id"]
    story = storage.get_story(authored_stories_dir, story_id)
    assert story.author == "Papa"


def test_api_create_with_unknown_author_returns_400(authored_auth_client):
    resp = authored_auth_client.post(
        "/api/stories",
        json={"title": "Story", "date": "2026-01-01", "markdown": "", "author": "Grandma"},
    )
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_api_create_author_ignored_when_not_configured(auth_client, stories_dir):
    resp = auth_client.post(
        "/api/stories",
        json={"title": "Story", "date": "2026-01-01", "markdown": "", "author": "Anyone"},
    )
    assert resp.status_code == 200
    story_id = resp.get_json()["id"]
    story = storage.get_story(stories_dir, story_id)
    assert story.author is None


def test_api_update_can_change_author(authored_auth_client, authored_stories_dir):
    story_id = storage.create_story(
        authored_stories_dir, "Story", date(2026, 1, 1), "body", author="Papa"
    )
    resp = authored_auth_client.put(
        f"/api/stories/{story_id}",
        json={"title": "Story", "date": "2026-01-01", "markdown": "body", "author": "Maman"},
    )
    assert resp.status_code == 200
    story = storage.get_story(authored_stories_dir, story_id)
    assert story.author == "Maman"


def test_api_update_unknown_author_returns_400(authored_auth_client, authored_stories_dir):
    story_id = storage.create_story(authored_stories_dir, "Story", date(2026, 1, 1), "body")
    resp = authored_auth_client.put(
        f"/api/stories/{story_id}",
        json={"title": "Story", "date": "2026-01-01", "markdown": "body", "author": "Grandma"},
    )
    assert resp.status_code == 400


# --- Page rendering -----------------------------------------------------------


def test_timeline_shows_legend_and_bylines_when_configured(authored_auth_client, authored_stories_dir):
    storage.create_story(authored_stories_dir, "Papa's story", date(2026, 1, 1), "", author="Papa")
    storage.create_story(authored_stories_dir, "Maman's story", date(2026, 1, 2), "", author="Maman")
    storage.create_story(authored_stories_dir, "No author story", date(2026, 1, 3), "")

    resp = authored_auth_client.get("/")
    html = resp.data.decode()
    assert "timeline__legend" in html
    assert "Papa" in html
    assert "Maman" in html
    assert "timeline__dot--author" in html


def test_timeline_hides_author_ui_when_not_configured(auth_client, stories_dir):
    storage.create_story(stories_dir, "Legacy story", date(2026, 1, 1), "", author="Ghost")

    resp = auth_client.get("/")
    html = resp.data.decode()
    assert "timeline__legend" not in html
    assert "timeline__dot--author" not in html
    assert "Ghost" not in html


def test_story_page_shows_byline_when_configured(authored_auth_client, authored_stories_dir):
    story_id = storage.create_story(
        authored_stories_dir, "Story", date(2026, 1, 1), "body", author="Maman"
    )
    resp = authored_auth_client.get(f"/story/{story_id}")
    html = resp.data.decode()
    assert "story__author" in html
    assert "Maman" in html
    assert "#7ba7d9" in html


def test_story_page_hides_byline_when_not_configured(auth_client, stories_dir):
    story_id = storage.create_story(stories_dir, "Story", date(2026, 1, 1), "body", author="Ghost")
    resp = auth_client.get(f"/story/{story_id}")
    html = resp.data.decode()
    assert "story__author" not in html
    assert "Ghost" not in html


def test_story_page_unknown_author_renders_neutral(authored_auth_client, authored_stories_dir):
    story_id = storage.create_story(
        authored_stories_dir, "Story", date(2026, 1, 1), "body", author="Grandma"
    )
    resp = authored_auth_client.get(f"/story/{story_id}")
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "Grandma" in html
    assert "#d9a441" not in html
    assert "#7ba7d9" not in html


def test_editor_shows_chips_when_configured_and_preselects_on_edit(
    authored_auth_client, authored_stories_dir
):
    story_id = storage.create_story(
        authored_stories_dir, "Story", date(2026, 1, 1), "body", author="Maman"
    )
    resp = authored_auth_client.get(f"/edit/{story_id}")
    html = resp.data.decode()
    assert "editor__authors" in html
    assert re.search(r'data-author-name="Maman"[^>]*aria-pressed="true"', html, re.DOTALL)
    assert re.search(r'data-author-name="Papa"[^>]*aria-pressed="false"', html, re.DOTALL)


def test_editor_hides_chips_when_not_configured(auth_client):
    resp = auth_client.get("/new")
    html = resp.data.decode()
    assert "editor__authors" not in html
