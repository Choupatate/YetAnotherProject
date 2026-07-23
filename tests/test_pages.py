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


def test_timeline_shows_cover_thumbnail_only_when_present(auth_client, stories_dir, jpeg_bytes):
    from datetime import date

    from werkzeug.datastructures import FileStorage

    from app import storage

    story_id = storage.create_story(stories_dir, "With cover", date(2024, 1, 1), "body")
    buf = jpeg_bytes(color="red", size=(200, 200))
    filename = storage.save_image(stories_dir, story_id, FileStorage(stream=buf, filename="c.jpg"))
    story = storage.get_story(stories_dir, story_id)
    storage.save_story(stories_dir, story_id, story.title, story.date, story.body, cover=filename)

    storage.create_story(stories_dir, "Without cover", date(2024, 2, 1), "body")

    resp = auth_client.get("/")
    html = resp.data.decode()
    assert html.count("timeline__thumb") == 1
    assert f"/story/{story_id}/media/photo-001.thumb.jpg" in html


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


def test_story_page_renders_tags_people_and_sources(auth_client, stories_dir):
    from datetime import date

    from app import people, storage

    people_dir = stories_dir / "people"
    grandma = people.create_person(people_dir, "Grandma")
    story_id = storage.create_story(
        stories_dir, "Beach day", date(2026, 1, 1), "body",
        people=[grandma], tags=["beach", "summer"],
        sources=[{"url": "https://example.com/photo", "note": "from aunt Jane"}],
    )

    resp = auth_client.get(f"/story/{story_id}")
    html = resp.data.decode()
    assert "beach" in html
    assert "summer" in html
    assert f'href="/people/{grandma}"' in html
    assert "Grandma" in html
    assert "from aunt Jane" in html
    assert 'href="https://example.com/photo"' in html


def test_story_page_renders_milestone(auth_client, stories_dir):
    from datetime import date

    from app import storage

    story_id = storage.create_story(
        stories_dir, "First steps", date(2026, 1, 1), "body", milestone="First steps"
    )
    resp = auth_client.get(f"/story/{story_id}")
    html = resp.data.decode()
    assert "story__milestone-pill" in html
    assert "First steps" in html


def test_timeline_shows_milestone_pill(auth_client, stories_dir):
    from datetime import date

    from app import storage

    storage.create_story(
        stories_dir, "First steps", date(2026, 1, 1), "body", milestone="First steps"
    )
    resp = auth_client.get("/")
    html = resp.data.decode()
    assert "timeline__milestone-pill" in html
    assert "First steps" in html


def test_firsts_page_lists_milestones_chronologically(auth_client, stories_dir):
    from datetime import date

    from app import storage

    storage.create_story(stories_dir, "Second one", date(2026, 6, 1), "", milestone="Second thing")
    storage.create_story(stories_dir, "First one", date(2026, 1, 1), "", milestone="First thing")
    storage.create_story(stories_dir, "No milestone", date(2026, 3, 1), "")

    resp = auth_client.get("/firsts")
    html = resp.data.decode()
    assert html.index("First thing") < html.index("Second thing")
    assert "First one" in html
    assert "Second one" in html
    assert "No milestone" not in html


def test_firsts_page_empty_state(auth_client):
    resp = auth_client.get("/firsts")
    html = resp.data.decode()
    assert "milestone label" in html


def test_firsts_page_excludes_drafts_and_sealed(auth_client, stories_dir):
    from datetime import date, timedelta

    from app import storage

    storage.create_story(
        stories_dir, "Draft first", date(2026, 1, 1), "", milestone="Draft", draft=True
    )
    storage.create_story(
        stories_dir, "Sealed first", date(2026, 1, 1), "", milestone="Sealed",
        unlock=date.today() + timedelta(days=365),
    )
    resp = auth_client.get("/firsts")
    html = resp.data.decode()
    assert "Draft" not in html
    assert "Sealed" not in html


def test_firsts_requires_auth(client):
    resp = client.get("/firsts")
    assert resp.status_code == 302


def test_timeline_shows_firsts_link_only_when_milestones_exist(auth_client, stories_dir):
    from datetime import date

    from app import storage

    storage.create_story(stories_dir, "Plain", date(2026, 1, 1), "")
    resp = auth_client.get("/")
    assert b'>Firsts<' not in resp.data

    storage.create_story(
        stories_dir, "First steps", date(2026, 1, 2), "", milestone="First steps"
    )
    resp = auth_client.get("/")
    assert b'>Firsts<' in resp.data


def _backdate_created(stories_dir, story_id, created_dt):
    import frontmatter

    index_path = stories_dir / story_id / "index.md"
    post = frontmatter.load(index_path)
    post["created"] = created_dt.isoformat()
    index_path.write_text(frontmatter.dumps(post) + "\n", encoding="utf-8")


def test_timeline_no_nudge_for_recent_activity(auth_client, stories_dir):
    from datetime import date

    from app import storage

    storage.create_story(stories_dir, "Just written", date(2026, 1, 1), "")
    resp = auth_client.get("/")
    assert b"timeline__nudge" not in resp.data


def test_timeline_shows_nudge_after_a_quiet_spell(auth_client, stories_dir):
    from datetime import date, datetime

    from app import storage

    story_id = storage.create_story(stories_dir, "Old one", date(2025, 1, 1), "")
    _backdate_created(stories_dir, story_id, datetime(2025, 1, 1))

    resp = auth_client.get("/")
    html = resp.data.decode()
    assert "timeline__nudge" in html
    assert "Nothing new in" in html
    assert "a little story?" in html


def test_404_page_renders_custom_template(auth_client):
    resp = auth_client.get("/this-route-does-not-exist")
    assert resp.status_code == 404
    assert b"doesn't exist" in resp.data


def test_story_media_serves_image_and_rejects_bad_path(auth_client, stories_dir, jpeg_bytes):
    from datetime import date

    from werkzeug.datastructures import FileStorage

    from app import storage

    story_id = storage.create_story(stories_dir, "Media test", date(2024, 1, 1), "body")
    buf = jpeg_bytes(color="blue", size=(50, 50))
    filename = storage.save_image(stories_dir, story_id, FileStorage(stream=buf, filename="m.jpg"))

    resp = auth_client.get(f"/story/{story_id}/media/{filename}")
    assert resp.status_code == 200

    resp = auth_client.get(f"/story/{story_id}/media/../../etc/passwd")
    assert resp.status_code == 404

    resp = auth_client.get(f"/story/{story_id}/media/does-not-exist.jpg")
    assert resp.status_code == 404


def test_story_media_thumb_falls_back_to_full_size_when_missing(auth_client, stories_dir):
    """A photo saved before thumbnails existed has no `.thumb.` sibling on
    disk — requesting it serves the full-size original instead of 404ing."""
    from datetime import date

    from app import storage

    story_id = storage.create_story(stories_dir, "Legacy photo", date(2024, 1, 1), "body")
    (stories_dir / story_id / "photo-001.jpg").write_bytes(b"fake-jpeg-bytes")

    resp = auth_client.get(f"/story/{story_id}/media/{storage.thumb_filename('photo-001.jpg')}")
    assert resp.status_code == 200
    assert resp.data == b"fake-jpeg-bytes"
