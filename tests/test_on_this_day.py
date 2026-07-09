"""Tests for FEATURES.md F5: "X years ago today"."""

from datetime import date, timedelta

from app import storage


# --- storage.on_this_day (pure, explicit today) -----------------------------


def _story(id_, year, month, day, **kwargs):
    return storage.Story(
        id=id_, title=id_, date=date(year, month, day), created=None, updated=None, **kwargs
    )


def test_on_this_day_matches_previous_year_same_month_day():
    today = date(2026, 6, 18)
    match = _story("match", 2023, 6, 18)
    no_match = _story("no-match", 2023, 6, 19)
    result = storage.on_this_day([match, no_match], today=today)
    assert [s.id for s in result] == ["match"]


def test_on_this_day_no_match_returns_empty():
    today = date(2026, 6, 18)
    result = storage.on_this_day([_story("a", 2023, 1, 1)], today=today)
    assert result == []


def test_on_this_day_multiple_matches_capped_at_3_newest_first():
    today = date(2026, 6, 18)
    stories = [
        _story("y1", 2025, 6, 18),
        _story("y2", 2024, 6, 18),
        _story("y3", 2023, 6, 18),
        _story("y4", 2022, 6, 18),
    ]
    result = storage.on_this_day(stories, today=today)
    assert [s.id for s in result] == ["y1", "y2", "y3"]


def test_on_this_day_feb29_surfaces_on_mar1_in_non_leap_year():
    today = date(2023, 3, 1)  # 2023 is not a leap year
    story = _story("leap-baby", 2020, 2, 29)
    result = storage.on_this_day([story], today=today)
    assert [s.id for s in result] == ["leap-baby"]


def test_on_this_day_feb29_not_needed_on_mar1_in_leap_year():
    today = date(2024, 3, 1)  # 2024 is a leap year, Feb 29 already happened
    story = _story("leap-baby", 2020, 2, 29)
    result = storage.on_this_day([story], today=today)
    assert result == []


def test_on_this_day_excludes_drafts_and_sealed():
    today = date(2026, 6, 18)
    draft = _story("draft", 2023, 6, 18, draft=True)
    sealed = _story("sealed", 2023, 6, 18, unlock=date(2030, 1, 1))
    result = storage.on_this_day([draft, sealed], today=today)
    assert result == []


# --- route rendering (real relative dates, no monkeypatching) ---------------


def test_timeline_banner_shows_match(auth_client, stories_dir):
    today = date.today()
    match_date = today.replace(year=today.year - 3) if not (today.month == 2 and today.day == 29) \
        else today.replace(year=today.year - 3, day=28)
    storage.create_story(stories_dir, "First bike ride", match_date, "")

    resp = auth_client.get("/")
    html = resp.data.decode()
    assert "timeline__onthisday" in html
    assert "years ago today" in html or "year ago today" in html
    assert "First bike ride" in html


def test_timeline_banner_absent_when_no_match(auth_client, stories_dir):
    storage.create_story(stories_dir, "Unrelated", date(2020, 1, 1), "")
    resp = auth_client.get("/")
    if date.today().month == 1 and date.today().day == 1:
        return  # skip on the one real day this would coincidentally match
    html = resp.data.decode()
    assert "timeline__onthisday" not in html


def test_timeline_banner_excludes_draft_and_sealed(auth_client, stories_dir):
    today = date.today()
    match_date = today.replace(year=today.year - 3) if not (today.month == 2 and today.day == 29) \
        else today.replace(year=today.year - 3, day=28)
    storage.create_story(stories_dir, "A draft memory", match_date, "", draft=True)
    storage.create_story(
        stories_dir, "A sealed memory", match_date, "", unlock=today + timedelta(days=365)
    )

    resp = auth_client.get("/")
    html = resp.data.decode()
    assert "timeline__onthisday" not in html
