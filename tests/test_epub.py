"""Tests for FEATURES.md-adjacent EPUB export (/book.epub)."""

import xml.etree.ElementTree as etree
import zipfile
from datetime import date
from io import BytesIO

from app import storage


def test_epub_requires_auth(client):
    resp = client.get("/book.epub")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_epub_mimetype_entry_is_first_and_stored(auth_client, stories_dir):
    storage.create_story(stories_dir, "Story", date(2026, 1, 1), "body")
    resp = auth_client.get("/book.epub")
    assert resp.status_code == 200
    assert resp.headers["Content-Type"] == "application/epub+zip"

    zf = zipfile.ZipFile(BytesIO(resp.data))
    infos = zf.infolist()
    assert infos[0].filename == "mimetype"
    assert infos[0].compress_type == zipfile.ZIP_STORED
    assert zf.read("mimetype") == b"application/epub+zip"


def test_epub_has_valid_structure(auth_client, stories_dir):
    storage.create_story(stories_dir, "First story", date(2026, 1, 1), "Hello world")
    storage.create_story(stories_dir, "Second story", date(2026, 2, 1), "Another one")

    resp = auth_client.get("/book.epub")
    zf = zipfile.ZipFile(BytesIO(resp.data))
    names = zf.namelist()

    assert "META-INF/container.xml" in names
    assert "OEBPS/content.opf" in names
    assert "OEBPS/nav.xhtml" in names
    assert "OEBPS/cover.xhtml" in names
    assert "OEBPS/story-0.xhtml" in names
    assert "OEBPS/story-1.xhtml" in names

    # Well-formed XML sanity check for the generated documents.
    etree.fromstring(zf.read("OEBPS/content.opf"))
    etree.fromstring(zf.read("OEBPS/nav.xhtml"))
    etree.fromstring(zf.read("OEBPS/story-0.xhtml"))
    etree.fromstring(zf.read("META-INF/container.xml"))


def test_epub_contains_story_titles_and_body(auth_client, stories_dir):
    storage.create_story(stories_dir, "First story", date(2026, 1, 1), "Hello **world**")

    resp = auth_client.get("/book.epub")
    zf = zipfile.ZipFile(BytesIO(resp.data))
    story_xhtml = zf.read("OEBPS/story-0.xhtml").decode()
    assert "First story" in story_xhtml
    assert "<strong>world</strong>" in story_xhtml


def test_epub_excludes_drafts_and_sealed(auth_client, stories_dir):
    storage.create_story(stories_dir, "Published", date(2026, 1, 1), "visible")
    storage.create_story(stories_dir, "A draft", date(2026, 2, 1), "draft body", draft=True)
    storage.create_story(
        stories_dir, "A sealed letter", date(2026, 3, 1), "secret body", unlock=date(2040, 1, 1)
    )

    resp = auth_client.get("/book.epub")
    zf = zipfile.ZipFile(BytesIO(resp.data))
    all_text = "".join(zf.read(n).decode() for n in zf.namelist() if n.endswith(".xhtml"))
    assert "Published" in all_text
    assert "A draft" not in all_text
    assert "A sealed letter" not in all_text


def test_epub_embeds_story_images(auth_client, stories_dir, jpeg_bytes):
    from werkzeug.datastructures import FileStorage

    story_id = storage.create_story(
        stories_dir, "Photo story", date(2026, 1, 1), "![A caption](photo-001.jpg)"
    )
    buf = jpeg_bytes(color="red", size=(50, 50))
    filename = storage.save_image(stories_dir, story_id, FileStorage(stream=buf, filename="p.jpg"))
    expected_bytes = (stories_dir / story_id / filename).read_bytes()

    resp = auth_client.get("/book.epub")
    zf = zipfile.ZipFile(BytesIO(resp.data))
    image_path = f"OEBPS/images/{story_id}__{filename}"
    assert image_path in zf.namelist()
    assert zf.read(image_path) == expected_bytes

    story_xhtml = zf.read("OEBPS/story-0.xhtml").decode()
    assert f'src="images/{story_id}__{filename}"' in story_xhtml


def test_epub_smarty_entities_converted_to_unicode(auth_client, stories_dir):
    storage.create_story(
        stories_dir, "Story", date(2026, 1, 1),
        'An em-dash -- and an ellipsis... and "smart quotes."',
    )
    resp = auth_client.get("/book.epub")
    zf = zipfile.ZipFile(BytesIO(resp.data))
    story_xhtml = zf.read("OEBPS/story-0.xhtml").decode()

    # Well-formed XML is the real assertion: named HTML entities like
    # &mdash;/&hellip;/&rdquo; are invalid in strict XML without a DTD.
    etree.fromstring(story_xhtml)
    assert "&mdash;" not in story_xhtml
    assert "&hellip;" not in story_xhtml
    assert "–" in story_xhtml  # en dash (smarty converts "--" to an en dash)
    assert "…" in story_xhtml  # ellipsis


def test_epub_cover_page_shows_title_and_year_range(auth_client, stories_dir):
    storage.create_story(stories_dir, "Early", date(2022, 1, 1), "")
    storage.create_story(stories_dir, "Late", date(2025, 1, 1), "")

    resp = auth_client.get("/book.epub")
    zf = zipfile.ZipFile(BytesIO(resp.data))
    cover = zf.read("OEBPS/cover.xhtml").decode()
    assert "Storybook" in cover
    assert "Stories from 2022 to 2025" in cover


def test_epub_filename_uses_configured_title(tmp_path, monkeypatch):
    from app import create_app

    monkeypatch.setenv("STORYBOOK_STORIES_DIR", str(tmp_path))
    monkeypatch.setenv("STORYBOOK_TITLE", "Le livre de Milo")
    monkeypatch.setenv("STORYBOOK_PASSWORD", "test-password")
    monkeypatch.setenv("STORYBOOK_SECRET_KEY", "test-secret")
    app = create_app()
    app.config["WTF_CSRF_ENABLED"] = False
    client = app.test_client()
    client.post("/login", data={"password": "test-password"})

    resp = client.get("/book.epub")
    assert "le-livre-de-milo.epub" in resp.headers["Content-Disposition"]
