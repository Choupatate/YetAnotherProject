"""Tests for FEATURES.md F32: the MCP server (app/mcp_server.py) exposing
Storybook's stories/people as read-write tools for AI assistants.

The `@mcp.tool()` decorator returns the plain function unchanged (verified
directly against the installed SDK), so every tool below is called exactly
like any other Python function against a monkeypatched
STORYBOOK_STORIES_DIR — no MCP transport/client is involved in these tests.
"""

import base64
import io

import pytest
from PIL import Image

from app import mcp_server as m


@pytest.fixture(autouse=True)
def _stories_env(tmp_path, monkeypatch):
    monkeypatch.setenv("STORYBOOK_STORIES_DIR", str(tmp_path))
    monkeypatch.delenv("STORYBOOK_AUTHORS", raising=False)
    monkeypatch.delenv("STORYBOOK_BIRTHDATE", raising=False)
    monkeypatch.delenv("STORYBOOK_TITLE", raising=False)
    return tmp_path


def _jpeg_b64(color="red", size=(30, 30)):
    buf = io.BytesIO()
    Image.new("RGB", size, color=color).save(buf, format="JPEG")
    return base64.b64encode(buf.getvalue()).decode()


# --- stories: create/read/update ------------------------------------------


def test_create_and_get_story_round_trip():
    created = m.create_story(title="First steps", date="2024-06-20", body="Wobbly!",
                              tags=["milestone"], milestone="First steps")
    story = m.get_story(created["id"])
    assert story["title"] == "First steps"
    assert story["date"] == "2024-06-20"
    assert story["body"] == "Wobbly!"
    assert story["tags"] == ["milestone"]
    assert story["milestone"] == "First steps"


def test_get_story_missing_raises():
    with pytest.raises(ValueError):
        m.get_story("does-not-exist")


def test_create_story_bad_date_raises():
    with pytest.raises(ValueError, match="ISO date"):
        m.create_story(title="X", date="not-a-date")


def test_create_story_unknown_person_raises():
    with pytest.raises(ValueError, match="Unknown person"):
        m.create_story(title="X", date="2024-01-01", people_slugs=["ghost"])


def test_create_instant_allows_blank_title():
    created = m.create_story(title="", date="2024-01-01", kind="instant")
    assert created["title"] == ""
    story = m.get_story(created["id"])
    assert story["title"] == "Instant"


def test_create_story_rejects_blank_title():
    with pytest.raises(ValueError, match="Title is required"):
        m.create_story(title="  ", date="2024-01-01")


def test_update_story_requires_title_date_body_and_overwrites_them():
    created = m.create_story(title="Original", date="2024-01-01", body="old")
    m.update_story(created["id"], title="Renamed", date="2024-02-02", body="new")
    story = m.get_story(created["id"])
    assert story["title"] == "Renamed"
    assert story["date"] == "2024-02-02"
    assert story["body"] == "new"


def test_update_story_leaves_omitted_fields_unchanged():
    created = m.create_story(title="T", date="2024-01-01", body="b", tags=["a"], milestone="First")
    m.update_story(created["id"], title="T2", date="2024-01-01", body="b2")
    story = m.get_story(created["id"])
    assert story["tags"] == ["a"]
    assert story["milestone"] == "First"


def test_update_story_empty_list_clears_tags():
    created = m.create_story(title="T", date="2024-01-01", tags=["a", "b"])
    m.update_story(created["id"], title="T", date="2024-01-01", body="", tags=[])
    story = m.get_story(created["id"])
    assert story["tags"] == []


def test_update_story_draft_and_archived_default_to_unchanged():
    created = m.create_story(title="T", date="2024-01-01", draft=True)
    m.update_story(created["id"], title="T2", date="2024-01-01", body="")
    story = m.get_story(created["id"])
    assert story["draft"] is True


def test_update_story_missing_raises():
    with pytest.raises(ValueError):
        m.update_story("does-not-exist", title="T", date="2024-01-01", body="")


# --- story photos -----------------------------------------------------------


def test_add_story_photo_and_set_as_cover():
    created = m.create_story(title="T", date="2024-01-01")
    photo = m.add_story_photo(created["id"], _jpeg_b64())
    assert photo["filename"].startswith("photo-")
    m.update_story(created["id"], title="T", date="2024-01-01", body="", cover=photo["filename"])
    story = m.get_story(created["id"])
    assert story["cover"] == photo["filename"]


