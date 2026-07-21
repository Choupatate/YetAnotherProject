"""Tests for story version history: every save snapshots the content it's
about to overwrite into `.versions/`, so an accidental bad edit is never
unrecoverable."""

import time
from datetime import date

import pytest

from app import storage


def test_create_story_produces_no_versions(stories_dir):
    story_id = storage.create_story(stories_dir, "Story", date(2026, 1, 1), "v1")
    assert storage.list_versions(stories_dir, story_id) == []


def test_first_save_snapshots_the_created_version(stories_dir):
    story_id = storage.create_story(stories_dir, "Story", date(2026, 1, 1), "v1 body")
    storage.save_story(stories_dir, story_id, "Story", date(2026, 1, 1), "v2 body")

    versions = storage.list_versions(stories_dir, story_id)
    assert len(versions) == 1
    story = storage.get_story(stories_dir, story_id)
    assert story.body.strip() == "v2 body"


def test_multiple_saves_create_versions_newest_first(stories_dir):
    story_id = storage.create_story(stories_dir, "V1 title", date(2026, 1, 1), "v1 body")
    time.sleep(0.01)
    storage.save_story(stories_dir, story_id, "V2 title", date(2026, 1, 1), "v2 body")
    time.sleep(0.01)
    storage.save_story(stories_dir, story_id, "V3 title", date(2026, 1, 1), "v3 body")

    versions = storage.list_versions(stories_dir, story_id)
    assert len(versions) == 2
    assert [v["title"] for v in versions] == ["V2 title", "V1 title"]


def test_versions_pruned_beyond_cap(stories_dir, monkeypatch):
    monkeypatch.setattr(storage, "MAX_VERSIONS", 3)
    story_id = storage.create_story(stories_dir, "Story", date(2026, 1, 1), "body 0")
    for i in range(1, 6):
        time.sleep(0.001)
        storage.save_story(stories_dir, story_id, "Story", date(2026, 1, 1), f"body {i}")

    versions = storage.list_versions(stories_dir, story_id)
    assert len(versions) == 3


def test_restore_version_restores_content(stories_dir):
    story_id = storage.create_story(stories_dir, "Original title", date(2026, 1, 1), "original body")
    time.sleep(0.01)
    storage.save_story(stories_dir, story_id, "Changed title", date(2026, 1, 1), "changed body")

    versions = storage.list_versions(stories_dir, story_id)
    assert len(versions) == 1
    storage.restore_version(stories_dir, story_id, versions[0]["id"])

    story = storage.get_story(stories_dir, story_id)
    assert story.title == "Original title"
    assert story.body.strip() == "original body"


def test_restore_version_snapshots_current_before_replacing(stories_dir):
    story_id = storage.create_story(stories_dir, "Original title", date(2026, 1, 1), "original body")
    time.sleep(0.01)
    storage.save_story(stories_dir, story_id, "Changed title", date(2026, 1, 1), "changed body")

    versions_before = storage.list_versions(stories_dir, story_id)
    storage.restore_version(stories_dir, story_id, versions_before[0]["id"])

    versions_after = storage.list_versions(stories_dir, story_id)
    assert len(versions_after) == 2
    assert versions_after[0]["title"] == "Changed title"


def test_restore_version_reproduces_author_draft_unlock_archived(stories_dir):
    story_id = storage.create_story(
        stories_dir, "Story", date(2026, 1, 1), "body",
        author="Papa", draft=True, unlock=date(2040, 1, 1), archived=True,
    )
    time.sleep(0.01)
    storage.save_story(
        stories_dir, story_id, "Story", date(2026, 1, 1), "new body",
        author="", draft=False, unlock=None, archived=False,
    )

    versions = storage.list_versions(stories_dir, story_id)
    storage.restore_version(stories_dir, story_id, versions[0]["id"])

    story = storage.get_story(stories_dir, story_id)
    assert story.author == "Papa"
    assert story.draft is True
    assert story.unlock == date(2040, 1, 1)
    assert story.archived is True


