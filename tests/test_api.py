from io import BytesIO

from PIL import Image

from app import storage


def _jpeg_bytes():
    buf = BytesIO()
    Image.new("RGB", (100, 100), color="green").save(buf, format="JPEG")
    buf.seek(0)
    return buf


def _heic_bytes():
    buf = BytesIO()
    Image.new("RGB", (100, 100), color="green").save(buf, format="HEIF", quality=80)
    buf.seek(0)
    return buf


def test_create_story_via_api(auth_client, stories_dir):
    resp = auth_client.post(
        "/api/stories",
        json={"title": "New memory", "date": "2026-01-05", "markdown": "Hello **world**"},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["id"] == "2026-01-05-new-memory"

    story = storage.get_story(stories_dir, data["id"])
    assert story.title == "New memory"
    assert "Hello **world**" in story.body


def test_create_story_requires_title(auth_client):
    resp = auth_client.post("/api/stories", json={"title": "  ", "date": "2026-01-05", "markdown": ""})
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_create_story_requires_valid_date(auth_client):
    resp = auth_client.post(
        "/api/stories", json={"title": "Title", "date": "not-a-date", "markdown": ""}
    )
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_create_story_unauthenticated_redirects(client):
    resp = client.post(
        "/api/stories", json={"title": "Title", "date": "2026-01-05", "markdown": ""}
    )
    assert resp.status_code == 302


def test_update_story_via_api_keeps_id(auth_client, stories_dir):
    from datetime import date

    story_id = storage.create_story(stories_dir, "Original", date(2026, 1, 1), "old body")

    resp = auth_client.put(
        f"/api/stories/{story_id}",
        json={"title": "Updated title", "date": "2026-02-02", "markdown": "new body"},
    )
    assert resp.status_code == 200
    assert resp.get_json()["id"] == story_id

    story = storage.get_story(stories_dir, story_id)
    assert story.title == "Updated title"
    assert story.body.strip() == "new body"


def test_update_story_missing_returns_404(auth_client):
    resp = auth_client.put(
        "/api/stories/2026-01-01-does-not-exist",
        json={"title": "Title", "date": "2026-01-01", "markdown": ""},
    )
    assert resp.status_code == 404


def test_update_story_invalid_id_returns_404(auth_client):
    resp = auth_client.put(
        "/api/stories/..%2f..%2fetc",
        json={"title": "Title", "date": "2026-01-01", "markdown": ""},
    )
    assert resp.status_code == 404


def test_update_story_requires_title(auth_client, stories_dir):
    from datetime import date

    story_id = storage.create_story(stories_dir, "Original", date(2026, 1, 1), "body")
    resp = auth_client.put(
        f"/api/stories/{story_id}", json={"title": "", "date": "2026-01-01", "markdown": "b"}
    )
    assert resp.status_code == 400


def test_upload_image_returns_filename(auth_client, stories_dir):
    from datetime import date

    story_id = storage.create_story(stories_dir, "Photo story", date(2026, 1, 1), "")
    resp = auth_client.post(
        f"/api/stories/{story_id}/images",
        data={"file": (_jpeg_bytes(), "photo.jpg")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["filename"] == "photo-001.jpg"
    assert (stories_dir / story_id / "photo-001.jpg").is_file()


def test_upload_heic_image_converts_to_jpeg(auth_client, stories_dir):
    from datetime import date

    story_id = storage.create_story(stories_dir, "Heic photo story", date(2026, 1, 1), "")
    resp = auth_client.post(
        f"/api/stories/{story_id}/images",
        data={"file": (_heic_bytes(), "photo.heic")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["filename"] == "photo-001.jpg"
    saved = stories_dir / story_id / "photo-001.jpg"
    assert saved.is_file()
    with Image.open(saved) as img:
        assert img.format == "JPEG"


def test_upload_image_no_file_returns_400(auth_client, stories_dir):
    from datetime import date

    story_id = storage.create_story(stories_dir, "Photo story", date(2026, 1, 1), "")
    resp = auth_client.post(f"/api/stories/{story_id}/images", data={}, content_type="multipart/form-data")
    assert resp.status_code == 400


def test_upload_image_invalid_story_id_returns_404(auth_client):
    resp = auth_client.post(
        "/api/stories/../../etc/images",
        data={"file": (_jpeg_bytes(), "photo.jpg")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 404


def test_upload_image_nonexistent_story_returns_404(auth_client):
    resp = auth_client.post(
        "/api/stories/2026-01-01-nope/images",
        data={"file": (_jpeg_bytes(), "photo.jpg")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 404


def test_upload_image_bad_content_returns_400(auth_client, stories_dir):
    from datetime import date

    story_id = storage.create_story(stories_dir, "Photo story", date(2026, 1, 1), "")
    resp = auth_client.post(
        f"/api/stories/{story_id}/images",
        data={"file": (BytesIO(b"not an image"), "photo.jpg")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 400


def test_full_create_upload_update_read_cycle(auth_client, stories_dir):
    create_resp = auth_client.post(
        "/api/stories", json={"title": "Full cycle", "date": "2026-03-03", "markdown": ""}
    )
    story_id = create_resp.get_json()["id"]

    upload_resp = auth_client.post(
        f"/api/stories/{story_id}/images",
        data={"file": (_jpeg_bytes(), "photo.jpg")},
        content_type="multipart/form-data",
    )
    filename = upload_resp.get_json()["filename"]

    markdown = f"Some ==text== with a photo.\n\n![Caption]({filename})"
    update_resp = auth_client.put(
        f"/api/stories/{story_id}",
        json={"title": "Full cycle", "date": "2026-03-03", "markdown": markdown, "cover": filename},
    )
    assert update_resp.status_code == 200

    page_resp = auth_client.get(f"/story/{story_id}")
    assert page_resp.status_code == 200
    html = page_resp.data.decode()
    assert "<mark>text</mark>" in html
    assert f"/story/{story_id}/media/{filename}" in html

    raw = (stories_dir / story_id / "index.md").read_text()
    assert "==text==" in raw
    assert f"]({filename})" in raw


def test_upload_image_too_large_returns_413(auth_client, stories_dir):
    from datetime import date

    story_id = storage.create_story(stories_dir, "Big upload", date(2026, 1, 1), "")
    oversized = BytesIO(b"0" * (129 * 1024 * 1024))
    resp = auth_client.post(
        f"/api/stories/{story_id}/images",
        data={"file": (oversized, "huge.jpg")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 413
    assert "max 128 MB" in resp.get_json()["error"]
