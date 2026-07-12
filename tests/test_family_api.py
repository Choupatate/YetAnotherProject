"""Tests for FEATURES.md F18: the people API's parents/partners/friend_of/
gender fields, partner symmetry, cycle rejection, and GET /api/tree."""

from app import people


def _people_dir(stories_dir):
    return stories_dir / "people"


# --- Validation on create/update ---------------------------------------------


def test_create_person_with_gender(auth_client, stories_dir):
    resp = auth_client.post("/api/people", json={"name": "Papi", "gender": "m"})
    assert resp.status_code == 200
    p = people.get_person(_people_dir(stories_dir), "papi")
    assert p.gender == "m"


def test_create_person_invalid_gender_returns_400(auth_client):
    resp = auth_client.post("/api/people", json={"name": "Papi", "gender": "x"})
    assert resp.status_code == 400


def test_create_person_with_parents(auth_client, stories_dir):
    people_dir = _people_dir(stories_dir)
    papi = people.create_person(people_dir, "Papi")
    mamie = people.create_person(people_dir, "Mamie")
    resp = auth_client.post(
        "/api/people", json={"name": "Papa", "parents": [papi, mamie]}
    )
    assert resp.status_code == 200
    p = people.get_person(people_dir, resp.get_json()["id"])
    assert p.parents == [papi, mamie]


def test_create_person_unknown_parent_slug_returns_400(auth_client):
    resp = auth_client.post("/api/people", json={"name": "Papa", "parents": ["ghost"]})
    assert resp.status_code == 400


def test_create_person_more_than_two_parents_returns_400(auth_client, stories_dir):
    people_dir = _people_dir(stories_dir)
    a = people.create_person(people_dir, "A")
    b = people.create_person(people_dir, "B")
    c = people.create_person(people_dir, "C")
    resp = auth_client.post("/api/people", json={"name": "Kid", "parents": [a, b, c]})
    assert resp.status_code == 400


def test_update_person_self_as_parent_returns_400(auth_client, stories_dir):
    slug = people.create_person(_people_dir(stories_dir), "Loop")
    resp = auth_client.put(f"/api/people/{slug}", json={"name": "Loop", "parents": [slug]})
    assert resp.status_code == 400


def test_update_person_self_as_partner_returns_400(auth_client, stories_dir):
    slug = people.create_person(_people_dir(stories_dir), "Loop")
    resp = auth_client.put(f"/api/people/{slug}", json={"name": "Loop", "partners": [slug]})
    assert resp.status_code == 400


def test_update_person_self_as_friend_of_returns_400(auth_client, stories_dir):
    slug = people.create_person(_people_dir(stories_dir), "Loop")
    resp = auth_client.put(f"/api/people/{slug}", json={"name": "Loop", "friend_of": [slug]})
    assert resp.status_code == 400


def test_update_person_parent_cycle_returns_400(auth_client, stories_dir):
    people_dir = _people_dir(stories_dir)
    grandparent = people.create_person(people_dir, "Grandparent")
    parent = people.create_person(people_dir, "Parent", parents=[grandparent])
    child = people.create_person(people_dir, "Child", parents=[parent])
    # Trying to make the grandchild a parent of the grandparent is a cycle.
    resp = auth_client.put(
        f"/api/people/{grandparent}", json={"name": "Grandparent", "parents": [child]}
    )
    assert resp.status_code == 400


def test_update_person_unknown_partner_slug_returns_400(auth_client, stories_dir):
    slug = people.create_person(_people_dir(stories_dir), "Someone")
    resp = auth_client.put(
        f"/api/people/{slug}", json={"name": "Someone", "partners": ["ghost"]}
    )
    assert resp.status_code == 400


def test_update_person_gender_empty_string_clears(auth_client, stories_dir):
    people_dir = _people_dir(stories_dir)
    slug = people.create_person(people_dir, "Someone", gender="m")
    resp = auth_client.put(f"/api/people/{slug}", json={"name": "Someone", "gender": ""})
    assert resp.status_code == 200
    assert people.get_person(people_dir, slug).gender is None


def test_update_person_omitted_family_fields_leave_unchanged(auth_client, stories_dir):
    people_dir = _people_dir(stories_dir)
    other = people.create_person(people_dir, "Other")
    slug = people.create_person(people_dir, "Someone", parents=[other], gender="f")
    resp = auth_client.put(f"/api/people/{slug}", json={"name": "Someone Else"})
    assert resp.status_code == 200
    p = people.get_person(people_dir, slug)
    assert p.parents == [other]
    assert p.gender == "f"