def test_restore_version_reproduces_people_tags_sources(stories_dir):
    story_id = storage.create_story(
        stories_dir, "Story", date(2026, 1, 1), "body",
        people=["grandma"], tags=["beach"], sources=[{"url": "https://example.com", "note": "x"}],
    )
    time.sleep(0.01)
    storage.save_story(
        stories_dir, story_id, "Story", date(2026, 1, 1), "new body",
        people=[], tags=[], sources=[],
    )

    versions = storage.list_versions(stories_dir, story_id)
    storage.restore_version(stories_dir, story_id, versions[0]["id"])

    story = storage.get_story(stories_dir, story_id)
    assert story.people == ["grandma"]
    assert story.tags == ["beach"]
    assert story.sources == [{"url": "https://example.com", "note": "x"}]


def test_restore_invalid_version_id_raises(stories_dir):
    story_id = storage.create_story(stories_dir, "Story", date(2026, 1, 1), "body")
    with pytest.raises(storage.InvalidVersionId):
        storage.restore_version(stories_dir, story_id, "not-a-version-id")


def test_restore_missing_version_raises(stories_dir):
    story_id = storage.create_story(stories_dir, "Story", date(2026, 1, 1), "body")
    with pytest.raises(FileNotFoundError):
        storage.restore_version(stories_dir, story_id, "20260101T000000000000")


def test_list_versions_for_missing_story_returns_empty(stories_dir):
    assert storage.list_versions(stories_dir, "2026-01-01-nope") == []


# --- API -------------------------------------------------------------------------


def test_api_restore_version_requires_auth(client, stories_dir):
    story_id = storage.create_story(stories_dir, "Story", date(2026, 1, 1), "v1")
    storage.save_story(stories_dir, story_id, "Story", date(2026, 1, 1), "v2")
    versions = storage.list_versions(stories_dir, story_id)
    resp = client.post(f"/api/stories/{story_id}/versions/{versions[0]['id']}/restore")
    assert resp.status_code == 302


def test_api_restore_version_success(auth_client, stories_dir):
    story_id = storage.create_story(stories_dir, "Story", date(2026, 1, 1), "v1")
    time.sleep(0.01)
    storage.save_story(stories_dir, story_id, "Story", date(2026, 1, 1), "v2")
    versions = storage.list_versions(stories_dir, story_id)

    resp = auth_client.post(f"/api/stories/{story_id}/versions/{versions[0]['id']}/restore")
    assert resp.status_code == 200
    story = storage.get_story(stories_dir, story_id)
    assert story.body.strip() == "v1"


def test_api_restore_version_unknown_id_returns_404(auth_client, stories_dir):
    story_id = storage.create_story(stories_dir, "Story", date(2026, 1, 1), "v1")
    resp = auth_client.post(f"/api/stories/{story_id}/versions/20260101T000000000000/restore")
    assert resp.status_code == 404


def test_api_restore_version_malformed_id_returns_404(auth_client, stories_dir):
    story_id = storage.create_story(stories_dir, "Story", date(2026, 1, 1), "v1")
    resp = auth_client.post(f"/api/stories/{story_id}/versions/not-a-version/restore")
    assert resp.status_code == 404


# --- history page ------------------------------------------------------------------


def test_story_history_page_lists_versions(auth_client, stories_dir):
    story_id = storage.create_story(stories_dir, "Original title", date(2026, 1, 1), "v1")
    time.sleep(0.01)
    storage.save_story(stories_dir, story_id, "Changed title", date(2026, 1, 1), "v2")

    resp = auth_client.get(f"/story/{story_id}/history")
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "Original title" in html
    assert "history__restore" in html


def test_story_history_page_empty_state(auth_client, stories_dir):
    story_id = storage.create_story(stories_dir, "Story", date(2026, 1, 1), "v1")
    resp = auth_client.get(f"/story/{story_id}/history")
    html = resp.data.decode()
    assert "No earlier versions yet" in html


def test_story_history_page_404_for_missing_story(auth_client):
    resp = auth_client.get("/story/2026-01-01-nope/history")
    assert resp.status_code == 404


def test_editor_shows_history_link_when_editing(auth_client, stories_dir):
    story_id = storage.create_story(stories_dir, "Story", date(2026, 1, 1), "v1")
    resp = auth_client.get(f"/edit/{story_id}")
    html = resp.data.decode()
    assert f'/story/{story_id}/history' in html
    assert "View history" in html


def test_editor_hides_history_link_for_new_story(auth_client):
    resp = auth_client.get("/new")
    html = resp.data.decode()
    assert "View history" not in html
