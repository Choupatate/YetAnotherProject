"""Tests for FEATURES.md F27: life dates (birthdays, deaths, unions) —
the pure functions behind the timeline's quiet banners and the almanac."""

from datetime import date

from app import life_events, people


def _person(slug, name, born=None, died=None, unions=None):
    return people.Person(
        slug=slug, name=name, created=None, updated=None,
        born=born, died=died, unions=unions or [],
    )


def _union(partner, kind, since, until=None):
    return {"partner": partner, "kind": kind, "since": since, "until": until}


# --- birthdays_today ---------------------------------------------------------


def test_birthdays_today_matches_previous_year_same_month_day():
    today = date(2026, 6, 18)
    match = _person("mamie", "Mamie", born=date(1958, 6, 18))
    no_match = _person("papi", "Papi", born=date(1958, 6, 19))
    result = life_events.birthdays_today([match, no_match], today=today)
    assert [p.slug for p in result] == ["mamie"]


def test_birthdays_today_no_match_returns_empty():
    today = date(2026, 6, 18)
    result = life_events.birthdays_today([_person("a", "A", born=date(1958, 1, 1))], today=today)
    assert result == []


def test_birthdays_today_excludes_deceased():
    today = date(2026, 6, 18)
    deceased = _person("gone", "Gone", born=date(1958, 6, 18), died=date(2020, 1, 1))
    result = life_events.birthdays_today([deceased], today=today)
    assert result == []


def test_birthdays_today_excludes_birth_year_itself():
    today = date(2026, 6, 18)
    newborn = _person("baby", "Baby", born=date(2026, 6, 18))
    result = life_events.birthdays_today([newborn], today=today)
    assert result == []


def test_birthdays_today_feb29_surfaces_on_mar1_in_non_leap_year():
    today = date(2023, 3, 1)  # 2023 is not a leap year
    leap_baby = _person("leap", "Leap Baby", born=date(1996, 2, 29))
    result = life_events.birthdays_today([leap_baby], today=today)
    assert [p.slug for p in result] == ["leap"]


def test_birthdays_today_sorted_oldest_first():
    today = date(2026, 6, 18)
    younger = _person("younger", "Younger", born=date(1990, 6, 18))
    older = _person("older", "Older", born=date(1958, 6, 18))
    result = life_events.birthdays_today([younger, older], today=today)
    assert [p.slug for p in result] == ["older", "younger"]


# --- union_anniversaries_today ------------------------------------------------


def test_union_anniversaries_today_matches_and_dedupes_symmetric_records():
    today = date(2026, 6, 18)
    a = _person("a", "A", unions=[_union("b", "wedding", date(2015, 6, 18))])
    b = _person("b", "B", unions=[_union("a", "wedding", date(2015, 6, 18))])
    result = life_events.union_anniversaries_today([a, b], today=today)
    assert len(result) == 1
    assert result[0]["kind"] == "wedding"


def test_union_anniversaries_today_no_match_returns_empty():
    today = date(2026, 6, 18)
    a = _person("a", "A", unions=[_union("b", "wedding", date(2015, 1, 1))])
    b = _person("b", "B", unions=[_union("a", "wedding", date(2015, 1, 1))])
    result = life_events.union_anniversaries_today([a, b], today=today)
    assert result == []


def test_union_anniversaries_today_excludes_ended_unions():
    today = date(2026, 6, 18)
    a = _person("a", "A", unions=[_union("b", "wedding", date(2015, 6, 18), until=date(2020, 1, 1))])
    b = _person("b", "B", unions=[_union("a", "wedding", date(2015, 6, 18), until=date(2020, 1, 1))])
    result = life_events.union_anniversaries_today([a, b], today=today)
    assert result == []