def test_update_person_preserves_relation_and_body(auth_client, stories_dir):
    """A family-field-only update must not blow away relation/body (these
    aren't 'None means unchanged' fields on the writer)."""
    people_dir = _people_dir(stories_dir)
    other = people.create_person(people_dir, "Other")
    slug = people.create_person(
        people_dir, "Someone", relation="your friend", body="a whole bio"
    )
    resp = auth_client.put(
        f"/api/people/{slug}",
        json={"name": "Someone", "relation": "your friend", "markdown": "a whole bio",
              "partners": [other]},
    )
    assert resp.status_code == 200
    p = people.get_person(people_dir, slug)
    assert p.relation == "your friend"
    assert p.body.strip() == "a whole bio"


# --- Partner symmetry ---------------------------------------------------------


def test_create_person_with_partner_writes_reverse_link(auth_client, stories_dir):
    people_dir = _people_dir(stories_dir)
    claire = people.create_person(people_dir, "Claire")
    resp = auth_client.post("/api/people", json={"name": "Papa", "partners": [claire]})
    assert resp.status_code == 200
    papa_slug = resp.get_json()["id"]
    claire_after = people.get_person(people_dir, claire)
    assert claire_after.partners == [papa_slug]


def test_update_person_adding_partner_writes_reverse_link(auth_client, stories_dir):
    people_dir = _people_dir(stories_dir)
    papa = people.create_person(people_dir, "Papa")
    claire = people.create_person(people_dir, "Claire")
    resp = auth_client.put(f"/api/people/{papa}", json={"name": "Papa", "partners": [claire]})
    assert resp.status_code == 200
    assert people.get_person(people_dir, claire).partners == [papa]


def test_update_person_removing_partner_removes_reverse_link(auth_client, stories_dir):
    people_dir = _people_dir(stories_dir)
    papa = people.create_person(people_dir, "Papa")
    claire = people.create_person(people_dir, "Claire", partners=[papa])
    people.update_person(people_dir, papa, "Papa", partners=[claire])

    resp = auth_client.put(f"/api/people/{papa}", json={"name": "Papa", "partners": []})
    assert resp.status_code == 200
    assert people.get_person(people_dir, claire).partners == []


def test_partner_symmetry_preserves_other_persons_relation_and_body(auth_client, stories_dir):
    people_dir = _people_dir(stories_dir)
    claire = people.create_person(
        people_dir, "Claire", relation="your mother", body="claire's whole bio"
    )
    resp = auth_client.post("/api/people", json={"name": "Papa", "partners": [claire]})
    assert resp.status_code == 200
    claire_after = people.get_person(people_dir, claire)
    assert claire_after.relation == "your mother"
    assert claire_after.body.strip() == "claire's whole bio"


def test_hand_edited_single_sided_partner_link_reads_as_symmetric(stories_dir, auth_client):
    """FEATURES.md F18: 'reads take the union of both directions so a
    hand-edited single side still works.'"""
    people_dir = _people_dir(stories_dir)
    a = people.create_person(people_dir, "A")
    people.create_person(people_dir, "B", partners=[a])
    resp = auth_client.get("/api/tree")
    people_by_id = {p["id"]: p for p in resp.get_json()["people"]}
    assert "b" in people_by_id["a"]["rels"]["partners"]


# --- GET /api/tree ------------------------------------------------------------


def test_api_tree_requires_auth(client):
    resp = client.get("/api/tree")
    assert resp.status_code == 302


def test_api_tree_anchor_null_when_unset(auth_client):
    resp = auth_client.get("/api/tree")
    assert resp.status_code == 200
    assert resp.get_json()["anchor"] is None


def test_api_tree_anchor_set_when_child_slug_configured(stories_dir):
    from app import create_app

    people.create_person(_people_dir(stories_dir), "Milo")
    app = create_app(test_config={
        "STORIES_DIR": stories_dir, "TESTING": True,
        "PASSWORD": "test-password", "SECRET_KEY": "test-secret-key",
        "CHILD_SLUG": "milo",
    })
    client = app.test_client()
    client.post("/login", data={"password": "test-password"})
    resp = client.get("/api/tree")
    assert resp.get_json()["anchor"] == "milo"


