"""Tests for FEATURES.md F29: the "Growing up" birthday photo wall route."""

from datetime import date

import pytest
from werkzeug.datastructures import FileStorage

from app import storage


@pytest.fixture
def dated_app(app_factory):
    return app_factory(BIRTHDATE=date(2020, 6, 18))


@pytest.fixture
def dated_stories_dir(dated_app):
    return dated_app.config["STORIES_DIR"]


@pytest.fixture
def dated_auth_client(dated_app):
    client = dated_app.test_client()
    client.post("/login", data={"password": "test-password"})
    return client


def _story_with_cover(stories_dir, title, story_date, jpeg_bytes):
    story_id = storage.create_story(stories_dir, title, story_date, "body")
    buf = jpeg_bytes(color="red", size=(200, 200))
    filename = storage.save_image(stories_dir, story_id, FileStorage(stream=buf, filename="c.jpg"))
    story = storage.get_story(stories_dir, story_id)
    storage.save_story(stories_dir, story_id, story.title, story.date, story.body, cover=filename)
    return story_id


def test_growth_requires_auth(client):
    resp = client.get("/growth")
    assert resp.status_code == 302


def test_growth_empty_state_when_no_birthdate(auth_client):
    resp = auth_client.get("/growth")
    html = resp.data.decode()
    assert "STORYBOOK_BIRTHDATE" in html


def test_growth_empty_state_when_no_photos(dated_auth_client):
    resp = dated_auth_client.get("/growth")
    html = resp.data.decode()
    assert "take its place here" in html


def test_growth_lists_nearest_photo_per_birthday(dated_auth_client, dated_stories_dir, jpeg_bytes):
    story_id = _story_with_cover(dated_stories_dir, "First birthday", date(2021, 6, 20), jpeg_bytes)
    resp = dated_auth_client.get("/growth")
    html = resp.data.decode()
    assert "Newborn" in html
    assert "Turning 1" in html
    assert f'href="/story/{story_id}"' in html


def test_timeline_shows_growth_link_only_when_photos_exist(dated_auth_client, dated_stories_dir, jpeg_bytes):
    resp = dated_auth_client.get("/")
    assert b">Growing up<" not in resp.data

    _story_with_cover(dated_stories_dir, "First birthday", date(2020, 6, 20), jpeg_bytes)
    resp = dated_auth_client.get("/")
    assert b">Growing up<" in resp.data


def test_growth_excludes_drafts_and_sealed(dated_auth_client, dated_stories_dir, jpeg_bytes):
    story_id = _story_with_cover(dated_stories_dir, "Draft photo", date(2020, 6, 20), jpeg_bytes)
    story = storage.get_story(dated_stories_dir, story_id)
    storage.save_story(
        dated_stories_dir, story_id, story.title, story.date, story.body,
        cover=story.cover, draft=True,
    )
    resp = dated_auth_client.get("/growth")
    html = resp.data.decode()
    assert "take its place here" in html
