"""Tests for FEATURES.md F14: people (the cast of the book)."""

from io import BytesIO

from PIL import Image

from app import people, storage


def _people_dir(stories_dir):
    return stories_dir / "people"


def _jpeg_bytes():
    buf = BytesIO()
    Image.new("RGB", (100, 100), color="blue").save(buf, format="JPEG")
    buf.seek(0)
    return buf


# --- app/people.py storage layer -------------------------------------------


def test_create_person_returns_slug(stories_dir):
    people_dir = _people_dir(stories_dir)
    slug = people.create_person(people_dir, "Grandma Rose", relation="your grandmother")
    assert slug == "grandma-rose"
    p = people.get_person(people_dir, slug)
    assert p.name == "Grandma Rose"
    assert p.relation == "your grandmother"


def test_create_person_slug_collision_appends_suffix(stories_dir):
    people_dir = _people_dir(stories_dir)
    first = people.create_person(people_dir, "Sam")
    second = people.create_person(people_dir, "Sam")
    assert first == "sam"
    assert second == "sam-2"


def test_update_person_keeps_slug(stories_dir):
    people_dir = _people_dir(stories_dir)
    slug = people.create_person(people_dir, "Uncle Theo", body="old bio")
    people.update_person(people_dir, slug, "Uncle Theo", relation="dad's brother", body="new bio")
    p = people.get_person(people_dir, slug)
    assert p.slug == slug
    assert p.body.strip() == "new bio"
    assert p.relation == "dad's brother"


def test_update_person_missing_raises(stories_dir):
    import pytest

    people_dir = _people_dir(stories_dir)
    with pytest.raises(FileNotFoundError):
        people.update_person(people_dir, "does-not-exist", "Name")


def test_update_person_photo_none_leaves_unchanged(stories_dir):
    people_dir = _people_dir(stories_dir)
    slug = people.create_person(people_dir, "Photo Person")
    people.update_person(people_dir, slug, "Photo Person", photo="photo-001.jpg")
    people.update_person(people_dir, slug, "Photo Person", body="updated")
    p = people.get_person(people_dir, slug)
    assert p.photo == "photo-001.jpg"


def test_update_person_photo_empty_string_clears(stories_dir):
    people_dir = _people_dir(stories_dir)
    slug = people.create_person(people_dir, "Photo Person")
    people.update_person(people_dir, slug, "Photo Person", photo="photo-001.jpg")
    people.update_person(people_dir, slug, "Photo Person", photo="")
    p = people.get_person(people_dir, slug)
    assert p.photo is None


def test_list_people_sorted_by_created_ascending(stories_dir):
    people_dir = _people_dir(stories_dir)
    people.create_person(people_dir, "First")
    people.create_person(people_dir, "Second")
    result = people.list_people(people_dir)
    assert [p.name for p in result] == ["First", "Second"]


def test_list_people_skips_folder_missing_name(stories_dir, caplog):
    people_dir = _people_dir(stories_dir)
    bad_dir = people_dir / "no-name"
    bad_dir.mkdir(parents=True)
    (bad_dir / "index.md").write_text("---\nrelation: friend\n---\nbody", encoding="utf-8")
    result = people.list_people(people_dir)
    assert result == []


def test_list_people_missing_dir_returns_empty(stories_dir):
    assert people.list_people(_people_dir(stories_dir)) == []


def test_get_person_missing_returns_none(stories_dir):
    assert people.get_person(_people_dir(stories_dir), "nobody") is None


# --- F18: family fields on the Person dataclass -----------------------------


def test_person_defaults_family_fields_empty(stories_dir):
    people_dir = _people_dir(stories_dir)
    slug = people.create_person(people_dir, "Solo")
    p = people.get_person(people_dir, slug)
    assert p.parents == []
    assert p.partners == []
    assert p.friend_of == []
    assert p.gender is None


def test_create_person_with_family_fields(stories_dir):
    people_dir = _people_dir(stories_dir)
    papi = people.create_person(people_dir, "Papi Georges", gender="m")
    mamie = people.create_person(people_dir, "Mamie Lise", gender="f")
    child = people.create_person(
        people_dir, "Papa", parents=[papi, mamie], partners=["claire"], gender="m",
    )
    p = people.get_person(people_dir, child)
    assert p.parents == [papi, mamie]
    assert p.partners == ["claire"]
    assert p.gender == "m"