def test_api_tree_unset_child_slug_not_found_gives_null_anchor(stories_dir):
    from app import create_app

    app = create_app(test_config={
        "STORIES_DIR": stories_dir, "TESTING": True,
        "PASSWORD": "test-password", "SECRET_KEY": "test-secret-key",
        "CHILD_SLUG": "does-not-exist",
    })
    client = app.test_client()
    client.post("/login", data={"password": "test-password"})
    resp = client.get("/api/tree")
    assert resp.get_json()["anchor"] is None


def test_api_tree_photo_null_when_none(auth_client, stories_dir):
    people.create_person(_people_dir(stories_dir), "Someone")
    resp = auth_client.get("/api/tree")
    entry = resp.get_json()["people"][0]
    assert entry["photo"] is None


def test_api_tree_family_person_has_kinship_and_rels(auth_client, stories_dir):
    people_dir = _people_dir(stories_dir)
    papi = people.create_person(people_dir, "Papi", gender="m")
    people.create_person(people_dir, "Papa", parents=[papi])
    resp = auth_client.get("/api/tree")
    people_by_id = {p["id"]: p for p in resp.get_json()["people"]}
    assert "rels" in people_by_id["papi"]
    assert people_by_id["papi"]["rels"]["children"] == ["papa"]
    assert "kinship" in people_by_id["papi"]
    assert "friend_of" not in people_by_id["papi"]


def test_api_tree_friend_only_person_has_friend_of_key(auth_client, stories_dir):
    people_dir = _people_dir(stories_dir)
    papa = people.create_person(people_dir, "Papa")
    people.create_person(people_dir, "Ami Jean", friend_of=[papa])
    resp = auth_client.get("/api/tree")
    people_by_id = {p["id"]: p for p in resp.get_json()["people"]}
    jean = people_by_id["ami-jean"]
    assert jean["friend_of"] == [papa]
    assert "kinship" not in jean
    assert "rels" not in jean


def test_api_tree_unlinked_person_has_empty_friend_of(auth_client, stories_dir):
    people.create_person(_people_dir(stories_dir), "Solo Gaston")
    resp = auth_client.get("/api/tree")
    entry = resp.get_json()["people"][0]
    assert entry["friend_of"] == []


def test_api_tree_kinship_null_when_no_anchor(auth_client, stories_dir):
    people_dir = _people_dir(stories_dir)
    papi = people.create_person(people_dir, "Papi")
    people.create_person(people_dir, "Papa", parents=[papi])
    resp = auth_client.get("/api/tree")
    people_by_id = {p["id"]: p for p in resp.get_json()["people"]}
    assert people_by_id["papi"]["kinship"] is None


def test_api_tree_kinship_computed_relative_to_anchor(stories_dir):
    from app import create_app

    people_dir = _people_dir(stories_dir)
    papi = people.create_person(people_dir, "Papi", gender="m")
    papa = people.create_person(people_dir, "Papa", parents=[papi])
    people.create_person(people_dir, "Milo", parents=[papa])

    app = create_app(test_config={
        "STORIES_DIR": stories_dir, "TESTING": True,
        "PASSWORD": "test-password", "SECRET_KEY": "test-secret-key",
        "CHILD_SLUG": "milo",
    })
    client = app.test_client()
    client.post("/login", data={"password": "test-password"})
    resp = client.get("/api/tree")
    people_by_id = {p["id"]: p for p in resp.get_json()["people"]}
    assert people_by_id["papi"]["kinship"] == "your grandfather"


def test_api_tree_photo_resolves_to_person_media_url(auth_client, stories_dir):
    from io import BytesIO

    from PIL import Image

    people_dir = _people_dir(stories_dir)
    slug = people.create_person(people_dir, "Photo Person")
    buf = BytesIO()
    Image.new("RGB", (10, 10)).save(buf, format="JPEG")
    buf.seek(0)
    auth_client.post(
        f"/api/people/{slug}/images",
        data={"file": (buf, "photo.jpg")},
        content_type="multipart/form-data",
    )
    resp = auth_client.get("/api/tree")
    people_by_id = {p["id"]: p for p in resp.get_json()["people"]}
    assert people_by_id[slug]["photo"] == f"/people/{slug}/media/photo-001.jpg"
