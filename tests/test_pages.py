def test_index_redirects_to_login_when_unauthenticated(client):
    resp = client.get("/")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_correct_password_logs_in_and_redirects_to_timeline(client):
    resp = client.post("/login", data={"password": "test-password"})
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/")

    resp = client.get("/")
    assert resp.status_code == 200


def test_wrong_password_shows_error_and_stays_logged_out(client):
    resp = client.post("/login", data={"password": "nope"}, follow_redirects=True)
    assert resp.status_code == 200
    assert b"Incorrect password" in resp.data

    resp = client.get("/")
    assert resp.status_code == 302


def test_login_redirect_preserves_next_param(client):
    resp = client.get("/story/2026-01-01-something")
    assert resp.status_code == 302
    assert "next=" in resp.headers["Location"]


def test_login_rejects_external_redirect(client):
    resp = client.post(
        "/login?next=https://evil.example.com", data={"password": "test-password"}
    )
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/"


def test_login_rejects_protocol_relative_redirect(client):
    resp = client.post("/login?next=//evil.example.com", data={"password": "test-password"})
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/"


def test_login_allows_legitimate_local_next(client):
    resp = client.post(
        "/login?next=/edit/2026-01-01-some-id", data={"password": "test-password"}
    )
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/edit/2026-01-01-some-id"


def test_logout_clears_session(auth_client):
    resp = auth_client.get("/")
    assert resp.status_code == 200

    auth_client.post("/logout")
    resp = auth_client.get("/")
    assert resp.status_code == 302


def test_timeline_empty_state(auth_client):
    resp = auth_client.get("/")
    assert resp.status_code == 200
    assert b"No stories yet" in resp.data


def test_timeline_shows_year_markers_and_entries(auth_client, stories_dir):
    from datetime import date

    from app import storage

    storage.create_story(stories_dir, "Story A", date(2024, 1, 1), "body a")
    storage.create_story(stories_dir, "Story B", date(2025, 6, 1), "body b")

    resp = auth_client.get("/")
    assert resp.status_code == 200
    html = resp.data.decode()
    assert ">2024<" in html
    assert ">2025<" in html
    assert "Story A" in html
    assert "Story B" in html
    assert "No stories yet" not in html


def test_timeline_shows_cover_thumbnail_only_when_present(auth_client, stories_dir):
    from datetime import date
    from io import BytesIO

    from PIL import Image
    from werkzeug.datastructures import FileStorage

    from app import storage

    story_id = storage.create_story(stories_dir, "With cover", date(2024, 1, 1), "body")
    buf = BytesIO()
    Image.new("RGB", (200, 200), color="red").save(buf, format="JPEG")
    buf.seek(0)
    filename = storage.save_image(stories_dir, story_id, FileStorage(stream=buf, filename="c.jpg"))
    story = storage.get_story(stories_dir, story_id)
    storage.save_story(stories_dir, story_id, story.title, story.date, story.body, cover=filename)

    storage.create_story(stories_dir, "Without cover", date(2024, 2, 1), "body")

    resp = auth_client.get("/")
    html = resp.data.decode()
    assert html.count("timeline__thumb") == 1


def test_story_page_renders_markdown_with_highlight_and_image(auth_client, stories_dir):
    from datetime import date

    from app import storage

    story_id = storage.create_story(
        stories_dir,
        "A test story",
        date(2024, 3, 5),
        "This has ==a highlight== and an image.\n\n![A caption](photo-001.jpg)",
    )

    resp = auth_client.get(f"/story/{story_id}")
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "<mark>a highlight</mark>" in html
    assert f"/story/{story_id}/media/photo-001.jpg" in html
    assert "<figcaption>A caption</figcaption>" in html


def test_story_page_404_for_missing_story(auth_client):
    resp = auth_client.get("/story/2026-01-01-nope")
    assert resp.status_code == 404


def test_404_page_renders_custom_template(auth_client):
    resp = auth_client.get("/this-route-does-not-exist")
    assert resp.status_code == 404
    assert b"doesn't exist" in resp.data


def test_story_media_serves_image_and_rejects_bad_path(auth_client, stories_dir):
    from datetime import date
    from io import BytesIO

    from PIL import Image
    from werkzeug.datastructures import FileStorage

    from app import storage

    story_id = storage.create_story(stories_dir, "Media test", date(2024, 1, 1), "body")
    buf = BytesIO()
    Image.new("RGB", (50, 50), color="blue").save(buf, format="JPEG")
    buf.seek(0)
    filename = storage.save_image(stories_dir, story_id, FileStorage(stream=buf, filename="m.jpg"))

    resp = auth_client.get(f"/story/{story_id}/media/{filename}")
    assert resp.status_code == 200

    resp = auth_client.get(f"/story/{story_id}/media/../../etc/passwd")
    assert resp.status_code == 404

    resp = auth_client.get(f"/story/{story_id}/media/does-not-exist.jpg")
    assert resp.status_code == 404
