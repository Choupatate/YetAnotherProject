"""Tests for FEATURES.md F12: voice memos on stories."""

from datetime import date
from io import BytesIO

from app import storage


# --- storage.list_memos ---------------------------------------------------


def test_list_memos_empty_dir_returns_empty(stories_dir):
    story_id = storage.create_story(stories_dir, "Story", date(2026, 1, 1), "")
    assert storage.list_memos(stories_dir / story_id) == []


def test_list_memos_sorted_by_filename(stories_dir):
    story_id = storage.create_story(stories_dir, "Story", date(2026, 1, 1), "")
    story_dir = stories_dir / story_id
    (story_dir / "memo-002.m4a").write_bytes(b"b")
    (story_dir / "memo-001.webm").write_bytes(b"a")
    (story_dir / "memo-010.mp3").write_bytes(b"c")
    memos = storage.list_memos(story_dir)
    assert [m.filename for m in memos] == ["memo-001.webm", "memo-002.m4a", "memo-010.mp3"]


def test_list_memos_ignores_non_matching_files(stories_dir):
    story_id = storage.create_story(stories_dir, "Story", date(2026, 1, 1), "")
    story_dir = stories_dir / story_id
    (story_dir / "memo-001.webm").write_bytes(b"a")
    (story_dir / "memo-01.webm").write_bytes(b"b")  # only 2 digits
    (story_dir / "memo-001.wav").write_bytes(b"c")  # disallowed extension
    (story_dir / "notes.txt").write_text("not a sidecar")
    (story_dir / "photo-001.jpg").write_bytes(b"d")
    memos = storage.list_memos(story_dir)
    assert [m.filename for m in memos] == ["memo-001.webm"]


def test_list_memos_reads_transcript_sidecar(stories_dir):
    story_id = storage.create_story(stories_dir, "Story", date(2026, 1, 1), "")
    story_dir = stories_dir / story_id
    (story_dir / "memo-001.webm").write_bytes(b"a")
    (story_dir / "memo-001.txt").write_text("Hello there.\n", encoding="utf-8")
    memos = storage.list_memos(story_dir)
    assert memos[0].transcript == "Hello there."


def test_list_memos_no_sidecar_means_none_transcript(stories_dir):
    story_id = storage.create_story(stories_dir, "Story", date(2026, 1, 1), "")
    story_dir = stories_dir / story_id
    (story_dir / "memo-001.webm").write_bytes(b"a")
    memos = storage.list_memos(story_dir)
    assert memos[0].transcript is None


def test_list_memos_missing_dir_returns_empty(stories_dir):
    assert storage.list_memos(stories_dir / "nonexistent") == []


# --- storage.save_memo / delete_memo --------------------------------------


class _FakeFileStorage:
    def __init__(self, filename, content=b"fake-audio-bytes"):
        self.filename = filename
        self._content = content

    def save(self, dest):
        dest.write_bytes(self._content)


def test_save_memo_first_is_numbered_001(stories_dir):
    story_id = storage.create_story(stories_dir, "Story", date(2026, 1, 1), "")
    filename = storage.save_memo(stories_dir, story_id, _FakeFileStorage("memo.webm"))
    assert filename == "memo-001.webm"
    assert (stories_dir / story_id / "memo-001.webm").is_file()


def test_save_memo_numbers_after_existing(stories_dir):
    story_id = storage.create_story(stories_dir, "Story", date(2026, 1, 1), "")
    (stories_dir / story_id / "memo-001.webm").write_bytes(b"x")
    filename = storage.save_memo(stories_dir, story_id, _FakeFileStorage("memo.m4a"))
    assert filename == "memo-002.m4a"


def test_save_memo_invalid_extension_raises(stories_dir):
    story_id = storage.create_story(stories_dir, "Story", date(2026, 1, 1), "")
    import pytest

    with pytest.raises(ValueError):
        storage.save_memo(stories_dir, story_id, _FakeFileStorage("memo.wav"))


def test_delete_memo_removes_audio_and_sidecar(stories_dir):
    story_id = storage.create_story(stories_dir, "Story", date(2026, 1, 1), "")
    story_dir = stories_dir / story_id
    (story_dir / "memo-001.webm").write_bytes(b"a")
    (story_dir / "memo-001.txt").write_text("transcript")
    assert storage.delete_memo(stories_dir, story_id, "memo-001.webm") is True
    assert not (story_dir / "memo-001.webm").exists()
    assert not (story_dir / "memo-001.txt").exists()


