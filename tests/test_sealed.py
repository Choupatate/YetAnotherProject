"""Tests for FEATURES.md F4: sealed letters."""

from datetime import date, timedelta

from app import storage

FUTURE = date.today() + timedelta(days=365)
PAST = date.today() - timedelta(days=1)


def test_sealed_story_page_shows_envelope_not_body(auth_client, stories_dir):
    story_id = storage.create_story(
        stories_dir, "Secret title", date(2026, 1, 1), "secret body", unlock=FUTURE
    )
    resp = auth_client.get(f"/story/{story_id}")
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "sealed__illo" in html
    assert "A sealed letter" in html
    assert "Secret title" not in html
    assert "secret body" not in html
    assert "story__edit" not in html


def test_sealed_story_page_shows_author_and_open_date(auth_client, stories_dir):
    story_id = storage.create_story(
        stories_dir, "Secret", date(2026, 1, 1), "body", author="Papa", unlock=date(2040, 6, 18)
    )
    resp = auth_client.get(f"/story/{story_id}")
    html = resp.data.decode()
    assert "from Papa" in html
    assert "June 18, 2040" in html


def test_unlock_date_in_past_renders_normally(auth_client, stories_dir):
    story_id = storage.create_story(
        stories_dir, "No longer secret", date(2026, 1, 1), "now visible", unlock=PAST
    )
    resp = auth_client.get(f"/story/{story_id}")
    html = resp.data.decode()
    assert "No longer secret" in html
    assert "now visible" in html
    assert "sealed__illo" not in html


def test_timeline_shows_envelope_entry_for_sealed_story(auth_client, stories_dir):
    storage.create_story(
        stories_dir, "Secret title", date(2026, 1, 1), "body", unlock=date(2040, 6, 18)
    )
    resp = auth_client.get("/")
    html = resp.data.decode()
    assert "timeline__envelope" in html
    assert "A sealed letter" in html
    assert "opens June 18, 2040" in html
    assert "Secret title" not in html


def test_timeline_sealed_entry_hides_thumbnail(auth_client, stories_dir):
    from io import BytesIO

    from PIL import Image
    from werkzeug.datastructures import FileStorage

    story_id = storage.create_story(
        stories_dir, "Secret", date(2026, 1, 1), "body", unlock=date(2040, 6, 18)
    )
    buf = BytesIO()
    Image.new("RGB", (200, 200), color="red").save(buf, format="JPEG")
    buf.seek(0)
    filename = storage.save_image(stories_dir, story_id, FileStorage(stream=buf, filename="c.jpg"))
    story = storage.get_story(stories_dir, story_id)
    storage.save_story(
        stories_dir, story_id, story.title, story.date, story.body, cover=filename,
        unlock=date(2040, 6, 18),
    )

    resp = auth_client.get("/")
    html = resp.data.decode()
    assert "timeline__thumb" not in html


def test_edit_route_still_works_for_sealed_story(auth_client, stories_dir):
    story_id = storage.create_story(
        stories_dir, "Secret", date(2026, 1, 1), "body", unlock=date(2040, 6, 18)
    )
    resp = auth_client.get(f"/edit/{story_id}")
    assert resp.status_code == 200
    assert b"Secret" in resp.data
