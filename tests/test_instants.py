"""Tests for FEATURES.md F13: instants (photo + one line, fifteen seconds)."""

from datetime import date

from app import storage


# --- storage round-trip -------------------------------------------------------


def test_create_story_default_kind_is_story(stories_dir):
    story_id = storage.create_story(stories_dir, "Story", date(2026, 1, 1), "body")
    story = storage.get_story(stories_dir, story_id)
    assert story.kind == "story"
    raw = (stories_dir / story_id / "index.md").read_text()
    assert "kind" not in raw


def test_create_instant_round_trips(stories_dir):
    story_id = storage.create_story(
        stories_dir, "A quiet moment", date(2026, 1, 1), "A quiet moment", kind="instant"
    )
    story = storage.get_story(stories_dir, story_id)
    assert story.kind == "instant"
    raw = (stories_dir / story_id / "index.md").read_text()
    assert "kind: instant" in raw


def test_kind_survives_save_story_update(stories_dir):
    story_id = storage.create_story(
        stories_dir, "A quiet moment", date(2026, 1, 1), "body", kind="instant"
    )
    storage.save_story(stories_dir, story_id, "Changed line", date(2026, 1, 1), "new body")
    story = storage.get_story(stories_dir, story_id)
    assert story.kind == "instant"


def test_unrecognized_kind_on_disk_reads_as_story(stories_dir):
    story_id = storage.create_story(stories_dir, "Story", date(2026, 1, 1), "body")
    index_path = stories_dir / story_id / "index.md"
    text = index_path.read_text().replace("---\n", "---\nkind: something-weird\n", 1)
    index_path.write_text(text, encoding="utf-8")
    story = storage.get_story(stories_dir, story_id)
    assert story.kind == "story"


# --- API: create -----------------------------------------------------------------


def test_api_create_instant_defaults_kind_story(auth_client, stories_dir):
    resp = auth_client.post(
        "/api/stories",
        json={"title": "", "date": "2026-01-01", "markdown": "", "kind": "instant"},
    )
    assert resp.status_code == 200
    story_id = resp.get_json()["id"]
    story = storage.get_story(stories_dir, story_id)
    assert story.kind == "instant"
    assert story.title == "Instant"


def test_api_create_instant_truncates_long_line_to_60_chars(auth_client, stories_dir):
    long_line = "A" * 100
    resp = auth_client.post(
        "/api/stories",
        json={"title": long_line, "date": "2026-01-01", "markdown": long_line, "kind": "instant"},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["title"]) == 60
    story = storage.get_story(stories_dir, data["id"])
    assert len(story.title) == 60


def test_api_create_invalid_kind_returns_400(auth_client):
    resp = auth_client.post(
        "/api/stories",
        json={"title": "Story", "date": "2026-01-01", "markdown": "", "kind": "nonsense"},
    )
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_api_create_story_still_requires_title(auth_client):
    resp = auth_client.post(
        "/api/stories", json={"title": "  ", "date": "2026-01-01", "markdown": ""}
    )
    assert resp.status_code == 400


# --- API: update (PUT does not accept kind; cover validation) -----------------


def test_api_update_cannot_change_kind(auth_client, stories_dir):
    story_id = storage.create_story(
        stories_dir, "A quiet moment", date(2026, 1, 1), "body", kind="instant"
    )
    resp = auth_client.put(
        f"/api/stories/{story_id}",
        json={"title": "Changed", "date": "2026-01-01", "markdown": "body", "kind": "story"},
    )
    assert resp.status_code == 200
    story = storage.get_story(stories_dir, story_id)
    assert story.kind == "instant"


def test_api_update_cover_accepts_existing_file(auth_client, stories_dir, jpeg_bytes):
    story_id = storage.create_story(stories_dir, "Story", date(2026, 1, 1), "body")
    upload_resp = auth_client.post(
        f"/api/stories/{story_id}/images",
        data={"file": (jpeg_bytes(color="green", size=(100, 100)), "photo.jpg")},
        content_type="multipart/form-data",
    )
    filename = upload_resp.get_json()["filename"]

    resp = auth_client.put(
        f"/api/stories/{story_id}",
        json={"title": "Story", "date": "2026-01-01", "markdown": "body", "cover": filename},
    )
    assert resp.status_code == 200
    story = storage.get_story(stories_dir, story_id)
    assert story.cover == filename


def test_api_update_cover_rejects_nonexistent_file(auth_client, stories_dir):
    story_id = storage.create_story(stories_dir, "Story", date(2026, 1, 1), "body")
    resp = auth_client.put(
        f"/api/stories/{story_id}",
        json={
            "title": "Story", "date": "2026-01-01", "markdown": "body",
            "cover": "photo-999.jpg",
        },
    )
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_api_update_cover_rejects_invalid_filename(auth_client, stories_dir):
    story_id = storage.create_story(stories_dir, "Story", date(2026, 1, 1), "body")
    resp = auth_client.put(
        f"/api/stories/{story_id}",
        json={
            "title": "Story", "date": "2026-01-01", "markdown": "body",
            "cover": "../../etc/passwd",
        },
    )
    assert resp.status_code == 400


