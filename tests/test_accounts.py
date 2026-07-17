"""Tests for FEATURES.md F19 Phase 1: account credentials layered on
people.py's Person model (app/accounts.py)."""

import pytest

from app import accounts, people


def test_is_valid_username():
    assert accounts.is_valid_username("papa")
    assert accounts.is_valid_username("maman-2")
    assert not accounts.is_valid_username("Papa")
    assert not accounts.is_valid_username("pa")
    assert not accounts.is_valid_username("a" * 33)
    assert not accounts.is_valid_username("papa smith")
    assert not accounts.is_valid_username("")


def test_create_account_round_trips(people_dir):
    slug = people.create_person(people_dir, "Papa")
    account = accounts.create_account(people_dir, slug, "papa", "hunter22", "admin")

    assert account.person_slug == slug
    assert account.username == "papa"
    assert account.role == "admin"
    assert account.status == "active"
    assert account.password_hash != "hunter22"

    fetched = accounts.get_account(people_dir, slug)
    assert fetched.username == "papa"
    assert fetched.role == "admin"


def test_create_account_lowercases_username(people_dir):
    slug = people.create_person(people_dir, "Papa")
    account = accounts.create_account(people_dir, slug, "PaPa", "hunter22", "family")
    assert account.username == "papa"


def test_create_account_rejects_bad_role(people_dir):
    slug = people.create_person(people_dir, "Papa")
    with pytest.raises(ValueError):
        accounts.create_account(people_dir, slug, "papa", "hunter22", "superuser")


def test_create_account_rejects_short_password(people_dir):
    slug = people.create_person(people_dir, "Papa")
    with pytest.raises(ValueError):
        accounts.create_account(people_dir, slug, "papa", "short", "family")


def test_create_account_rejects_bad_username(people_dir):
    slug = people.create_person(people_dir, "Papa")
    with pytest.raises(ValueError):
        accounts.create_account(people_dir, slug, "Not Valid", "hunter22", "family")


def test_create_account_rejects_unknown_person(people_dir):
    with pytest.raises(FileNotFoundError):
        accounts.create_account(people_dir, "nobody", "papa", "hunter22", "family")


def test_create_account_rejects_second_account_for_same_person(people_dir):
    slug = people.create_person(people_dir, "Papa")
    accounts.create_account(people_dir, slug, "papa", "hunter22", "family")
    with pytest.raises(ValueError):
        accounts.create_account(people_dir, slug, "papa2", "hunter22", "family")


def test_create_account_rejects_duplicate_username(people_dir):
    papa = people.create_person(people_dir, "Papa")
    maman = people.create_person(people_dir, "Maman")
    accounts.create_account(people_dir, papa, "shared", "hunter22", "family")
    with pytest.raises(ValueError):
        accounts.create_account(people_dir, maman, "shared", "hunter22", "family")


def test_list_accounts_and_any_accounts_exist(people_dir):
    assert accounts.list_accounts(people_dir) == []
    assert accounts.any_accounts_exist(people_dir) is False

    papa = people.create_person(people_dir, "Papa")
    people.create_person(people_dir, "Milo")  # no account
    accounts.create_account(people_dir, papa, "papa", "hunter22", "admin")

    all_accounts = accounts.list_accounts(people_dir)
    assert [a.username for a in all_accounts] == ["papa"]
    assert accounts.any_accounts_exist(people_dir) is True


def test_get_account_by_username_and_is_username_taken(people_dir):
    papa = people.create_person(people_dir, "Papa")
    accounts.create_account(people_dir, papa, "papa", "hunter22", "admin")

    assert accounts.get_account_by_username(people_dir, "papa").person_slug == papa
    assert accounts.get_account_by_username(people_dir, "PAPA").person_slug == papa
    assert accounts.get_account_by_username(people_dir, "nobody") is None
    assert accounts.is_username_taken(people_dir, "papa") is True
    assert accounts.is_username_taken(people_dir, "maman") is False


def test_set_status_disable_and_enable(people_dir):
    papa = people.create_person(people_dir, "Papa")
    accounts.create_account(people_dir, papa, "papa", "hunter22", "family")

    accounts.set_status(people_dir, papa, "disabled")
    assert accounts.get_account(people_dir, papa).status == "disabled"

    accounts.set_status(people_dir, papa, "active")
    assert accounts.get_account(people_dir, papa).status == "active"


def test_set_status_rejects_unknown_person(people_dir):
    with pytest.raises(FileNotFoundError):
        accounts.set_status(people_dir, "nobody", "disabled")


def test_verify_login_correct_credentials(people_dir):
    papa = people.create_person(people_dir, "Papa")
    accounts.create_account(people_dir, papa, "papa", "hunter22", "family")

    account = accounts.verify_login(people_dir, "papa", "hunter22")
    assert account is not None
    assert account.person_slug == papa


def test_verify_login_wrong_password(people_dir):
    papa = people.create_person(people_dir, "Papa")
    accounts.create_account(people_dir, papa, "papa", "hunter22", "family")
    assert accounts.verify_login(people_dir, "papa", "wrong-password") is None


def test_verify_login_unknown_username(people_dir):
    assert accounts.verify_login(people_dir, "nobody", "hunter22") is None


def test_verify_login_disabled_account(people_dir):
    papa = people.create_person(people_dir, "Papa")
    accounts.create_account(people_dir, papa, "papa", "hunter22", "family")
    accounts.set_status(people_dir, papa, "disabled")
    assert accounts.verify_login(people_dir, "papa", "hunter22") is None
