"""Tests for editor autosave-to-localStorage.

The recovery flow itself (localStorage read/write, banner, Restore/Discard)
is pure client-side JS with no pytest coverage; it's exercised manually with
a headless browser (see conversation notes). These tests cover the
server-rendered contract editor.js depends on: the recovery banner markup
and the data hooks it reads (setMarkdown support doesn't apply here, but the
banner's ids and the story-id data attribute do)."""

from datetime import date

from app import storage


def test_editor_includes_recovery_banner_markup(auth_client):
    resp = auth_client.get("/new")
    html = resp.data.decode()
    assert 'id="editor-recovery"' in html
    assert "hidden" in html
    assert 'id="editor-recovery-time"' in html
    assert 'id="editor-recovery-restore"' in html
    assert 'id="editor-recovery-discard"' in html


def test_editor_recovery_banner_present_when_editing_existing_story(auth_client, stories_dir):
    story_id = storage.create_story(stories_dir, "Story", date(2026, 1, 1), "body")
    resp = auth_client.get(f"/edit/{story_id}")
    html = resp.data.decode()
    assert 'id="editor-recovery"' in html
