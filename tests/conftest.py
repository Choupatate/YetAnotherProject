from io import BytesIO

import pytest
from PIL import Image

from app import create_app, storage

BASE_TEST_CONFIG = {
    "TESTING": True,
    "PASSWORD": "test-password",
    "SECRET_KEY": "test-secret-key",
}


@pytest.fixture
def stories_dir(tmp_path):
    d = tmp_path / "stories"
    d.mkdir()
    return d


@pytest.fixture
def people_dir(stories_dir):
    return stories_dir / "people"


@pytest.fixture
def app_factory(stories_dir):
    """A configured app sharing this test's stories_dir, for tests that need
    a non-default config key (AUTHORS, BIRTHDATE, CHILD_SLUG, ...) without
    repeating the whole base test_config block to get it."""
    def _make(**extra_config):
        return create_app(
            test_config={"STORIES_DIR": stories_dir, **BASE_TEST_CONFIG, **extra_config}
        )
    return _make


@pytest.fixture
def app(app_factory):
    return app_factory()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def auth_client(client):
    client.post("/login", data={"password": "test-password"})
    return client


@pytest.fixture
def auth_client_factory(app_factory):
    """A logged-in client for an app_factory(**extra_config) variant, built
    and logged in in one call."""
    def _make(**extra_config):
        c = app_factory(**extra_config).test_client()
        c.post("/login", data={"password": "test-password"})
        return c
    return _make


@pytest.fixture
def jpeg_bytes():
    """An in-memory JPEG, sized/colored per call — the "just need a valid
    uploadable image" case used throughout the upload/photo tests."""
    def _make(color="red", size=(50, 50)):
        buf = BytesIO()
        Image.new("RGB", size, color=color).save(buf, format="JPEG")
        buf.seek(0)
        return buf
    return _make


@pytest.fixture
def heic_bytes():
    """Same idea as jpeg_bytes, but HEIC — for exercising the pillow-heif
    conversion path (FEATURES.md F11)."""
    def _make(color="green", size=(100, 100)):
        buf = BytesIO()
        Image.new("RGB", size, color=color).save(buf, format="HEIF", quality=80)
        buf.seek(0)
        return buf
    return _make


@pytest.fixture
def make_story():
    """A storage.Story with created/updated defaulted to None — the shape
    every purely in-memory (no filesystem) storage-function test needs."""
    def _make(id_, date_, title=None, **kwargs):
        return storage.Story(
            id=id_, title=title if title is not None else id_, date=date_,
            created=None, updated=None, **kwargs,
        )
    return _make