def test_delete_memo_without_sidecar(stories_dir):
    story_id = storage.create_story(stories_dir, "Story", date(2026, 1, 1), "")
    story_dir = stories_dir / story_id
    (story_dir / "memo-001.webm").write_bytes(b"a")
    assert storage.delete_memo(stories_dir, story_id, "memo-001.webm") is True


def test_delete_memo_nonexistent_returns_false(stories_dir):
    story_id = storage.create_story(stories_dir, "Story", date(2026, 1, 1), "")
    assert storage.delete_memo(stories_dir, story_id, "memo-001.webm") is False


def test_delete_memo_traversal_shaped_filename_returns_false(stories_dir):
    story_id = storage.create_story(stories_dir, "Story", date(2026, 1, 1), "")
    assert storage.delete_memo(stories_dir, story_id, "../../etc/passwd") is False


# --- API: POST /api/stories/<id>/memos ------------------------------------


def test_upload_memo_returns_filename_201(auth_client, stories_dir):
    story_id = storage.create_story(stories_dir, "Voice story", date(2026, 1, 1), "")
    resp = auth_client.post(
        f"/api/stories/{story_id}/memos",
        data={"file": (BytesIO(b"fake-webm-bytes"), "memo.webm")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["filename"] == "memo-001.webm"
    assert (stories_dir / story_id / "memo-001.webm").is_file()


def test_upload_memo_numbering_after_existing(auth_client, stories_dir):
    story_id = storage.create_story(stories_dir, "Voice story", date(2026, 1, 1), "")
    (stories_dir / story_id / "memo-001.webm").write_bytes(b"x")
    resp = auth_client.post(
        f"/api/stories/{story_id}/memos",
        data={"file": (BytesIO(b"fake-m4a-bytes"), "memo.m4a")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 201
    assert resp.get_json()["filename"] == "memo-002.m4a"


def test_upload_memo_bad_extension_returns_400(auth_client, stories_dir):
    story_id = storage.create_story(stories_dir, "Voice story", date(2026, 1, 1), "")
    resp = auth_client.post(
        f"/api/stories/{story_id}/memos",
        data={"file": (BytesIO(b"data"), "memo.wav")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_upload_memo_no_file_returns_400(auth_client, stories_dir):
    story_id = storage.create_story(stories_dir, "Voice story", date(2026, 1, 1), "")
    resp = auth_client.post(
        f"/api/stories/{story_id}/memos", data={}, content_type="multipart/form-data"
    )
    assert resp.status_code == 400


def test_upload_memo_invalid_story_id_returns_404(auth_client):
    resp = auth_client.post(
        "/api/stories/../../etc/memos",
        data={"file": (BytesIO(b"data"), "memo.webm")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 404


def test_upload_memo_nonexistent_story_returns_404(auth_client):
    resp = auth_client.post(
        "/api/stories/2026-01-01-nope/memos",
        data={"file": (BytesIO(b"data"), "memo.webm")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 404


def test_upload_memo_unauthenticated_redirects(client, stories_dir):
    story_id = storage.create_story(stories_dir, "Voice story", date(2026, 1, 1), "")
    resp = client.post(
        f"/api/stories/{story_id}/memos",
        data={"file": (BytesIO(b"data"), "memo.webm")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 302


# --- API: DELETE /api/stories/<id>/memos/<filename> -----------------------


def test_delete_memo_returns_204(auth_client, stories_dir):
    story_id = storage.create_story(stories_dir, "Voice story", date(2026, 1, 1), "")
    (stories_dir / story_id / "memo-001.webm").write_bytes(b"a")
    resp = auth_client.delete(f"/api/stories/{story_id}/memos/memo-001.webm")
    assert resp.status_code == 204
    assert not (stories_dir / story_id / "memo-001.webm").exists()


def test_delete_memo_removes_sidecar(auth_client, stories_dir):
    story_id = storage.create_story(stories_dir, "Voice story", date(2026, 1, 1), "")
    story_dir = stories_dir / story_id
    (story_dir / "memo-001.webm").write_bytes(b"a")
    (story_dir / "memo-001.txt").write_text("transcript")
    resp = auth_client.delete(f"/api/stories/{story_id}/memos/memo-001.webm")
    assert resp.status_code == 204
    assert not (story_dir / "memo-001.txt").exists()


def test_delete_memo_unknown_filename_returns_404(auth_client, stories_dir):
    story_id = storage.create_story(stories_dir, "Voice story", date(2026, 1, 1), "")
    resp = auth_client.delete(f"/api/stories/{story_id}/memos/memo-001.webm")
    assert resp.status_code == 404


def test_delete_memo_traversal_shaped_filename_returns_404(auth_client, stories_dir):
    story_id = storage.create_story(stories_dir, "Voice story", date(2026, 1, 1), "")
    resp = auth_client.delete(f"/api/stories/{story_id}/memos/..%2f..%2fetc")
    assert resp.status_code == 404


def test_delete_memo_unauthenticated_redirects(client, stories_dir):
    story_id = storage.create_story(stories_dir, "Voice story", date(2026, 1, 1), "")
    (stories_dir / story_id / "memo-001.webm").write_bytes(b"a")
    resp = client.delete(f"/api/stories/{story_id}/memos/memo-001.webm")
    assert resp.status_code == 302


# --- Playback: Range requests for seeking ---------------------------------


def test_story_media_range_request_returns_206(auth_client, stories_dir):
    story_id = storage.create_story(stories_dir, "Voice story", date(2026, 1, 1), "")
    (stories_dir / story_id / "memo-001.webm").write_bytes(b"0123456789")
    resp = auth_client.get(
        f"/story/{story_id}/media/memo-001.webm", headers={"Range": "bytes=0-3"}
    )
    assert resp.status_code == 206
    assert resp.data == b"0123"


# --- Story page: Listen section --------------------------------------------


def test_story_page_shows_listen_section_with_memo(auth_client, stories_dir):
    story_id = storage.create_story(stories_dir, "Voice story", date(2026, 1, 1), "body")
    (stories_dir / story_id / "memo-001.webm").write_bytes(b"a")
    resp = auth_client.get(f"/story/{story_id}")
    html = resp.data.decode()
    assert "Listen" in html
    assert f"/story/{story_id}/media/memo-001.webm" in html


def test_story_page_no_listen_section_without_memos(auth_client, stories_dir):
    story_id = storage.create_story(stories_dir, "Quiet story", date(2026, 1, 1), "body")
    resp = auth_client.get(f"/story/{story_id}")
    html = resp.data.decode()
    assert 'class="story__listen"' not in html


def test_story_page_shows_transcript_when_sidecar_present(auth_client, stories_dir):
    story_id = storage.create_story(stories_dir, "Voice story", date(2026, 1, 1), "body")
    story_dir = stories_dir / story_id
    (story_dir / "memo-001.webm").write_bytes(b"a")
    (story_dir / "memo-001.txt").write_text("What grandma said.", encoding="utf-8")
    resp = auth_client.get(f"/story/{story_id}")
    html = resp.data.decode()
    assert "Transcript" in html
    assert "What grandma said." in html


def test_story_page_no_transcript_block_without_sidecar(auth_client, stories_dir):
    story_id = storage.create_story(stories_dir, "Voice story", date(2026, 1, 1), "body")
    (stories_dir / story_id / "memo-001.webm").write_bytes(b"a")
    resp = auth_client.get(f"/story/{story_id}")
    html = resp.data.decode()
    assert "Transcript" not in html


def test_sealed_story_page_never_shows_memos(auth_client, stories_dir):
    from datetime import date as date_cls

    story_id = storage.create_story(
        stories_dir, "Sealed story", date(2026, 1, 1), "secret",
        unlock=date_cls(2099, 1, 1),
    )
    (stories_dir / story_id / "memo-001.webm").write_bytes(b"a")
    resp = auth_client.get(f"/story/{story_id}")
    html = resp.data.decode()
    assert "Listen" not in html
    assert "memo-001.webm" not in html


# --- Editor page: Voice section ---------------------------------------------


def test_new_story_page_has_voice_section_but_no_memos(auth_client):
    resp = auth_client.get("/new")
    html = resp.data.decode()
    assert 'id="editor-voice"' in html
    assert 'id="voice-record-btn"' in html
    assert 'id="voice-list"' in html


def test_edit_story_page_lists_existing_memos(auth_client, stories_dir):
    story_id = storage.create_story(stories_dir, "Voice story", date(2026, 1, 1), "body")
    (stories_dir / story_id / "memo-001.webm").write_bytes(b"a")
    resp = auth_client.get(f"/edit/{story_id}")
    html = resp.data.decode()
    assert 'data-filename="memo-001.webm"' in html
    assert f"/story/{story_id}/media/memo-001.webm" in html
