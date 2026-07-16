"""Tests for FEATURES.md F18: the person page's Family section and the
computed kinship/friend-of small-caps line."""

import pytest

from app import people


def _people_dir(stories_dir):
    return stories_dir / "people"


@pytest.fixture
def anchored_client(auth_client_factory):
    def _make(child_slug):
        return auth_client_factory(CHILD_SLUG=child_slug)
    return _make


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


def test_person_page_family_thumb_uses_portrait_when_available(auth_client, stories_dir, jpeg_bytes):
    people_dir = _people_dir(stories_dir)
    papi = people.create_person(people_dir, "Papi Georges")
    auth_client.post(
        f"/api/people/{papi}/photo",
        data={"file": (jpeg_bytes(size=(10, 10)), "photo.jpg")},
        content_type="multipart/form-data",
    )
    slug = people.create_person(people_dir, "Papa", parents=[papi])

    resp = auth_client.get(f"/people/{slug}")
    html = resp.data.decode()
    assert f"/people/{papi}/media/photo-001.jpg" in html


# --- Kinship label: the small-caps line ----------------------------------


def test_person_page_kinship_label_shown_when_relation_absent(stories_dir, anchored_client):
    people_dir = _people_dir(stories_dir)
    adele = people.create_person(people_dir, "Great-Grandma Adele", gender="f")
    georges = people.create_person(people_dir, "Papi Georges", parents=[adele])
    papa = people.create_person(people_dir, "Papa", parents=[georges])
    people.create_person(people_dir, "Milo", parents=[papa])

    client = anchored_client("milo")
    resp = client.get(f"/people/{adele}")
    html = resp.data.decode()
    assert "your great-grandmother" in html


def test_person_page_relation_wins_over_kinship_label(stories_dir, anchored_client):
    people_dir = _people_dir(stories_dir)
    papi = people.create_person(
        people_dir, "Papi Georges", relation="the family patriarch",
    )
    papa = people.create_person(people_dir, "Papa", parents=[papi])
    people.create_person(people_dir, "Milo", parents=[papa])

    client = anchored_client("milo")
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


def test_new_person_editor_shows_hint_when_no_other_people(auth_client):
    resp = auth_client.get("/new-person")
    html = resp.data.decode()
    assert "editor__family-hint" in html
    assert "Add another person" in html


def test_new_person_editor_no_hint_when_other_people_exist(auth_client, stories_dir):
    people.create_person(_people_dir(stories_dir), "Someone")
    resp = auth_client.get("/new-person")
    html = resp.data.decode()
    assert "editor__family-hint" not in html


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


def test_edit_person_editor_relation_input_empty_not_literal_none(auth_client, stories_dir):
    """Regression: a person with no relation set must render an empty
    input value, not the literal text "None" (Jinja stringifies a bare
    `person.relation` when it's Python None) — otherwise saving the Family
    fieldset without retyping Relation silently sets relation to "None"
    and permanently hides the computed kinship label."""
    people_dir = _people_dir(stories_dir)
    slug = people.create_person(people_dir, "No Relation Yet")
    people.create_person(people_dir, "Other")
    resp = auth_client.get(f"/edit-person/{slug}")
    html = resp.data.decode()
    assert 'id="person-relation"' in html
    assert 'value="None"' not in html
    assert 'value=""' in html


def test_editor_js_and_family_picker_script_present_on_person_editor(auth_client, stories_dir):
    people.create_person(_people_dir(stories_dir), "Someone")
    resp = auth_client.get("/new-person")
    assert b'js/editor.js' in resp.data


# --- /people discoverability link -------------------------------------------


def test_people_page_no_tree_link_when_no_family_links(auth_client, stories_dir):
    people.create_person(_people_dir(stories_dir), "Solo")
    resp = auth_client.get("/people")
    assert b"Family tree" not in resp.data


def test_people_page_shows_tree_link_when_parents_exist(auth_client, stories_dir):
    people_dir = _people_dir(stories_dir)
    papi = people.create_person(people_dir, "Papi")
    people.create_person(people_dir, "Papa", parents=[papi])
    resp = auth_client.get("/people")
    assert b"Family tree" in resp.data


def test_people_page_shows_tree_link_when_only_partners_exist(auth_client, stories_dir):
    people_dir = _people_dir(stories_dir)
    a = people.create_person(people_dir, "A")
    people.create_person(people_dir, "B", partners=[a])
    resp = auth_client.get("/people")
    assert b"Family tree" in resp.data


def test_people_page_no_tree_link_with_only_friend_of(auth_client, stories_dir):
    people_dir = _people_dir(stories_dir)
    a = people.create_person(people_dir, "A")
    people.create_person(people_dir, "B", friend_of=[a])
    resp = auth_client.get("/people")
    assert b"Family tree" not in resp.data


# --- /tree page ---------------------------------------------------------


def test_tree_page_requires_auth(client):
    resp = client.get("/tree")
    assert resp.status_code == 302


def test_tree_page_empty_state_when_no_family_links(auth_client, stories_dir):
    people.create_person(_people_dir(stories_dir), "Solo")
    resp = auth_client.get("/tree")
    html = resp.data.decode()
    assert "Link two people in the person editor" in html
    assert 'id="FamilyChart"' not in html


def test_tree_page_renders_chart_container_when_linked(auth_client, stories_dir):
    people_dir = _people_dir(stories_dir)
    papi = people.create_person(people_dir, "Papi")
    people.create_person(people_dir, "Papa", parents=[papi])
    resp = auth_client.get("/tree")
    html = resp.data.decode()
    assert 'id="FamilyChart"' in html
    assert 'data-tree-url="/api/tree"' in html


