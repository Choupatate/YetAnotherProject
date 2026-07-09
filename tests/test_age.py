"""Tests for FEATURES.md F3: age at each memory."""

from datetime import date, timedelta

import pytest

from app import create_app, dates, storage


# --- app.dates.age_label -------------------------------------------------------


def test_age_before_birth():
    assert dates.age_label(date(2023, 6, 18), date(2023, 6, 17)) == "before you were born"


def test_age_days_old_singular_and_plural():
    assert dates.age_label(date(2023, 6, 18), date(2023, 6, 18)) == "0 days old"
    assert dates.age_label(date(2023, 6, 18), date(2023, 6, 19)) == "1 day old"
    assert dates.age_label(date(2023, 6, 18), date(2023, 7, 1)) == "13 days old"


def test_age_day_adjustment_edge_born_20th_story_19th_later_month():
    # Jan 20 -> Feb 19 is 30 days but not yet a full month (one day short).
    assert dates.age_label(date(2023, 1, 20), date(2023, 2, 19)) == "30 days old"
    # Jan 20 -> Feb 20 is exactly one full month.
    assert dates.age_label(date(2023, 1, 20), date(2023, 2, 20)) == "1 month old"


def test_age_months_old_singular_and_plural():
    assert dates.age_label(date(2023, 1, 1), date(2023, 2, 1)) == "1 month old"
    assert dates.age_label(date(2023, 1, 1), date(2023, 6, 1)) == "5 months old"
    assert dates.age_label(date(2023, 1, 1), date(2023, 12, 31)) == "11 months old"


def test_age_years_old_singular_and_plural():
    assert dates.age_label(date(2020, 6, 18), date(2023, 6, 18)) == "3 years old"
    assert dates.age_label(date(2020, 6, 18), date(2023, 6, 17)) == "2 years old"
    assert dates.age_label(date(2020, 6, 18), date(2021, 6, 18)) == "1 year old"


def test_age_year_wrap_day_adjustment():
    # Nov 20 -> Jan 19 the following year is one day short of two full months.
    assert dates.age_label(date(2022, 11, 20), date(2023, 1, 19)) == "1 month old"


# --- config parsing --------------------------------------------------------------


def test_birthdate_unset_disables_feature(monkeypatch, tmp_path):
    monkeypatch.delenv("STORYBOOK_BIRTHDATE", raising=False)
    monkeypatch.setenv("STORYBOOK_STORIES_DIR", str(tmp_path))
    app = create_app()
    assert app.config["BIRTHDATE"] is None


def test_birthdate_valid_parses(monkeypatch, tmp_path):
    monkeypatch.setenv("STORYBOOK_BIRTHDATE", "2023-06-18")
    monkeypatch.setenv("STORYBOOK_STORIES_DIR", str(tmp_path))
    app = create_app()
    assert app.config["BIRTHDATE"] == date(2023, 6, 18)


def test_birthdate_malformed_raises(monkeypatch, tmp_path):
    monkeypatch.setenv("STORYBOOK_BIRTHDATE", "not-a-date")
    monkeypatch.setenv("STORYBOOK_STORIES_DIR", str(tmp_path))
    with pytest.raises(RuntimeError, match="STORYBOOK_BIRTHDATE"):
        create_app()


# --- page rendering ----------------------------------------------------------------


@pytest.fixture
def dated_app(tmp_path):
    stories_dir = tmp_path / "stories"
    stories_dir.mkdir()
    return create_app(
        test_config={
            "STORIES_DIR": stories_dir,
            "TESTING": True,
            "PASSWORD": "test-password",
            "SECRET_KEY": "test-secret-key",
            "BIRTHDATE": date(2020, 6, 18),
        }
    )


@pytest.fixture
def dated_stories_dir(dated_app):
    return dated_app.config["STORIES_DIR"]


@pytest.fixture
def dated_client(dated_app):
    return dated_app.test_client()


@pytest.fixture
def dated_auth_client(dated_client):
    dated_client.post("/login", data={"password": "test-password"})
    return dated_client


def test_story_page_shows_age_when_configured(dated_auth_client, dated_stories_dir):
    story_id = storage.create_story(dated_stories_dir, "Story", date(2023, 6, 18), "body")
    resp = dated_auth_client.get(f"/story/{story_id}")
    html = resp.data.decode()
    assert "story__age" in html
    assert "3 years old" in html


def test_story_page_hides_age_when_not_configured(auth_client, stories_dir):
    story_id = storage.create_story(stories_dir, "Story", date(2023, 6, 18), "body")
    resp = auth_client.get(f"/story/{story_id}")
    html = resp.data.decode()
    assert "story__age" not in html


def test_timeline_shows_age_when_configured(dated_auth_client, dated_stories_dir):
    storage.create_story(dated_stories_dir, "Story", date(2023, 6, 18), "")
    resp = dated_auth_client.get("/")
    html = resp.data.decode()
    assert "timeline__age" in html
    assert "3 years old" in html


def test_sealed_story_does_not_show_age(dated_auth_client, dated_stories_dir):
    future = date.today() + timedelta(days=365)
    story_id = storage.create_story(
        dated_stories_dir, "Secret", date(2023, 6, 18), "body", unlock=future
    )
    resp = dated_auth_client.get(f"/story/{story_id}")
    html = resp.data.decode()
    assert "story__age" not in html

    resp = dated_auth_client.get("/")
    html = resp.data.decode()
    assert "timeline__age" not in html
