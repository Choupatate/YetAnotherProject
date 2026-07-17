"""Tests for FEATURES.md F19 Phase 3: delegated write-links
(app/write_links.py)."""

from datetime import datetime, timedelta

import pytest

from app import people, write_links


def test_create_link_round_trips(people_dir):
    slug = people.create_person(people_dir, "Papa")
    link, token = write_links.create_link(people_dir, slug, label="for the recital")

    assert link.person_slug == slug
    assert link.label == "for the recital"
    assert link.single_use is True
    assert link.revoked is False
    assert link.used_at is None
    assert len(token) > 20
    assert link.token_hash != token

    fetched = write_links.get_link(people_dir, slug, link.id)
    assert fetched.label == "for the recital"


def test_create_link_rejects_unknown_person(people_dir):
    with pytest.raises(FileNotFoundError):
        write_links.create_link(people_dir, "nobody")


def test_create_link_blank_label_becomes_none(people_dir):
    slug = people.create_person(people_dir, "Papa")
    link, _ = write_links.create_link(people_dir, slug, label="   ")
    assert link.label is None


def test_create_link_with_expiry(people_dir):
    slug = people.create_person(people_dir, "Papa")
    link, _ = write_links.create_link(people_dir, slug, expires_in_days=7)
    assert link.expires_at is not None
    assert link.expires_at > datetime.now()


def test_list_links_newest_first(people_dir):
    slug = people.create_person(people_dir, "Papa")
    write_links.create_link(people_dir, slug, label="first")
    write_links.create_link(people_dir, slug, label="second")
    labels = [link.label for link in write_links.list_links(people_dir, slug)]
    assert labels == ["second", "first"]


def test_get_link_unknown_returns_none(people_dir):
    slug = people.create_person(people_dir, "Papa")
    assert write_links.get_link(people_dir, slug, "nope") is None


def test_find_by_token_matches_and_is_bounded_to_hash(people_dir):
    slug = people.create_person(people_dir, "Papa")
    link, token = write_links.create_link(people_dir, slug)

    found = write_links.find_by_token(people_dir, token)
    assert found.id == link.id
    assert write_links.find_by_token(people_dir, "wrong-token") is None
    assert write_links.find_by_token(people_dir, "") is None


def test_is_link_valid_true_for_fresh_link(people_dir):
    slug = people.create_person(people_dir, "Papa")
    link, _ = write_links.create_link(people_dir, slug)
    assert write_links.is_link_valid(link) is True


def test_is_link_valid_false_when_revoked(people_dir):
    slug = people.create_person(people_dir, "Papa")
    link, _ = write_links.create_link(people_dir, slug)
    write_links.revoke_link(people_dir, slug, link.id)
    revoked = write_links.get_link(people_dir, slug, link.id)
    assert write_links.is_link_valid(revoked) is False


def test_is_link_valid_false_when_expired(people_dir):
    slug = people.create_person(people_dir, "Papa")
    link, _ = write_links.create_link(people_dir, slug)
    link.expires_at = datetime.now() - timedelta(days=1)
    assert write_links.is_link_valid(link) is False


def test_is_link_valid_false_for_used_single_use_link(people_dir):
    slug = people.create_person(people_dir, "Papa")
    link, _ = write_links.create_link(people_dir, slug, single_use=True)
    write_links.mark_used(people_dir, slug, link.id, "some-story-id")
    used = write_links.get_link(people_dir, slug, link.id)
    assert write_links.is_link_valid(used) is False


def test_is_link_valid_true_for_used_multi_use_link(people_dir):
    slug = people.create_person(people_dir, "Papa")
    link, _ = write_links.create_link(people_dir, slug, single_use=False)
    write_links.mark_used(people_dir, slug, link.id, "some-story-id")
    used = write_links.get_link(people_dir, slug, link.id)
    assert write_links.is_link_valid(used) is True


def test_revoke_link_rejects_unknown_id(people_dir):
    slug = people.create_person(people_dir, "Papa")
    with pytest.raises(FileNotFoundError):
        write_links.revoke_link(people_dir, slug, "nope")


def test_mark_used_records_story_id(people_dir):
    slug = people.create_person(people_dir, "Papa")
    link, _ = write_links.create_link(people_dir, slug)
    write_links.mark_used(people_dir, slug, link.id, "2026-01-01-a-story")
    updated = write_links.get_link(people_dir, slug, link.id)
    assert updated.used_by_story_id == "2026-01-01-a-story"
    assert updated.used_at is not None


def test_list_all_active_excludes_revoked_expired_and_used(people_dir):
    papa = people.create_person(people_dir, "Papa")
    maman = people.create_person(people_dir, "Maman")

    active_link, _ = write_links.create_link(people_dir, papa, label="active one")
    revoked_link, _ = write_links.create_link(people_dir, papa, label="revoked one")
    write_links.revoke_link(people_dir, papa, revoked_link.id)
    used_link, _ = write_links.create_link(people_dir, maman, label="used one", single_use=True)
    write_links.mark_used(people_dir, maman, used_link.id, "some-story")

    active = write_links.list_all_active(people_dir)
    assert [link.id for link in active] == [active_link.id]


def test_list_all_active_empty_when_no_people(people_dir):
    assert write_links.list_all_active(people_dir) == []
