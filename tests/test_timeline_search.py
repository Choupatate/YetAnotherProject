"""Tests for client-side timeline search and jump-to-latest.

The filtering/scrolling itself is pure client-side JS (see timeline.js) and
is exercised manually with a headless browser; these tests cover the
server-rendered markup that script depends on."""

from datetime import date

from app import storage


def test_timeline_includes_search_and_jump_markup_when_stories_exist(auth_client, stories_dir):
    storage.create_story(stories_dir, "A story", date(2026, 1, 1), "")
    resp = auth_client.get("/")
    html = resp.data.decode()
    assert 'id="timeline-search"' in html
    assert 'id="timeline-jump-latest"' in html
    assert 'id="timeline-search-empty"' in html


def test_timeline_empty_state_has_no_search_markup(auth_client):
    resp = auth_client.get("/")
    html = resp.data.decode()
    assert "No stories yet" in html
    assert 'id="timeline-search"' not in html


def test_timeline_includes_hidden_tags_and_people_for_search_matching(auth_client, stories_dir):
    from app import people

    people_dir = stories_dir / "people"
    grandma = people.create_person(people_dir, "Grandma")
    storage.create_story(
        stories_dir, "Beach day", date(2026, 1, 1), "", people=[grandma], tags=["beach"],
    )
    resp = auth_client.get("/")
    html = resp.data.decode()
    assert 'class="timeline__tags" hidden' in html
    assert "beach" in html
    assert "Grandma" in html


def test_timeline_does_not_leak_sealed_story_tags_or_people(auth_client, stories_dir):
    from datetime import date as date_cls

    from app import people

    people_dir = stories_dir / "people"
    secret_person = people.create_person(people_dir, "Secret Person")
    storage.create_story(
        stories_dir, "Sealed story", date(2026, 1, 1), "",
        people=[secret_person], tags=["secret-tag"], unlock=date_cls(2099, 1, 1),
    )
    resp = auth_client.get("/")
    html = resp.data.decode()
    assert "secret-tag" not in html
    assert "Secret Person" not in html