def test_add_story_photo_missing_story_raises():
    with pytest.raises(ValueError):
        m.add_story_photo("does-not-exist", _jpeg_b64())


def test_add_story_photo_bad_base64_raises():
    created = m.create_story(title="T", date="2024-01-01")
    with pytest.raises(ValueError, match="base64"):
        m.add_story_photo(created["id"], "not-valid-base64!!!")


def test_add_story_photo_accepts_data_uri_prefix():
    created = m.create_story(title="T", date="2024-01-01")
    photo = m.add_story_photo(created["id"], "data:image/jpeg;base64," + _jpeg_b64())
    assert photo["filename"].startswith("photo-")


# --- list_stories filters ----------------------------------------------------


def test_list_stories_excludes_drafts_by_default():
    m.create_story(title="Published", date="2024-01-01")
    m.create_story(title="Draft", date="2024-01-02", draft=True)
    result = m.list_stories()
    titles = [s["title"] for s in result]
    assert "Published" in titles
    assert "Draft" not in titles


def test_list_stories_include_drafts():
    m.create_story(title="Draft", date="2024-01-02", draft=True)
    result = m.list_stories(include_drafts=True)
    assert any(s["title"] == "Draft" for s in result)


def test_list_stories_filters_by_tag_and_person_and_milestone():
    papa = m.create_person(name="Papa")
    m.create_story(title="A", date="2024-01-01", tags=["park"], people_slugs=[papa["id"]])
    m.create_story(title="B", date="2024-01-02", milestone="First words")
    m.create_story(title="C", date="2024-01-03")

    assert [s["title"] for s in m.list_stories(tag="park")] == ["A"]
    assert [s["title"] for s in m.list_stories(person_slug=papa["id"])] == ["A"]
    assert [s["title"] for s in m.list_stories(milestones_only=True)] == ["B"]


def test_list_stories_date_range():
    m.create_story(title="Jan", date="2024-01-15")
    m.create_story(title="Feb", date="2024-02-15")
    result = m.list_stories(since="2024-02-01", until="2024-02-28")
    assert [s["title"] for s in result] == ["Feb"]


# --- people: create/read/update ---------------------------------------------


def test_create_and_get_person_round_trip():
    created = m.create_person(name="Papa", relation="Papa", gender="m", born="1985-03-01")
    person = m.get_person(created["id"])
    assert person["name"] == "Papa"
    assert person["gender"] == "m"
    assert person["born"] == "1985-03-01"


def test_get_person_missing_raises():
    with pytest.raises(ValueError):
        m.get_person("ghost")


def test_create_person_requires_name():
    with pytest.raises(ValueError, match="Name is required"):
        m.create_person(name="  ")


def test_create_person_invalid_gender_raises():
    with pytest.raises(ValueError, match="Gender"):
        m.create_person(name="X", gender="other")


def test_update_person_rejects_self_as_parent():
    created = m.create_person(name="Solo")
    with pytest.raises(ValueError, match="own parent"):
        m.update_person(created["id"], name="Solo", parents=[created["id"]])


def test_update_person_death_before_birth_raises():
    created = m.create_person(name="X", born="2000-01-01")
    with pytest.raises(ValueError, match="before"):
        m.update_person(created["id"], name="X", died="1999-01-01")


def test_update_person_born_died_leave_unchanged_when_omitted():
    created = m.create_person(name="X", born="2000-01-01")
    m.update_person(created["id"], name="X (renamed)")
    person = m.get_person(created["id"])
    assert person["born"] == "2000-01-01"


def test_update_person_empty_string_clears_born():
    created = m.create_person(name="X", born="2000-01-01")
    m.update_person(created["id"], name="X", born="")
    person = m.get_person(created["id"])
    assert person["born"] is None


def test_update_person_parents_cycle_rejected():
    a = m.create_person(name="A")
    b = m.create_person(name="B", parents=[a["id"]])
    with pytest.raises(ValueError, match="cycle"):
        m.update_person(a["id"], name="A", parents=[b["id"]])


# --- partner/union symmetry ---------------------------------------------------


