"""Tests for FEATURES.md F0: story visibility groundwork (draft/unlock)."""

from datetime import date

from app import storage


# --- storage.is_sealed / readable_stories -----------------------------------


def test_is_sealed_true_when_unlock_in_future():
    story = storage.Story(
        id="x", title="T", date=date(2026, 1, 1), created=None, updated=None,
        unlock=date(2030, 1, 1),
    )
    assert storage.is_sealed(story, today=date(2026, 1, 1)) is True


def test_is_sealed_false_when_unlock_in_past_or_today():
    past = storage.Story(
        id="x", title="T", date=date(2026, 1, 1), created=None, updated=None,
        unlock=date(2020, 1, 1),
    )
    today_unlock = storage.Story(
        id="y", title="T", date=date(2026, 1, 1), created=None, updated=None,
        unlock=date(2026, 1, 1),
    )
    assert storage.is_sealed(past, today=date(2026, 1, 1)) is False
    assert storage.is_sealed(today_unlock, today=date(2026, 1, 1)) is False


def test_is_sealed_false_when_no_unlock():
    story = storage.Story(id="x", title="T", date=date(2026, 1, 1), created=None, updated=None)
    assert storage.is_sealed(story, today=date(2026, 1, 1)) is False


def test_readable_stories_excludes_drafts_and_sealed():
    today = date(2026, 1, 1)
    published = storage.Story(id="a", title="Published", date=date(2025, 1, 1), created=None, updated=None)
    draft = storage.Story(id="b", title="Draft", date=date(2025, 2, 1), created=None, updated=None, draft=True)
    sealed = storage.Story(
        id="c", title="Sealed", date=date(2025, 3, 1), created=None, updated=None,
        unlock=date(2030, 1, 1),
    )
    result = storage.readable_stories([published, draft, sealed], today=today)
    assert [s.id for s in result] == ["a"]


def test_readable_stories_sorted_date_ascending():
    today = date(2026, 1, 1)
    later = storage.Story(id="later", title="Later", date=date(2025, 6, 1), created=None, updated=None)
    earlier = storage.Story(id="earlier", title="Earlier", date=date(2025, 1, 1), created=None, updated=None)
    result = storage.readable_stories([later, earlier], today=today)
    assert [s.id for s in result] == ["earlier", "later"]


# --- storage round-trip -------------------------------------------------------


def test_create_story_with_draft_and_unlock_round_trips(stories_dir):
    story_id = storage.create_story(
        stories_dir, "Story", date(2026, 1, 1), "body", draft=True, unlock=date(2040, 6, 18)
    )
    story = storage.get_story(stories_dir, story_id)
    assert story.draft is True
    assert story.unlock == date(2040, 6, 18)
    raw = (stories_dir / story_id / "index.md").read_text()
    assert "draft: true" in raw
    assert "2040-06-18" in raw


def test_create_story_without_draft_or_unlock_omits_fields(stories_dir):
    story_id = storage.create_story(stories_dir, "Story", date(2026, 1, 1), "body")
    story = storage.get_story(stories_dir, story_id)
    assert story.draft is False
    assert story.unlock is None
    raw = (stories_dir / story_id / "index.md").read_text()
    assert "draft" not in raw
    assert "unlock" not in raw


def test_save_story_sets_and_clears_draft_and_unlock(stories_dir):
    story_id = storage.create_story(
        stories_dir, "Story", date(2026, 1, 1), "body", draft=True, unlock=date(2040, 6, 18)
    )
    storage.save_story(
        stories_dir, story_id, "Story", date(2026, 1, 1), "new body", draft=False, unlock=None
    )
    story = storage.get_story(stories_dir, story_id)
    assert story.draft is False
    assert story.unlock is None


def test_unlock_bad_value_on_disk_parses_as_none(stories_dir):
    story_id = storage.create_story(stories_dir, "Story", date(2026, 1, 1), "body")
    index_path = stories_dir / story_id / "index.md"
    text = index_path.read_text()
    text = text.replace("---\n", "---\nunlock: not-a-date\n", 1)
    index_path.write_text(text, encoding="utf-8")

    story = storage.get_story(stories_dir, story_id)
    assert story.unlock is None


# --- API validation ------------------------------------------------------------


def test_api_create_with_draft_and_unlock(auth_client, stories_dir):
    resp = auth_client.post(
        "/api/stories",
        json={
            "title": "Story", "date": "2026-01-01", "markdown": "",
            "draft": True, "unlock": "2040-06-18",
        },
    )
    assert resp.status_code == 200
    story_id = resp.get_json()["id"]
    story = storage.get_story(stories_dir, story_id)
    assert story.draft is True
    assert story.unlock == date(2040, 6, 18)


def test_api_create_invalid_unlock_returns_400(auth_client):
    resp = auth_client.post(
        "/api/stories",
        json={"title": "Story", "date": "2026-01-01", "markdown": "", "unlock": "not-a-date"},
    )
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_api_update_can_clear_draft_and_unlock(auth_client, stories_dir):
    story_id = storage.create_story(
        stories_dir, "Story", date(2026, 1, 1), "body", draft=True, unlock=date(2040, 6, 18)
    )
    resp = auth_client.put(
        f"/api/stories/{story_id}",
        json={"title": "Story", "date": "2026-01-01", "markdown": "body", "draft": False, "unlock": ""},
    )
    assert resp.status_code == 200
    story = storage.get_story(stories_dir, story_id)
    assert story.draft is False
    assert story.unlock is None


# --- editor UI -----------------------------------------------------------------


def test_editor_shows_draft_toggle_and_unlock_input(auth_client):
    resp = auth_client.get("/new")
    html = resp.data.decode()
    assert 'id="draft-toggle"' in html
    assert 'id="story-unlock"' in html
    assert 'aria-pressed="false"' in html


def test_editor_preselects_draft_and_unlock_when_editing(auth_client, stories_dir):
    story_id = storage.create_story(
        stories_dir, "Story", date(2026, 1, 1), "body", draft=True, unlock=date(2040, 6, 18)
    )
    resp = auth_client.get(f"/edit/{story_id}")
    html = resp.data.decode()
    import re

    assert re.search(r'id="draft-toggle"[^>]*aria-pressed="true"', html, re.DOTALL)
    assert 'value="2040-06-18"' in html
