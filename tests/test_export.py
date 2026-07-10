"""Tests for FEATURES.md F8: one-tap backup."""

import zipfile
from datetime import date
from io import BytesIO

from app import storage


def test_export_requires_auth(client):
    resp = client.get("/export")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_export_zip_contains_same_files_and_bytes(auth_client, stories_dir):
    story_id = storage.create_story(stories_dir, "Backup me", date(2026, 1, 1), "Hello **world**")
    index_bytes = (stories_dir / story_id / "index.md").read_bytes()

    resp = auth_client.get("/export")
    assert resp.status_code == 200
    assert resp.headers["Content-Type"] == "application/zip"
    assert f"storybook-backup-{date.today().isoformat()}.zip" in resp.headers["Content-Disposition"]

    zf = zipfile.ZipFile(BytesIO(resp.data))
    names = zf.namelist()
    assert f"{story_id}/index.md" in names
    assert zf.read(f"{story_id}/index.md") == index_bytes


def test_export_excludes_tmp_leftovers(auth_client, stories_dir):
    story_id = storage.create_story(stories_dir, "Story", date(2026, 1, 1), "body")
    (stories_dir / story_id / "index.md.tmp").write_text("garbage", encoding="utf-8")

    resp = auth_client.get("/export")
    zf = zipfile.ZipFile(BytesIO(resp.data))
    names = zf.namelist()
    assert f"{story_id}/index.md" in names
    assert f"{story_id}/index.md.tmp" not in names


def test_export_preserves_on_disk_folder_structure(auth_client, stories_dir):
    from werkzeug.datastructures import FileStorage

    from PIL import Image

    story_id = storage.create_story(stories_dir, "Photo story", date(2026, 1, 1), "")
    buf = BytesIO()
    Image.new("RGB", (50, 50), color="green").save(buf, format="JPEG")
    buf.seek(0)
    filename = storage.save_image(stories_dir, story_id, FileStorage(stream=buf, filename="p.jpg"))

    resp = auth_client.get("/export")
    zf = zipfile.ZipFile(BytesIO(resp.data))
    assert f"{story_id}/{filename}" in zf.namelist()