def test_tree_page_loads_vendored_scripts(auth_client, stories_dir):
    people_dir = _people_dir(stories_dir)
    papi = people.create_person(people_dir, "Papi")
    people.create_person(people_dir, "Papa", parents=[papi])
    resp = auth_client.get("/tree")
    html = resp.data.decode()
    assert "vendor/d3/d3.min.js" in html
    assert "vendor/familychart/family-chart.min.js" in html
    assert "vendor/familychart/family-chart.css" in html
    assert "js/safe-storage.js" in html
    assert "js/tree-logic.js" in html
    assert "js/tree.js" in html
    # safe-storage.js and tree-logic.js (both used by tree.js) must load
    # before tree.js itself
    assert html.index("js/safe-storage.js") < html.index("js/tree.js")
    assert html.index("js/tree-logic.js") < html.index("js/tree.js")


def test_tree_page_no_vendored_scripts_when_empty(auth_client, stories_dir):
    people.create_person(_people_dir(stories_dir), "Solo")
    resp = auth_client.get("/tree")
    html = resp.data.decode()
    assert "family-chart.min.js" not in html


def test_tree_page_has_views_toolbar_container_when_linked(auth_client, stories_dir):
    people_dir = _people_dir(stories_dir)
    papi = people.create_person(people_dir, "Papi")
    people.create_person(people_dir, "Papa", parents=[papi])
    resp = auth_client.get("/tree")
    html = resp.data.decode()
    assert 'id="tree-views"' in html


def test_tree_page_no_views_toolbar_when_empty(auth_client, stories_dir):
    people.create_person(_people_dir(stories_dir), "Solo")
    resp = auth_client.get("/tree")
    html = resp.data.decode()
    assert 'id="tree-views"' not in html


def test_tree_page_lists_friend_only_person_in_others(auth_client, stories_dir):
    people_dir = _people_dir(stories_dir)
    papi = people.create_person(people_dir, "Papi")
    people.create_person(people_dir, "Papa", parents=[papi])
    people.create_person(people_dir, "Ami Jean", friend_of=[papi])

    resp = auth_client.get("/tree")
    html = resp.data.decode()
    assert "Ami Jean" in html
    assert "friend of" in html
    assert f'href="/people/{papi}"' in html


def test_tree_page_lists_fully_unlinked_person_in_others(auth_client, stories_dir):
    people_dir = _people_dir(stories_dir)
    papi = people.create_person(people_dir, "Papi")
    people.create_person(people_dir, "Papa", parents=[papi])
    people.create_person(people_dir, "Solo Gaston")

    resp = auth_client.get("/tree")
    html = resp.data.decode()
    assert "Solo Gaston" in html


def test_tree_page_family_member_not_in_others_list(auth_client, stories_dir):
    people_dir = _people_dir(stories_dir)
    papi = people.create_person(people_dir, "Papi")
    people.create_person(people_dir, "Papa", parents=[papi])

    resp = auth_client.get("/tree")
    html = resp.data.decode()
    others_section = html[html.find("tree__others") :]
    assert "Papi" not in others_section
    assert "Papa" not in others_section


# --- /tree print outline -------------------------------------------------


def test_tree_page_print_outline_groups_by_generation_with_anchor(stories_dir, anchored_client):
    people_dir = _people_dir(stories_dir)
    papi = people.create_person(people_dir, "Papi Georges", gender="m")
    papa = people.create_person(people_dir, "Papa", parents=[papi], gender="m")
    milo = people.create_person(people_dir, "Milo", parents=[papa], gender="m")

    client = anchored_client(milo)
    resp = client.get("/tree")
    html = resp.data.decode()
    outline = html[html.find("tree__print-outline") : html.find("tree__others")]

    assert "Grandparents’ generation" in outline
    assert "Parents’ generation" in outline
    assert "Milo’s generation" in outline
    assert "Papi Georges" in outline
    assert "your grandfather" in outline
    assert "Papa" in outline
    assert "your father" in outline
    # Order: oldest generation first.
    assert outline.find("Grandparents’ generation") < outline.find("Parents’ generation")
    assert outline.find("Parents’ generation") < outline.find("Milo’s generation")


def test_tree_page_print_outline_single_bucket_without_anchor(auth_client, stories_dir):
    people_dir = _people_dir(stories_dir)
    papi = people.create_person(people_dir, "Papi Georges")
    people.create_person(people_dir, "Papa", parents=[papi])

    resp = auth_client.get("/tree")
    html = resp.data.decode()
    outline = html[html.find("tree__print-outline") : html.find("tree__others")]
    assert "Family" in outline
    assert "Papi Georges" in outline
    assert "Papa" in outline
    assert "your" not in outline.lower()


def test_tree_page_print_outline_excludes_friends_and_unlinked(stories_dir, anchored_client):
    people_dir = _people_dir(stories_dir)
    papi = people.create_person(people_dir, "Papi Georges", gender="m")
    milo = people.create_person(people_dir, "Milo", parents=[papi], gender="m")
    people.create_person(people_dir, "Ami Jean", friend_of=[papi])
    people.create_person(people_dir, "Solo Gaston")

    client = anchored_client(milo)
    resp = client.get("/tree")
    html = resp.data.decode()
    outline = html[html.find("tree__print-outline") : html.find("tree__others")]
    assert "Ami Jean" not in outline
    assert "Solo Gaston" not in outline
