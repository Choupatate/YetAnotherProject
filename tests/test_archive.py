"""Tests for the archive feature: a softer, reversible alternative to
deletion. Archived stories are hidden from every listing (timeline, drafts,
book, prev/next, on-this-day) but remain fully reachable and readable at
their direct URL, same philosophy as drafts and sealed letters."""

from datetime import date

from app import storage


# --- storage round-trip -------------------------------------------------------


def test_create_story_with_archived_round_trips(stories_dir):
    story_id = storage.create_story(stories_dir, "Story", date(2026, 1, 1), "body", archived=True)
    story = storage.get_story(stories_dir, story_id)
    assert story.archived is True
    raw = (stories_dir / story_id / "index.md").read_text()
    assert "archived: true" in raw


def test_create_story_without_archived_omits_field(stories_dir):
    story_id = storage.create_story(stories_dir, "Story", date(2026, 1, 1), "body")
    story = storage.get_story(stories_dir, story_id)
    assert story.archived is False
    raw = (stories_dir / story_id / "index.md").read_text()
    assert "archived" not in raw


def test_save_story_sets_and_clears_archived(stories_dir):
    story_id = storage.create_story(stories_dir, "Story", date(2026, 1, 1), "body", archived=True)
    storage.save_story(stories_dir, story_id, "Story", date(2026, 1, 1), "body", archived=False)
    story = storage.get_story(stories_dir, story_id)
    assert story.archived is False


def test_readable_stories_excludes_archived():
    today = date(2026, 1, 1)
    published = storage.Story(id="a", title="Published", date=date(2025, 1, 1), created=None, updated=None)
    archived = storage.Story(
        id="b", title="Archived", date=date(2025, 2, 1), created=None, updated=None, archived=True
    )
    result = storage.readable_stories([published, archived], today=today)
    assert [s.id for s in result] == ["a"]


# --- timeline / drafts --------------------------------------------------------


def test_timeline_excludes_archived_stories(auth_client, stories_dir):
    storage.create_story(stories_dir, "Published", date(2026, 1, 1), "")
    storage.create_story(stories_dir, "Put away", date(2026, 1, 2), "", archived=True)

    resp = auth_client.get("/")
    html = resp.data.decode()
    assert "Published" in html
    assert "Put away" not in html


def test_timeline_shows_archived_link_only_when_present(auth_client, stories_dir):
    storage.create_story(stories_dir, "Published", date(2026, 1, 1), "")
    resp = auth_client.get("/")
    assert b"Archived (" not in resp.data

    storage.create_story(stories_dir, "Put away", date(2026, 1, 2), "", archived=True)
    resp = auth_client.get("/")
    assert b"Archived (1)" in resp.data


def test_archived_draft_excluded_from_drafts_listing(auth_client, stories_dir):
    storage.create_story(
        stories_dir, "Draft and archived", date(2026, 1, 1), "", draft=True, archived=True
    )
    resp = auth_client.get("/drafts")
    html = resp.data.decode()
    assert "Draft and archived" not in html
    assert b"Drafts (" not in auth_client.get("/").data


# --- archived page -------------------------------------------------------------


def test_archived_page_lists_archived_sorted_by_updated_desc(auth_client, stories_dir):
    import time

    storage.create_story(stories_dir, "First archived", date(2026, 1, 1), "", archived=True)
    time.sleep(0.01)
    storage.create_story(stories_dir, "Second archived", date(2026, 1, 2), "", archived=True)
    storage.create_story(stories_dir, "Published", date(2026, 1, 3), "")

    resp = auth_client.get("/archived")
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "Published" not in html
    assert html.index("Second archived") < html.index("First archived")


def test_archived_page_empty_state(auth_client):
    resp = auth_client.get("/archived")
    assert resp.status_code == 200
    assert b"Nothing archived" in resp.data


def test_archived_page_requires_auth(client):
    resp = client.get("/archived")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


# --- story page pill and direct access -----------------------------------------