def test_partner_and_union_symmetry_synced_to_other_person():
    papa = m.create_person(name="Papa")
    maman = m.create_person(name="Maman")
    m.update_person(
        papa["id"], name="Papa", partners=[maman["id"]],
        unions=[{"partner": maman["id"], "kind": "wedding", "since": "2018-05-01"}],
    )
    other = m.get_person(maman["id"])
    assert other["partners"] == [papa["id"]]
    assert other["unions"] == [{"partner": papa["id"], "kind": "wedding",
                                 "since": "2018-05-01", "until": None}]


def test_removing_partner_drops_union_on_both_sides():
    papa = m.create_person(name="Papa")
    maman = m.create_person(name="Maman")
    m.update_person(
        papa["id"], name="Papa", partners=[maman["id"]],
        unions=[{"partner": maman["id"], "kind": "wedding", "since": "2018-05-01"}],
    )
    m.update_person(papa["id"], name="Papa", partners=[])
    assert m.get_person(papa["id"])["unions"] == []
    assert m.get_person(maman["id"])["partners"] == []
    assert m.get_person(maman["id"])["unions"] == []


def test_union_unknown_kind_raises():
    papa = m.create_person(name="Papa")
    maman = m.create_person(name="Maman")
    with pytest.raises(ValueError, match="kind"):
        m.update_person(
            papa["id"], name="Papa", partners=[maman["id"]],
            unions=[{"partner": maman["id"], "kind": "engagement", "since": "2018-05-01"}],
        )


def test_union_partner_not_in_partners_raises():
    papa = m.create_person(name="Papa")
    maman = m.create_person(name="Maman")
    with pytest.raises(ValueError, match="partner"):
        m.update_person(
            papa["id"], name="Papa", partners=[],
            unions=[{"partner": maman["id"], "kind": "wedding", "since": "2018-05-01"}],
        )


# --- person photo ------------------------------------------------------------


def test_set_person_photo():
    created = m.create_person(name="Papa")
    photo = m.set_person_photo(created["id"], _jpeg_b64())
    assert photo["filename"].startswith("photo-")
    person = m.get_person(created["id"])
    assert person is not None


def test_set_person_photo_missing_raises():
    with pytest.raises(ValueError):
        m.set_person_photo("ghost", _jpeg_b64())


# --- author validation --------------------------------------------------------


def test_create_story_unknown_author_rejected_when_authors_configured(monkeypatch):
    monkeypatch.setenv("STORYBOOK_AUTHORS", "Papa:#d9a441,Maman:#7ba7d9")
    with pytest.raises(ValueError, match="Unknown author"):
        m.create_story(title="T", date="2024-01-01", author="Stranger")


def test_create_story_known_author_accepted(monkeypatch):
    monkeypatch.setenv("STORYBOOK_AUTHORS", "Papa:#d9a441")
    created = m.create_story(title="T", date="2024-01-01", author="Papa")
    assert m.get_story(created["id"])["author"] == "Papa"


def test_create_story_any_author_accepted_when_unconfigured():
    created = m.create_story(title="T", date="2024-01-01", author="Anyone")
    assert m.get_story(created["id"])["author"] == "Anyone"


# --- get_journal_context -------------------------------------------------------


def test_journal_context_empty():
    ctx = m.get_journal_context()
    assert ctx["total_stories"] == 0
    assert ctx["most_recent_story"] is None
    assert ctx["months_since_last_story"] is None
    assert ctx["quiet_spell"] is False


def test_journal_context_reports_recent_story_and_firsts():
    m.create_story(title="A first", date="2024-01-01", milestone="First words")
    ctx = m.get_journal_context()
    assert ctx["total_stories"] == 1
    assert ctx["most_recent_story"]["title"] == "A first"
    assert ctx["firsts_count"] == 1


def test_journal_context_child_age_requires_birthdate(monkeypatch):
    assert m.get_journal_context()["child_age_today"] is None
    monkeypatch.setenv("STORYBOOK_BIRTHDATE", "2020-01-01")
    assert m.get_journal_context()["child_age_today"] is not None


def test_journal_context_todays_birthdays_and_anniversaries():
    from datetime import date
    today = date.today()
    m.create_person(name="Mamie", born=today.replace(year=today.year - 70).isoformat())
    ctx = m.get_journal_context()
    assert any(b["name"] == "Mamie" for b in ctx["todays_birthdays"])