def test_api_update_cover_absent_key_keeps_existing(auth_client, stories_dir, jpeg_bytes):
    story_id = storage.create_story(stories_dir, "Story", date(2026, 1, 1), "body")
    upload_resp = auth_client.post(
        f"/api/stories/{story_id}/images",
        data={"file": (jpeg_bytes(color="green", size=(100, 100)), "photo.jpg")},
        content_type="multipart/form-data",
    )
    filename = upload_resp.get_json()["filename"]
    auth_client.put(
        f"/api/stories/{story_id}",
        json={"title": "Story", "date": "2026-01-01", "markdown": "body", "cover": filename},
    )

    resp = auth_client.put(
        f"/api/stories/{story_id}",
        json={"title": "Story renamed", "date": "2026-01-01", "markdown": "body"},
    )
    assert resp.status_code == 200
    story = storage.get_story(stories_dir, story_id)
    assert story.cover == filename


# --- Full capture flow (mirrors instant.js: create -> upload -> set cover) ----


def test_full_instant_capture_flow(auth_client, stories_dir, jpeg_bytes):
    create_resp = auth_client.post(
        "/api/stories",
        json={
            "title": "First steps!", "date": "2026-03-03", "markdown": "First steps!",
            "kind": "instant",
        },
    )
    assert create_resp.status_code == 200
    created = create_resp.get_json()

    upload_resp = auth_client.post(
        f"/api/stories/{created['id']}/images",
        data={"file": (jpeg_bytes(color="green", size=(100, 100)), "photo.jpg")},
        content_type="multipart/form-data",
    )
    filename = upload_resp.get_json()["filename"]

    update_resp = auth_client.put(
        f"/api/stories/{created['id']}",
        json={
            "title": created["title"], "date": "2026-03-03", "markdown": "First steps!",
            "cover": filename,
        },
    )
    assert update_resp.status_code == 200

    story = storage.get_story(stories_dir, created["id"])
    assert story.kind == "instant"
    assert story.cover == filename
    assert story.title == "First steps!"


# --- Pages -----------------------------------------------------------------------


def test_new_instant_page_renders(auth_client):
    resp = auth_client.get("/new-instant")
    assert resp.status_code == 200
    assert b'id="instant-form"' in resp.data
    assert b'id="instant-photo"' in resp.data


def test_new_instant_page_requires_auth(client):
    resp = client.get("/new-instant")
    assert resp.status_code == 302


def test_timeline_shows_compact_instant_entry(auth_client, stories_dir, jpeg_bytes):
    story_id = storage.create_story(
        stories_dir, "A little moment", date(2026, 1, 1), "A little moment", kind="instant"
    )
    upload_resp = auth_client.post(
        f"/api/stories/{story_id}/images",
        data={"file": (jpeg_bytes(color="green", size=(100, 100)), "photo.jpg")},
        content_type="multipart/form-data",
    )
    filename = upload_resp.get_json()["filename"]
    storage.save_story(
        stories_dir, story_id, "A little moment", date(2026, 1, 1), "A little moment",
        cover=filename,
    )

    resp = auth_client.get("/")
    html = resp.data.decode()
    assert "timeline__instant-line" in html
    assert "timeline__thumb--instant" in html
    assert "A little moment" in html


def test_instant_story_page_renders_normally(auth_client, stories_dir):
    story_id = storage.create_story(
        stories_dir, "A little moment", date(2026, 1, 1), "A little moment", kind="instant"
    )
    resp = auth_client.get(f"/story/{story_id}")
    assert resp.status_code == 200
    assert b"A little moment" in resp.data


# --- Exclusions: F2 prev/next -----------------------------------------------------


def test_prev_next_skips_instants(auth_client, stories_dir):
    storage.create_story(stories_dir, "First", date(2026, 1, 1), "")
    storage.create_story(
        stories_dir, "An instant", date(2026, 1, 2), "line", kind="instant"
    )
    last_id = storage.create_story(stories_dir, "Last", date(2026, 1, 3), "")

    resp = auth_client.get(f"/story/{last_id}")
    html = resp.data.decode()
    assert "First" in html
    assert "An instant" not in html


def test_instant_own_page_has_no_prev_next(auth_client, stories_dir):
    storage.create_story(stories_dir, "First", date(2026, 1, 1), "")
    instant_id = storage.create_story(
        stories_dir, "An instant", date(2026, 1, 2), "line", kind="instant"
    )
    storage.create_story(stories_dir, "Last", date(2026, 1, 3), "")

    resp = auth_client.get(f"/story/{instant_id}")
    html = resp.data.decode()
    assert "story__prev" not in html
    assert "story__next" not in html


# --- Inclusion: F10 book (compact) --------------------------------------------------


def test_book_includes_instant_compactly(auth_client, stories_dir, jpeg_bytes):
    story_id = storage.create_story(
        stories_dir, "A little moment", date(2026, 1, 1), "A little moment", kind="instant"
    )
    upload_resp = auth_client.post(
        f"/api/stories/{story_id}/images",
        data={"file": (jpeg_bytes(color="green", size=(100, 100)), "photo.jpg")},
        content_type="multipart/form-data",
    )
    filename = upload_resp.get_json()["filename"]
    storage.save_story(
        stories_dir, story_id, "A little moment", date(2026, 1, 1), "A little moment",
        cover=filename,
    )
    storage.create_story(stories_dir, "A real story", date(2026, 1, 2), "Full body text.")

    resp = auth_client.get("/book")
    html = resp.data.decode()
    assert "book__instant" in html
    assert "A little moment" in html
    assert "book__story" in html  # the real story still renders as a full chapter
