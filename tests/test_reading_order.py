"""Tests for FEATURES.md F2: reading order (previous/next)."""

from datetime import date

from app import storage


def test_middle_story_has_prev_and_next_links_in_order(auth_client, stories_dir):
    first_id = storage.create_story(stories_dir, "First story", date(2026, 1, 1), "")
    middle_id = storage.create_story(stories_dir, "Middle story", date(2026, 1, 2), "")
    third_id = storage.create_story(stories_dir, "Third story", date(2026, 1, 3), "")

    resp = auth_client.get(f"/story/{middle_id}")
    html = resp.data.decode()
    assert f'href="/story/{first_id}"' in html
    assert f'href="/story/{third_id}"' in html
    assert html.index(f"/story/{first_id}") < html.index(f"/story/{third_id}")
    assert 'rel="prev"' in html
    assert 'rel="next"' in html


def test_first_story_omits_prev_link(auth_client, stories_dir):
    first_id = storage.create_story(stories_dir, "First story", date(2026, 1, 1), "")
    storage.create_story(stories_dir, "Second story", date(2026, 1, 2), "")

    resp = auth_client.get(f"/story/{first_id}")
    html = resp.data.decode()
    assert "story__prev" not in html
    assert "story__next" in html
    assert 'rel="prev"' not in html


def test_last_story_omits_next_link(auth_client, stories_dir):
    storage.create_story(stories_dir, "First story", date(2026, 1, 1), "")
    last_id = storage.create_story(stories_dir, "Second story", date(2026, 1, 2), "")

    resp = auth_client.get(f"/story/{last_id}")
    html = resp.data.decode()
    assert "story__prev" in html
    assert "story__next" not in html
    assert 'rel="next"' not in html


def test_only_story_omits_both_links(auth_client, stories_dir):
    only_id = storage.create_story(stories_dir, "Only story", date(2026, 1, 1), "")
    resp = auth_client.get(f"/story/{only_id}")
    html = resp.data.decode()
    assert "story__prev" not in html
    assert "story__next" not in html


def test_draft_and_sealed_between_two_published_are_skipped(auth_client, stories_dir):
    first_id = storage.create_story(stories_dir, "First story", date(2026, 1, 1), "")
    storage.create_story(stories_dir, "A draft", date(2026, 1, 2), "", draft=True)
    storage.create_story(stories_dir, "A sealed letter", date(2026, 1, 3), "", unlock=date(2040, 1, 1))
    last_id = storage.create_story(stories_dir, "Last story", date(2026, 1, 4), "")

    resp = auth_client.get(f"/story/{last_id}")
    html = resp.data.decode()
    assert "First story" in html
    assert "A draft" not in html

    resp = auth_client.get(f"/story/{first_id}")
    html = resp.data.decode()
    assert "Last story" in html
    assert "A sealed letter" not in html


def test_draft_story_own_page_renders_without_prev_next(auth_client, stories_dir):
    storage.create_story(stories_dir, "First story", date(2026, 1, 1), "")
    draft_id = storage.create_story(stories_dir, "A draft", date(2026, 1, 2), "", draft=True)
    storage.create_story(stories_dir, "Third story", date(2026, 1, 3), "")

    resp = auth_client.get(f"/story/{draft_id}")
    html = resp.data.decode()
    assert "story__prev" not in html
    assert "story__next" not in html


def test_long_title_truncated_with_ellipsis(auth_client, stories_dir):
    long_title = "A" * 60
    storage.create_story(stories_dir, long_title, date(2026, 1, 1), "")
    second_id = storage.create_story(stories_dir, "Second", date(2026, 1, 2), "")

    resp = auth_client.get(f"/story/{second_id}")
    html = resp.data.decode()
    assert long_title not in html
    assert "…" in html


def test_story_js_only_loaded_on_story_page(auth_client, stories_dir):
    story_id = storage.create_story(stories_dir, "A story", date(2026, 1, 1), "")

    resp = auth_client.get(f"/story/{story_id}")
    assert b"js/story.js" in resp.data

    resp = auth_client.get("/")
    assert b"js/story.js" not in resp.data
