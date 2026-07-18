"""Tests for FEATURES.md F19 Phase 4: real per-account authorship
replacing F1's STORYBOOK_AUTHORS chip picker when accounts mode is on."""

import pytest

from app import accounts, people, storage
from tests.conftest import _bootstrap_admin, _login, _people_dir


@pytest.fixture
def accounts_app(app_factory):
    return app_factory(ACCOUNTS_ENABLED=True)


@pytest.fixture
def accounts_client(accounts_app):
    return accounts_app.test_client()


# --- automatic attribution on create ----------------------------------------


def test_creating_a_story_auto_attributes_to_logged_in_account(accounts_client, accounts_app):
    _bootstrap_admin(accounts_client)
    _login(accounts_client, "papa", "hunter22")

    resp = accounts_client.post(
        "/api/stories", json={"title": "A story", "date": "2026-01-01", "markdown": ""}
    )
    assert resp.status_code == 200
    story = storage.get_story(accounts_app.config["STORIES_DIR"], resp.get_json()["id"])
    assert story.author == "Papa"


def test_creating_a_story_ignores_a_spoofed_author_field(accounts_client, accounts_app):
    """Even if a client sends an author, accounts mode never trusts it —
    the session's own bound Person always wins."""
    _bootstrap_admin(accounts_client)
    _login(accounts_client, "papa", "hunter22")

    resp = accounts_client.post(
        "/api/stories",
        json={"title": "A story", "date": "2026-01-01", "markdown": "", "author": "Someone Else"},
    )
    assert resp.status_code == 200
    story = storage.get_story(accounts_app.config["STORIES_DIR"], resp.get_json()["id"])
    assert story.author == "Papa"


def test_creating_an_instant_auto_attributes_too(accounts_client, accounts_app):
    _bootstrap_admin(accounts_client)
    _login(accounts_client, "papa", "hunter22")

    resp = accounts_client.post(
        "/api/stories", json={"kind": "instant", "date": "2026-01-01", "markdown": ""}
    )
    assert resp.status_code == 200
    story = storage.get_story(accounts_app.config["STORIES_DIR"], resp.get_json()["id"])
    assert story.author == "Papa"


def test_editing_a_story_does_not_reassign_its_author(accounts_client, accounts_app):
    _bootstrap_admin(accounts_client)
    _login(accounts_client, "papa", "hunter22")
    resp = accounts_client.post(
        "/api/stories", json={"title": "A story", "date": "2026-01-01", "markdown": ""}
    )
    story_id = resp.get_json()["id"]

    from app import people as people_module

    milo = people_module.create_person(_people_dir(accounts_app), "Milo")
    accounts.create_account(_people_dir(accounts_app), milo, "milo", "milosecret1", "family")
    _login(accounts_client, "milo", "milosecret1")

    accounts_client.put(
        f"/api/stories/{story_id}", json={"title": "Edited title", "date": "2026-01-01", "markdown": "x"}
    )
    story = storage.get_story(accounts_app.config["STORIES_DIR"], story_id)
    assert story.title == "Edited title"
    assert story.author == "Papa"


# --- byline/legend colors derived from accounts, not config -----------------


def test_timeline_legend_shows_account_holders_with_default_color(accounts_client, accounts_app):
    _bootstrap_admin(accounts_client)
    _login(accounts_client, "papa", "hunter22")
    accounts_client.post(
        "/api/stories", json={"title": "A story", "date": "2026-01-01", "markdown": ""}
    )

    resp = accounts_client.get("/")
    html = resp.data.decode()
    assert "timeline__legend" in html
    assert "Papa" in html
    from app.routes_pages import DEFAULT_AUTHOR_COLOR

    assert DEFAULT_AUTHOR_COLOR in html


def test_timeline_legend_uses_persons_own_author_color(accounts_client, accounts_app):
    _bootstrap_admin(accounts_client)
    _login(accounts_client, "papa", "hunter22")
    papa_slug = accounts.get_account_by_username(_people_dir(accounts_app), "papa").person_slug
    people.update_person(_people_dir(accounts_app), papa_slug, "Papa", author_color="#123456")

    accounts_client.post(
        "/api/stories", json={"title": "A story", "date": "2026-01-01", "markdown": ""}
    )
    resp = accounts_client.get("/")
    assert "#123456" in resp.data.decode()


# --- editor UI hides the manual chip picker in accounts mode ----------------


def test_new_story_editor_hides_author_chip_picker_in_accounts_mode(accounts_client):
    _bootstrap_admin(accounts_client)
    _login(accounts_client, "papa", "hunter22")
    resp = accounts_client.get("/new")
    assert b"editor__authors" not in resp.data


def test_new_instant_editor_hides_author_chip_picker_in_accounts_mode(accounts_client):
    _bootstrap_admin(accounts_client)
    _login(accounts_client, "papa", "hunter22")
    resp = accounts_client.get("/new-instant")
    assert b"editor__authors" not in resp.data


def test_person_editor_shows_author_color_picker_in_accounts_mode(accounts_client):
    _bootstrap_admin(accounts_client)
    _login(accounts_client, "papa", "hunter22")
    resp = accounts_client.get("/new-person")
    assert b'name="author_color"' in resp.data


def test_person_editor_hides_author_color_picker_when_accounts_disabled(auth_client):
    resp = auth_client.get("/new-person")
    assert b'name="author_color"' not in resp.data


# --- accounts disabled: F1 completely untouched -----------------------------


def test_f1_author_picker_unaffected_when_accounts_disabled(app_factory):
    app = app_factory(AUTHORS=[{"name": "Papa", "color": "#d9a441"}])
    client = app.test_client()
    client.post("/login", data={"password": "test-password"})
    resp = client.get("/new")
    assert b"editor__authors" in resp.data
