"""Tests for FEATURES.md F18: the person page's Family section and the
computed kinship/friend-of small-caps line."""

from app import create_app, people


def _people_dir(stories_dir):
    return stories_dir / "people"


def _anchored_client(stories_dir, child_slug):
    app = create_app(test_config={
        "STORIES_DIR": stories_dir, "TESTING": True,
        "PASSWORD": "test-password", "SECRET_KEY": "test-secret-key",
        "CHILD_SLUG": child_slug,
    })
    client = app.test_client()
    client.post("/login", data={"password": "test-password"})
    return client


# --- Family section rendering -------------------------------------------


def test_person_page_no_family_section_when_no_links(auth_client, stories_dir):
    slug = people.create_person(_people_dir(stories_dir), "Solo")
    resp = auth_client.get(f"/people/{slug}")
    assert b"person-family" not in resp.data


def test_person_page_shows_parents(auth_client, stories_dir):
    people_dir = _people_dir(stories_dir)
    papi = people.create_person(people_dir, "Papi Georges")
    mamie = people.create_person(people_dir, "Mamie Lise")
    slug = people.create_person(people_dir, "Papa", parents=[papi, mamie])

    resp = auth_client.get(f"/people/{slug}")
    html = resp.data.decode()
    assert "Parents" in html
    assert "Papi Georges" in html
    assert "Mamie Lise" in html
    assert f'href="/people/{papi}"' in html


def test_person_page_shows_partner(auth_client, stories_dir):
    people_dir = _people_dir(stories_dir)
    papa = people.create_person(people_dir, "Papa")
    claire = people.create_person(people_dir, "Claire", partners=[papa])
    people.update_person(people_dir, papa, "Papa", partners=[claire])

    resp = auth_client.get(f"/people/{papa}")
    html = resp.data.decode()
    assert "Partner" in html
    assert "Claire" in html


def test_person_page_shows_children(auth_client, stories_dir):
    people_dir = _people_dir(stories_dir)
    papa = people.create_person(people_dir, "Papa")
    people.create_person(people_dir, "Milo", parents=[papa])

    resp = auth_client.get(f"/people/{papa}")
    html = resp.data.decode()
    assert "Children" in html
    assert "Milo" in html


def test_person_page_shows_siblings(auth_client, stories_dir):
    people_dir = _people_dir(stories_dir)
    papa = people.create_person(people_dir, "Papa")
    milo = people.create_person(people_dir, "Milo", parents=[papa])
    people.create_person(people_dir, "Emma", parents=[papa])

    resp = auth_client.get(f"/people/{milo}")
    html = resp.data.decode()
    assert "Siblings" in html
    assert "Emma" in html


def test_person_page_family_thumb_uses_portrait_when_available(auth_client, stories_dir):
    from io import BytesIO

    from PIL import Image

    people_dir = _people_dir(stories_dir)
    papi = people.create_person(people_dir, "Papi Georges")
    buf = BytesIO()
    Image.new("RGB", (10, 10)).save(buf, format="JPEG")
    buf.seek(0)
    auth_client.post(
        f"/api/people/{papi}/images",
        data={"file": (buf, "photo.jpg")},
        content_type="multipart/form-data",
    )
    slug = people.create_person(people_dir, "Papa", parents=[papi])

    resp = auth_client.get(f"/people/{slug}")
    html = resp.data.decode()
    assert f"/people/{papi}/media/photo-001.jpg" in html


# --- Kinship label: the small-caps line ----------------------------------


def test_person_page_kinship_label_shown_when_relation_absent(stories_dir):
    people_dir = _people_dir(stories_dir)
    adele = people.create_person(people_dir, "Great-Grandma Adele", gender="f")
    georges = people.create_person(people_dir, "Papi Georges", parents=[adele])
    papa = people.create_person(people_dir, "Papa", parents=[georges])
    people.create_person(people_dir, "Milo", parents=[papa])

    client = _anchored_client(stories_dir, "milo")
    resp = client.get(f"/people/{adele}")
    html = resp.data.decode()
    assert "your great-grandmother" in html