def test_union_anniversaries_today_sorted_oldest_first():
    today = date(2026, 6, 18)
    a = _person("a", "A", unions=[_union("b", "wedding", date(1990, 6, 18))])
    b = _person("b", "B", unions=[_union("a", "wedding", date(1990, 6, 18))])
    c = _person("c", "C", unions=[_union("d", "pacs", date(2015, 6, 18))])
    d = _person("d", "D", unions=[_union("c", "pacs", date(2015, 6, 18))])
    result = life_events.union_anniversaries_today([a, b, c, d], today=today)
    assert [(m["person"].slug, m["partner"].slug) for m in result] == [("a", "b"), ("c", "d")]


# --- almanac_entries -----------------------------------------------------------


def test_almanac_entries_includes_born_and_died():
    p = _person("gone", "Gone", born=date(1958, 6, 18), died=date(2020, 3, 1))
    entries = life_events.almanac_entries([p])
    types = {(e["type"], e["date"]) for e in entries}
    assert ("born", date(1958, 6, 18)) in types
    assert ("died", date(2020, 3, 1)) in types


def test_almanac_entries_union_dedupes_and_carries_until():
    a = _person("a", "A", unions=[_union("b", "wedding", date(2015, 6, 18), until=date(2020, 1, 1))])
    b = _person("b", "B", unions=[_union("a", "wedding", date(2015, 6, 18), until=date(2020, 1, 1))])
    entries = life_events.almanac_entries([a, b])
    union_entries = [e for e in entries if e["type"] == "union"]
    assert len(union_entries) == 1
    assert union_entries[0]["until"] == date(2020, 1, 1)


def test_almanac_entries_sorted_by_month_day():
    p1 = _person("p1", "P1", born=date(1990, 12, 25))
    p2 = _person("p2", "P2", born=date(1990, 1, 5))
    entries = life_events.almanac_entries([p1, p2])
    assert [e["person"].slug for e in entries] == ["p2", "p1"]


# --- route rendering (real relative dates, no monkeypatching) ---------------


def test_timeline_shows_birthday_banner(auth_client, stories_dir):
    from app import storage

    today = date.today()
    born = today.replace(year=today.year - 70) if not (today.month == 2 and today.day == 29) \
        else today.replace(year=today.year - 70, day=28)
    people.create_person(stories_dir / "people", "Mamie", born=born)
    storage.create_story(stories_dir, "Unrelated", date(2020, 1, 1), "")

    resp = auth_client.get("/")
    html = resp.data.decode()
    assert "timeline__onthisday" in html
    assert "Mamie" in html
    assert "turns 70 today" in html


def test_timeline_no_birthday_banner_for_deceased(auth_client, stories_dir):
    from app import storage

    today = date.today()
    born = today.replace(year=today.year - 70) if not (today.month == 2 and today.day == 29) \
        else today.replace(year=today.year - 70, day=28)
    people.create_person(
        stories_dir / "people", "Gone", born=born, died=date(2020, 1, 1)
    )
    storage.create_story(stories_dir, "Unrelated", date(2020, 1, 1), "")

    resp = auth_client.get("/")
    html = resp.data.decode()
    assert "timeline__onthisday" not in html


def test_almanac_page_lists_entries(auth_client, stories_dir):
    people.create_person(stories_dir / "people", "Grandma", born=date(1940, 5, 3))
    resp = auth_client.get("/almanac")
    html = resp.data.decode()
    assert "Grandma" in html
    assert "May" in html


def test_almanac_page_empty_state(auth_client, stories_dir):
    people.create_person(stories_dir / "people", "Solo")
    resp = auth_client.get("/almanac")
    html = resp.data.decode()
    assert "take its place here" in html


def test_almanac_requires_auth(client):
    resp = client.get("/almanac")
    assert resp.status_code == 302


def test_people_page_shows_almanac_link_only_when_life_dates_exist(auth_client, stories_dir):
    resp = auth_client.get("/people")
    assert b"Almanac" not in resp.data

    people.create_person(stories_dir / "people", "Grandma", born=date(1940, 5, 3))
    resp = auth_client.get("/people")
    assert b"Almanac" in resp.data