def test_update_person_family_fields_none_leaves_unchanged(stories_dir):
    people_dir = _people_dir(stories_dir)
    slug = people.create_person(people_dir, "Kept", parents=["a", "b"], gender="f")
    people.update_person(people_dir, slug, "Kept", body="updated")
    p = people.get_person(people_dir, slug)
    assert p.parents == ["a", "b"]
    assert p.gender == "f"


def test_update_person_family_fields_empty_list_clears(stories_dir):
    people_dir = _people_dir(stories_dir)
    slug = people.create_person(people_dir, "Cleared", parents=["a", "b"], partners=["c"])
    people.update_person(people_dir, slug, "Cleared", parents=[], partners=[])
    p = people.get_person(people_dir, slug)
    assert p.parents == []
    assert p.partners == []


def test_update_person_gender_empty_string_clears(stories_dir):
    people_dir = _people_dir(stories_dir)
    slug = people.create_person(people_dir, "Ungendered", gender="m")
    people.update_person(people_dir, slug, "Ungendered", gender="")
    p = people.get_person(people_dir, slug)
    assert p.gender is None


def test_family_fields_tolerant_of_malformed_frontmatter(stories_dir):
    people_dir = _people_dir(stories_dir)
    person_dir = people_dir / "weird"
    person_dir.mkdir(parents=True)
    (person_dir / "index.md").write_text(
        "---\nname: Weird\nparents: not-a-list\ngender: nonbinary-typo\n---\nbody",
        encoding="utf-8",
    )
    p = people.get_person(people_dir, "weird")
    assert p.parents == []
    assert p.gender is None


def test_friend_of_round_trips(stories_dir):
    people_dir = _people_dir(stories_dir)
    slug = people.create_person(people_dir, "Buddy", friend_of=["papa"])
    p = people.get_person(people_dir, slug)
    assert p.friend_of == ["papa"]


# --- list_stories() skips people/ silently ----------------------------------


def test_list_stories_skips_people_dir_without_warning(stories_dir, caplog):
    import logging

    from datetime import date

    storage.create_story(stories_dir, "Real story", date(2026, 1, 1), "")
    people.create_person(_people_dir(stories_dir), "Grandma")

    caplog.set_level(logging.WARNING)
    result = storage.list_stories(stories_dir)

    assert [s.title for s in result] == ["Real story"]
    assert "people" not in caplog.text.lower() or "malformed" not in caplog.text.lower()
    for record in caplog.records:
        assert "people" not in record.getMessage()


# --- API: people CRUD --------------------------------------------------------