def test_person_page_relation_wins_over_kinship_label(stories_dir):
    people_dir = _people_dir(stories_dir)
    papi = people.create_person(
        people_dir, "Papi Georges", relation="the family patriarch",
    )
    papa = people.create_person(people_dir, "Papa", parents=[papi])
    people.create_person(people_dir, "Milo", parents=[papa])

    client = _anchored_client(stories_dir, "milo")
    resp = client.get(f"/people/{papi}")
    html = resp.data.decode()
    assert "the family patriarch" in html
    assert "your grandfather" not in html


def test_person_page_no_kinship_label_without_anchor(auth_client, stories_dir):
    people_dir = _people_dir(stories_dir)
    papi = people.create_person(people_dir, "Papi Georges", gender="m")
    people.create_person(people_dir, "Papa", parents=[papi])

    resp = auth_client.get(f"/people/{papi}")
    html = resp.data.decode()
    assert "your grandfather" not in html


def test_person_page_friend_of_line_when_no_relation_or_kinship(auth_client, stories_dir):
    people_dir = _people_dir(stories_dir)
    papa = people.create_person(people_dir, "Papa")
    jean = people.create_person(people_dir, "Ami Jean", friend_of=[papa])

    resp = auth_client.get(f"/people/{jean}")
    html = resp.data.decode()
    assert "Friend of" in html
    assert f'href="/people/{papa}"' in html
    assert "Papa" in html


def test_person_page_relation_wins_over_friend_of(auth_client, stories_dir):
    people_dir = _people_dir(stories_dir)
    papa = people.create_person(people_dir, "Papa")
    jean = people.create_person(
        people_dir, "Ami Jean", relation="a family friend", friend_of=[papa],
    )

    resp = auth_client.get(f"/people/{jean}")
    html = resp.data.decode()
    assert "a family friend" in html
    assert "Friend of" not in html


# --- Person editor: Family fieldset ---------------------------------------


def test_new_person_editor_no_family_fieldset_when_no_other_people(auth_client):
    resp = auth_client.get("/new-person")
    assert b"editor-family" not in resp.data


def test_new_person_editor_shows_family_fieldset_when_other_people_exist(auth_client, stories_dir):
    people.create_person(_people_dir(stories_dir), "Someone")
    resp = auth_client.get("/new-person")
    html = resp.data.decode()
    assert 'id="editor-family"' in html
    assert "Someone" in html


def test_edit_person_editor_excludes_self_from_pickers(auth_client, stories_dir):
    people_dir = _people_dir(stories_dir)
    other = people.create_person(people_dir, "Other")
    slug = people.create_person(people_dir, "Self")
    resp = auth_client.get(f"/edit-person/{slug}")
    html = resp.data.decode()
    assert f'data-person-slug="{other}"' in html
    assert f'data-person-slug="{slug}"' not in html


def test_edit_person_editor_no_fieldset_when_self_only_person(auth_client, stories_dir):
    slug = people.create_person(_people_dir(stories_dir), "Solo")
    resp = auth_client.get(f"/edit-person/{slug}")
    assert b"editor-family" not in resp.data


def test_edit_person_editor_preselects_existing_parents(auth_client, stories_dir):
    import re

    people_dir = _people_dir(stories_dir)
    papi = people.create_person(people_dir, "Papi")
    slug = people.create_person(people_dir, "Papa", parents=[papi])
    resp = auth_client.get(f"/edit-person/{slug}")
    html = resp.data.decode()
    match = re.search(r'<button[^>]*data-person-slug="%s"[^>]*>' % papi, html)
    assert match is not None
    assert 'aria-pressed="true"' in match.group()


def test_edit_person_editor_preselects_gender(auth_client, stories_dir):
    import re

    people_dir = _people_dir(stories_dir)
    slug = people.create_person(people_dir, "Papa", gender="m")
    people.create_person(people_dir, "Other")
    resp = auth_client.get(f"/edit-person/{slug}")
    html = resp.data.decode()
    match = re.search(r'<button[^>]*data-gender="m"[^>]*>', html)
    assert match is not None
    assert 'aria-pressed="true"' in match.group()


def test_editor_js_and_family_picker_script_present_on_person_editor(auth_client, stories_dir):
    people.create_person(_people_dir(stories_dir), "Someone")
    resp = auth_client.get("/new-person")
    assert b'js/editor.js' in resp.data