def test_archived_story_page_shows_pill_and_direct_url_works(auth_client, stories_dir):
    story_id = storage.create_story(stories_dir, "Put away", date(2026, 1, 1), "body", archived=True)
    resp = auth_client.get(f"/story/{story_id}")
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "story__archived-pill" in html
    assert "ARCHIVED" in html


def test_published_story_page_has_no_archived_pill(auth_client, stories_dir):
    story_id = storage.create_story(stories_dir, "Published", date(2026, 1, 1), "body")
    resp = auth_client.get(f"/story/{story_id}")
    html = resp.data.decode()
    assert "story__archived-pill" not in html


# --- reading order / book / on-this-day -----------------------------------------


def test_archived_story_excluded_from_prev_next(auth_client, stories_dir):
    first_id = storage.create_story(stories_dir, "First", date(2026, 1, 1), "")
    storage.create_story(stories_dir, "Archived middle", date(2026, 1, 2), "", archived=True)
    last_id = storage.create_story(stories_dir, "Last", date(2026, 1, 3), "")

    resp = auth_client.get(f"/story/{last_id}")
    html = resp.data.decode()
    assert "First" in html
    assert "Archived middle" not in html


def test_archived_own_page_has_no_prev_next(auth_client, stories_dir):
    storage.create_story(stories_dir, "First", date(2026, 1, 1), "")
    archived_id = storage.create_story(stories_dir, "Archived", date(2026, 1, 2), "", archived=True)
    storage.create_story(stories_dir, "Last", date(2026, 1, 3), "")

    resp = auth_client.get(f"/story/{archived_id}")
    html = resp.data.decode()
    assert "story__prev" not in html
    assert "story__next" not in html


def test_book_excludes_archived_stories(auth_client, stories_dir):
    storage.create_story(stories_dir, "Published", date(2026, 1, 1), "visible body")
    storage.create_story(stories_dir, "Put away", date(2026, 1, 2), "hidden body", archived=True)

    resp = auth_client.get("/book")
    html = resp.data.decode()
    assert "Published" in html
    assert "Put away" not in html
    assert "hidden body" not in html


def test_on_this_day_excludes_archived():
    today = date(2026, 6, 18)
    archived = storage.Story(
        id="a", title="Archived", date=date(2023, 6, 18), created=None, updated=None, archived=True
    )
    result = storage.on_this_day([archived], today=today)
    assert result == []


# --- editor UI -----------------------------------------------------------------


def test_editor_shows_archive_toggle_default_off(auth_client):
    resp = auth_client.get("/new")
    html = resp.data.decode()
    import re

    assert re.search(r'id="archive-toggle"[^>]*aria-pressed="false"', html, re.DOTALL)


def test_editor_preselects_archive_toggle_when_editing_archived(auth_client, stories_dir):
    story_id = storage.create_story(stories_dir, "Story", date(2026, 1, 1), "body", archived=True)
    resp = auth_client.get(f"/edit/{story_id}")
    html = resp.data.decode()
    import re

    assert re.search(r'id="archive-toggle"[^>]*aria-pressed="true"', html, re.DOTALL)


# --- API -------------------------------------------------------------------------


def test_api_create_with_archived(auth_client, stories_dir):
    resp = auth_client.post(
        "/api/stories",
        json={"title": "Story", "date": "2026-01-01", "markdown": "", "archived": True},
    )
    assert resp.status_code == 200
    story_id = resp.get_json()["id"]
    story = storage.get_story(stories_dir, story_id)
    assert story.archived is True


def test_api_update_can_clear_archived(auth_client, stories_dir):
    story_id = storage.create_story(stories_dir, "Story", date(2026, 1, 1), "body", archived=True)
    resp = auth_client.put(
        f"/api/stories/{story_id}",
        json={"title": "Story", "date": "2026-01-01", "markdown": "body", "archived": False},
    )
    assert resp.status_code == 200
    story = storage.get_story(stories_dir, story_id)
    assert story.archived is False
