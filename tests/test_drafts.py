"""Tests for FEATURES.md F6: drafts."""

from datetime import date

from app import storage


def test_timeline_excludes_draft_stories(auth_client, stories_dir):
    storage.create_story(stories_dir, "Published", date(2026, 1, 1), "")
    storage.create_story(stories_dir, "A draft", date(2026, 1, 2), "", draft=True)

    resp = auth_client.get("/")
    html = resp.data.decode()
    assert "Published" in html
    assert "A draft" not in html


def test_timeline_shows_drafts_link_only_when_drafts_exist(auth_client, stories_dir):
    storage.create_story(stories_dir, "Published", date(2026, 1, 1), "")

    resp = auth_client.get("/")
    assert b"Drafts (" not in resp.data

    storage.create_story(stories_dir, "A draft", date(2026, 1, 2), "", draft=True)
    resp = auth_client.get("/")
    assert b"Drafts (1)" in resp.data


def test_draft_story_page_renders_with_pill_and_direct_url_works(auth_client, stories_dir):
    story_id = storage.create_story(stories_dir, "A draft", date(2026, 1, 2), "body", draft=True)
    resp = auth_client.get(f"/story/{story_id}")
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "story__draft-pill" in html
    assert "DRAFT" in html


def test_published_story_page_has_no_draft_pill(auth_client, stories_dir):
    story_id = storage.create_story(stories_dir, "Published", date(2026, 1, 2), "body")
    resp = auth_client.get(f"/story/{story_id}")
    html = resp.data.decode()
    assert "story__draft-pill" not in html


def test_drafts_page_lists_drafts_sorted_by_updated_desc(auth_client, stories_dir):
    import time

    id1 = storage.create_story(stories_dir, "First draft", date(2026, 1, 1), "", draft=True)
    time.sleep(0.01)
    id2 = storage.create_story(stories_dir, "Second draft", date(2026, 1, 2), "", draft=True)
    storage.create_story(stories_dir, "Published", date(2026, 1, 3), "")

    resp = auth_client.get("/drafts")
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "Published" not in html
    assert html.index("Second draft") < html.index("First draft")


def test_drafts_page_empty_state(auth_client):
    resp = auth_client.get("/drafts")
    assert resp.status_code == 200
    assert b"No drafts" in resp.data


def test_draft_chip_defaults_off_for_new_story(auth_client):
    resp = auth_client.get("/new")
    html = resp.data.decode()
    import re

    assert re.search(r'id="draft-toggle"[^>]*aria-pressed="false"', html, re.DOTALL)