def test_create_person_via_api(auth_client, stories_dir):
    resp = auth_client.post("/api/people", json={"name": "Papi", "relation": "grandfather"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["id"] == "papi"

    p = people.get_person(_people_dir(stories_dir), "papi")
    assert p.name == "Papi"
    assert p.relation == "grandfather"


def test_create_person_via_api_accepts_title_key(auth_client, stories_dir):
    """editor.js is shared with stories and always sends `title`."""
    resp = auth_client.post("/api/people", json={"title": "Mamie", "markdown": "bio"})
    assert resp.status_code == 200
    p = people.get_person(_people_dir(stories_dir), resp.get_json()["id"])
    assert p.name == "Mamie"
    assert p.body.strip() == "bio"


def test_create_person_blank_name_returns_400(auth_client):
    resp = auth_client.post("/api/people", json={"name": "  "})
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_create_person_unauthenticated_redirects(client):
    resp = client.post("/api/people", json={"name": "Someone"})
    assert resp.status_code == 302


def test_update_person_via_api(auth_client, stories_dir):
    slug = people.create_person(_people_dir(stories_dir), "Old Name")
    resp = auth_client.put(
        f"/api/people/{slug}", json={"name": "New Name", "relation": "friend", "markdown": "hi"}
    )
    assert resp.status_code == 200
    p = people.get_person(_people_dir(stories_dir), slug)
    assert p.name == "New Name"
    assert p.relation == "friend"


def test_update_person_blank_name_returns_400(auth_client, stories_dir):
    slug = people.create_person(_people_dir(stories_dir), "Someone")
    resp = auth_client.put(f"/api/people/{slug}", json={"name": ""})
    assert resp.status_code == 400


def test_update_person_missing_returns_404(auth_client):
    resp = auth_client.put("/api/people/does-not-exist", json={"name": "X"})
    assert resp.status_code == 404


def test_update_person_unauthenticated_redirects(client, stories_dir):
    slug = people.create_person(_people_dir(stories_dir), "Someone")
    resp = client.put(f"/api/people/{slug}", json={"name": "X"})
    assert resp.status_code == 302


# --- photo_focus (crop focus point) -----------------------------------------


def test_is_valid_photo_focus_accepts_percentage_pairs():
    assert people.is_valid_photo_focus("50% 50%")
    assert people.is_valid_photo_focus("0% 100%")


def test_is_valid_photo_focus_rejects_malformed_values():
    assert not people.is_valid_photo_focus("center center")
    assert not people.is_valid_photo_focus("150% 50%")
    assert not people.is_valid_photo_focus("50%,50%")
    assert not people.is_valid_photo_focus(None)
    assert not people.is_valid_photo_focus(42)


def test_update_person_sets_photo_focus(stories_dir):
    people_dir = _people_dir(stories_dir)
    slug = people.create_person(people_dir, "Someone")
    people.update_person(people_dir, slug, "Someone", photo_focus="30% 40%")
    p = people.get_person(people_dir, slug)
    assert p.photo_focus == "30% 40%"


def test_update_person_photo_focus_none_leaves_unchanged(stories_dir):
    people_dir = _people_dir(stories_dir)
    slug = people.create_person(people_dir, "Someone")
    people.update_person(people_dir, slug, "Someone", photo_focus="30% 40%")
    people.update_person(people_dir, slug, "Someone")
    p = people.get_person(people_dir, slug)
    assert p.photo_focus == "30% 40%"


def test_update_person_photo_focus_empty_string_clears(stories_dir):
    people_dir = _people_dir(stories_dir)
    slug = people.create_person(people_dir, "Someone")
    people.update_person(people_dir, slug, "Someone", photo_focus="30% 40%")
    people.update_person(people_dir, slug, "Someone", photo_focus="")
    p = people.get_person(people_dir, slug)
    assert p.photo_focus is None


def test_malformed_photo_focus_on_disk_parses_to_none(stories_dir):
    people_dir = _people_dir(stories_dir)
    slug = people.create_person(people_dir, "Someone")
    index_path = people_dir / slug / "index.md"
    text = index_path.read_text(encoding="utf-8")
    text = text.replace("---\n", "---\nphoto_focus: not-a-position\n", 1)
    index_path.write_text(text, encoding="utf-8")
    p = people.get_person(people_dir, slug)
    assert p.photo_focus is None


def test_update_person_api_sets_photo_focus(auth_client, stories_dir):
    slug = people.create_person(_people_dir(stories_dir), "Someone")
    resp = auth_client.put(f"/api/people/{slug}", json={"name": "Someone", "photo_focus": "20% 80%"})
    assert resp.status_code == 200
    p = people.get_person(_people_dir(stories_dir), slug)
    assert p.photo_focus == "20% 80%"


def test_update_person_api_invalid_photo_focus_returns_400(auth_client, stories_dir):
    slug = people.create_person(_people_dir(stories_dir), "Someone")
    resp = auth_client.put(f"/api/people/{slug}", json={"name": "Someone", "photo_focus": "not valid"})
    assert resp.status_code == 400


def test_update_person_api_photo_focus_absent_leaves_unchanged(auth_client, stories_dir):
    people_dir = _people_dir(stories_dir)
    slug = people.create_person(people_dir, "Someone")
    people.update_person(people_dir, slug, "Someone", photo_focus="10% 10%")
    resp = auth_client.put(f"/api/people/{slug}", json={"name": "Someone"})
    assert resp.status_code == 200
    p = people.get_person(people_dir, slug)
    assert p.photo_focus == "10% 10%"


def test_api_tree_includes_photo_focus(auth_client, stories_dir):
    people_dir = _people_dir(stories_dir)
    slug = people.create_person(people_dir, "Someone")
    people.update_person(people_dir, slug, "Someone", photo_focus="15% 25%")
    resp = auth_client.get("/api/tree")
    entry = next(e for e in resp.get_json()["people"] if e["id"] == slug)
    assert entry["photo_focus"] == "15% 25%"


# --- API: person image upload -----------------------------------------------


def test_upload_person_image_returns_filename(auth_client, stories_dir):
    slug = people.create_person(_people_dir(stories_dir), "Photo Person")
    resp = auth_client.post(
        f"/api/people/{slug}/images",
        data={"file": (_jpeg_bytes(), "photo.jpg")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 200
    assert resp.get_json()["filename"] == "photo-001.jpg"


def test_first_uploaded_image_becomes_photo(auth_client, stories_dir):
    slug = people.create_person(_people_dir(stories_dir), "Photo Person")
    auth_client.post(
        f"/api/people/{slug}/images",
        data={"file": (_jpeg_bytes(), "photo.jpg")},
        content_type="multipart/form-data",
    )
    p = people.get_person(_people_dir(stories_dir), slug)
    assert p.photo == "photo-001.jpg"


def test_second_uploaded_image_does_not_replace_photo(auth_client, stories_dir):
    slug = people.create_person(_people_dir(stories_dir), "Photo Person")
    auth_client.post(
        f"/api/people/{slug}/images",
        data={"file": (_jpeg_bytes(), "photo.jpg")},
        content_type="multipart/form-data",
    )
    auth_client.post(
        f"/api/people/{slug}/images",
        data={"file": (_jpeg_bytes(), "photo2.jpg")},
        content_type="multipart/form-data",
    )
    p = people.get_person(_people_dir(stories_dir), slug)
    assert p.photo == "photo-001.jpg"


def test_upload_person_image_nonexistent_person_returns_404(auth_client):
    resp = auth_client.post(
        "/api/people/nobody/images",
        data={"file": (_jpeg_bytes(), "photo.jpg")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 404


# --- person media route ------------------------------------------------------


def test_person_media_serves_file(auth_client, stories_dir):
    slug = people.create_person(_people_dir(stories_dir), "Photo Person")
    (stories_dir / "people" / slug / "photo-001.jpg").write_bytes(b"fake-jpeg")
    resp = auth_client.get(f"/people/{slug}/media/photo-001.jpg")
    assert resp.status_code == 200
    assert resp.data == b"fake-jpeg"


def test_person_media_traversal_rejected(auth_client, stories_dir):
    slug = people.create_person(_people_dir(stories_dir), "Photo Person")
    resp = auth_client.get(f"/people/{slug}/media/..%2f..%2findex.md")
    assert resp.status_code == 404


def test_person_media_missing_file_404(auth_client, stories_dir):
    slug = people.create_person(_people_dir(stories_dir), "Photo Person")
    resp = auth_client.get(f"/people/{slug}/media/nope.jpg")
    assert resp.status_code == 404


# --- pages --------------------------------------------------------------


def test_people_page_empty_state(auth_client):
    resp = auth_client.get("/people")
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "+ New person" in html


def test_people_page_lists_cards(auth_client, stories_dir):
    people.create_person(_people_dir(stories_dir), "Grandma Rose", relation="your grandmother")
    resp = auth_client.get("/people")
    html = resp.data.decode()
    assert "Grandma Rose" in html
    assert "your grandmother" in html


def test_people_page_placeholder_initial_when_no_photo(auth_client, stories_dir):
    people.create_person(_people_dir(stories_dir), "Zelda")
    resp = auth_client.get("/people")
    html = resp.data.decode()
    assert "people__portrait--placeholder" in html
    assert ">Z<" in html


def test_person_page_renders(auth_client, stories_dir):
    slug = people.create_person(
        _people_dir(stories_dir), "Grandma Rose", relation="your grandmother",
        body="She loved [Papi](/people/papi) dearly.",
    )
    resp = auth_client.get(f"/people/{slug}")
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "Grandma Rose" in html
    assert "your grandmother" in html
    assert 'href="/people/papi"' in html


def test_person_page_image_src_resolves_to_person_media(auth_client, stories_dir):
    slug = people.create_person(
        _people_dir(stories_dir), "Grandma Rose", body="![A photo](photo-001.jpg)"
    )
    resp = auth_client.get(f"/people/{slug}")
    html = resp.data.decode()
    assert f"/people/{slug}/media/photo-001.jpg" in html


def test_person_page_missing_404(auth_client):
    resp = auth_client.get("/people/nobody")
    assert resp.status_code == 404


def test_people_page_portrait_uses_photo_focus(auth_client, stories_dir):
    people_dir = _people_dir(stories_dir)
    slug = people.create_person(people_dir, "Grandma Rose")
    people.update_person(people_dir, slug, "Grandma Rose", photo="photo-001.jpg", photo_focus="20% 70%")
    resp = auth_client.get("/people")
    assert "object-position: 20% 70%" in resp.data.decode()


def test_people_page_portrait_defaults_focus_when_unset(auth_client, stories_dir):
    people_dir = _people_dir(stories_dir)
    slug = people.create_person(people_dir, "Grandma Rose")
    people.update_person(people_dir, slug, "Grandma Rose", photo="photo-001.jpg")
    resp = auth_client.get("/people")
    assert "object-position: 50% 50%" in resp.data.decode()


def test_person_page_cover_uses_photo_focus(auth_client, stories_dir):
    people_dir = _people_dir(stories_dir)
    slug = people.create_person(people_dir, "Grandma Rose")
    people.update_person(people_dir, slug, "Grandma Rose", photo="photo-001.jpg", photo_focus="10% 90%")
    resp = auth_client.get(f"/people/{slug}")
    assert "object-position: 10% 90%" in resp.data.decode()


def test_new_person_page_renders(auth_client):
    resp = auth_client.get("/new-person")
    assert resp.status_code == 200
    html = resp.data.decode()
    assert 'placeholder="Name"' in html
    assert 'id="person-relation"' in html
    assert 'id="editor-prompt"' not in html


def test_edit_person_page_renders(auth_client, stories_dir):
    slug = people.create_person(_people_dir(stories_dir), "Grandma Rose")
    resp = auth_client.get(f"/edit-person/{slug}")
    assert resp.status_code == 200
    assert "Grandma Rose" in resp.data.decode()


def test_edit_person_page_missing_404(auth_client):
    resp = auth_client.get("/edit-person/nobody")
    assert resp.status_code == 404


def test_people_page_requires_auth(client):
    resp = client.get("/people")
    assert resp.status_code == 302


def test_person_page_requires_auth(client, stories_dir):
    slug = people.create_person(_people_dir(stories_dir), "Someone")
    resp = client.get(f"/people/{slug}")
    assert resp.status_code == 302


def test_nav_has_people_link(auth_client):
    resp = auth_client.get("/")
    assert 'href="/people"' in resp.data.decode()


# --- people do not appear in book or timeline --------------------------------


def test_people_not_in_timeline(auth_client, stories_dir):
    people.create_person(_people_dir(stories_dir), "Grandma Rose")
    resp = auth_client.get("/")
    assert "Grandma Rose" not in resp.data.decode()


def test_people_not_in_book(auth_client, stories_dir):
    people.create_person(_people_dir(stories_dir), "Grandma Rose")
    resp = auth_client.get("/book")
    assert "Grandma Rose" not in resp.data.decode()


# --- story editor keeps working unforked (F14 regression guard) -------------


def test_story_editor_page_still_has_story_endpoints(auth_client):
    resp = auth_client.get("/new")
    html = resp.data.decode()
    assert 'data-create-url="/api/stories"' in html
    assert 'data-redirect-template="/story/__ID__"' in html


def test_create_story_via_api_still_works(auth_client, stories_dir):
    resp = auth_client.post(
        "/api/stories",
        json={"title": "New memory", "date": "2026-01-05", "markdown": "Hello **world**"},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["id"] == "2026-01-05-new-memory"
    story = storage.get_story(stories_dir, data["id"])
    assert story.title == "New memory"
