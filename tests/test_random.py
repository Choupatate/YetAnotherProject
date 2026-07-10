"""Tests for FEATURES.md F15: "Au hasard" — open a page at random."""

from datetime import date

from app import storage


def test_random_redirects_to_an_eligible_story(auth_client, stories_dir):
    story_id = storage.create_story(stories_dir, "Only story", date(2026, 1, 1), "")
    resp = auth_client.get("/random")
    assert resp.status_code == 302
    assert resp.headers["Location"] == f"/story/{story_id}"


def test_random_never_returns_excluded_id(auth_client, stories_dir):
    id1 = storage.create_story(stories_dir, "First", date(2026, 1, 1), "")
    id2 = storage.create_story(stories_dir, "Second", date(2026, 1, 2), "")

    for _ in range(30):
        resp = auth_client.get(f"/random?not={id1}")
        assert resp.status_code == 302
        assert resp.headers["Location"] == f"/story/{id2}"


def test_random_excludes_drafts(auth_client, stories_dir):
    storage.create_story(stories_dir, "A draft", date(2026, 1, 1), "", draft=True)
    resp = auth_client.get("/random")
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/"


def test_random_excludes_sealed_letters(auth_client, stories_dir):
    storage.create_story(
        stories_dir, "Sealed", date(2026, 1, 1), "", unlock=date(2040, 1, 1)
    )
    resp = auth_client.get("/random")
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/"


def test_random_excludes_archived(auth_client, stories_dir):
    storage.create_story(stories_dir, "Archived", date(2026, 1, 1), "", archived=True)
    resp = auth_client.get("/random")
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/"


def test_random_excludes_instants(auth_client, stories_dir):
    storage.create_story(
        stories_dir, "An instant", date(2026, 1, 1), "line", kind="instant"
    )
    resp = auth_client.get("/random")
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/"


def test_random_empty_case_redirects_to_timeline(auth_client):
    resp = auth_client.get("/random")
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/"


def test_random_requires_auth(client):
    resp = client.get("/random")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_random_only_candidate_excluded_falls_back_to_timeline(auth_client, stories_dir):
    story_id = storage.create_story(stories_dir, "Only story", date(2026, 1, 1), "")
    resp = auth_client.get(f"/random?not={story_id}")
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/"


# --- entry points ------------------------------------------------------------------


def test_timeline_links_to_random(auth_client, stories_dir):
    storage.create_story(stories_dir, "Story", date(2026, 1, 1), "")
    resp = auth_client.get("/")
    html = resp.data.decode()
    assert 'href="/random"' in html
    assert "Open a page at random" in html


def test_story_page_has_at_random_link_with_not_param(auth_client, stories_dir):
    story_id = storage.create_story(stories_dir, "Story", date(2026, 1, 1), "")
    resp = auth_client.get(f"/story/{story_id}")
    html = resp.data.decode()
    assert "story__random" in html
    assert f"/random?not={story_id}" in html
    assert "At random" in html


def test_story_page_at_random_link_present_even_without_prev_next(auth_client, stories_dir):
    story_id = storage.create_story(stories_dir, "Only story", date(2026, 1, 1), "")
    resp = auth_client.get(f"/story/{story_id}")
    html = resp.data.decode()
    assert "story__prev" not in html
    assert "story__next" not in html
    assert "story__random" in html
