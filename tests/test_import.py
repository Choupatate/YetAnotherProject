"""Tests for restoring a backup zip (from /export) via /import."""

import zipfile
from datetime import date
from io import BytesIO
from pathlib import Path

import pytest

from app import storage


def _export_zip(source_dir):
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for path in sorted(Path(source_dir).rglob("*")):
            if path.is_dir():
                continue
            zf.write(path, path.relative_to(source_dir))
    buf.seek(0)
    return buf


# --- storage.import_backup ----------------------------------------------------


def test_import_backup_restores_into_empty_dir(tmp_path, stories_dir):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    story_id = storage.create_story(source_dir, "Restored story", date(2026, 1, 1), "body")

    count = storage.import_backup(stories_dir, _export_zip(source_dir))

    assert count == 1
    story = storage.get_story(stories_dir, story_id)
    assert story.title == "Restored story"
    assert story.body.strip() == "body"


def test_import_backup_rejects_on_collision_writes_nothing(tmp_path, stories_dir):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    story_id = storage.create_story(source_dir, "Story", date(2026, 1, 1), "new body")
    storage.create_story(stories_dir, "Story", date(2026, 1, 1), "existing body")

    zip_buf = _export_zip(source_dir)
    with pytest.raises(storage.ImportCollision) as exc_info:
        storage.import_backup(stories_dir, zip_buf)
    assert story_id in exc_info.value.colliding_ids

    assert len(list(stories_dir.iterdir())) == 1
    existing = storage.get_story(stories_dir, story_id)
    assert existing.body.strip() == "existing body"


def test_import_backup_rejects_path_traversal(stories_dir):
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("../evil.txt", "pwned")
    buf.seek(0)
    with pytest.raises(ValueError):
        storage.import_backup(stories_dir, buf)


def test_import_backup_rejects_unexpected_root_files(stories_dir):
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("readme.txt", "hi")
    buf.seek(0)
    with pytest.raises(ValueError):
        storage.import_backup(stories_dir, buf)


def test_import_backup_rejects_empty_zip(stories_dir):
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w"):
        pass
    buf.seek(0)
    with pytest.raises(ValueError):
        storage.import_backup(stories_dir, buf)


def test_import_backup_rejects_bad_zip(stories_dir):
    buf = BytesIO(b"not a zip file")
    with pytest.raises(zipfile.BadZipFile):
        storage.import_backup(stories_dir, buf)


def test_import_backup_includes_images(tmp_path, stories_dir):
    from io import BytesIO as BIO

    from PIL import Image
    from werkzeug.datastructures import FileStorage

    source_dir = tmp_path / "source"
    source_dir.mkdir()
    story_id = storage.create_story(source_dir, "Photo story", date(2026, 1, 1), "")
    img_buf = BIO()
    Image.new("RGB", (50, 50), color="blue").save(img_buf, format="JPEG")
    img_buf.seek(0)
    filename = storage.save_image(
        source_dir, story_id, FileStorage(stream=img_buf, filename="p.jpg")
    )

    storage.import_backup(stories_dir, _export_zip(source_dir))

    assert (stories_dir / story_id / filename).is_file()


# --- API -------------------------------------------------------------------------


def test_api_import_requires_auth(client):
    resp = client.post("/api/import", data={}, content_type="multipart/form-data")
    assert resp.status_code == 302


def test_api_import_no_file_returns_400(auth_client):
    resp = auth_client.post("/api/import", data={}, content_type="multipart/form-data")
    assert resp.status_code == 400


def test_api_import_success(auth_client, stories_dir, tmp_path):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    storage.create_story(source_dir, "Restored", date(2026, 1, 1), "body")

    resp = auth_client.post(
        "/api/import",
        data={"file": (_export_zip(source_dir), "backup.zip")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 200
    assert resp.get_json()["imported"] == 1


def test_api_import_collision_returns_409(auth_client, stories_dir, tmp_path):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    storage.create_story(source_dir, "Story", date(2026, 1, 1), "new")
    storage.create_story(stories_dir, "Story", date(2026, 1, 1), "existing")

    resp = auth_client.post(
        "/api/import",
        data={"file": (_export_zip(source_dir), "backup.zip")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 409
    assert "error" in resp.get_json()


def test_api_import_bad_zip_returns_400(auth_client):
    resp = auth_client.post(
        "/api/import",
        data={"file": (BytesIO(b"not a zip"), "backup.zip")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 400


# --- page --------------------------------------------------------------------------


def test_import_page_renders(auth_client):
    resp = auth_client.get("/import")
    assert resp.status_code == 200
    assert b"Import a backup" in resp.data


def test_import_page_requires_auth(client):
    resp = client.get("/import")
    assert resp.status_code == 302
