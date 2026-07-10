"""Tests for client-side timeline search and jump-to-latest.

The filtering/scrolling itself is pure client-side JS (see timeline.js) and
is exercised manually with a headless browser; these tests cover the
server-rendered markup that script depends on."""

from datetime import date

from app import storage


def test_timeline_includes_search_and_jump_markup_when_stories_exist(auth_client, stories_dir):
    storage.create_story(stories_dir, "A story", date(2026, 1, 1), "")
    resp = auth_client.get("/")
    html = resp.data.decode()
    assert 'id="timeline-search"' in html
    assert 'id="timeline-jump-latest"' in html
    assert 'id="timeline-search-empty"' in html


def test_timeline_empty_state_has_no_search_markup(auth_client):
    resp = auth_client.get("/")
    html = resp.data.decode()
    assert "No stories yet" in html
    assert 'id="timeline-search"' not in html
