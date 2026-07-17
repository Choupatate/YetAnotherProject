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


def test_set_status_refuses_to_disable_the_only_admin(people_dir):
    papa = people.create_person(people_dir, "Papa")
    accounts.create_account(people_dir, papa, "papa", "hunter22", "admin")
    with pytest.raises(ValueError):
        accounts.set_status(people_dir, papa, "disabled")
    assert accounts.get_account(people_dir, papa).status == "active"


def test_set_status_allows_disabling_an_admin_when_another_remains(people_dir):
    papa = people.create_person(people_dir, "Papa")
    maman = people.create_person(people_dir, "Maman")
    accounts.create_account(people_dir, papa, "papa", "hunter22", "admin")
    accounts.create_account(people_dir, maman, "maman", "hunter22", "admin")
    accounts.set_status(people_dir, papa, "disabled")
    assert accounts.get_account(people_dir, papa).status == "disabled"


def test_set_status_allows_disabling_a_family_account_when_it_is_the_only_account(people_dir):
    papa = people.create_person(people_dir, "Papa")
    accounts.create_account(people_dir, papa, "papa", "hunter22", "family")
    accounts.set_status(people_dir, papa, "disabled")
    assert accounts.get_account(people_dir, papa).status == "disabled"


def test_set_role_promotes_and_demotes(people_dir):
    papa = people.create_person(people_dir, "Papa")
    maman = people.create_person(people_dir, "Maman")
    accounts.create_account(people_dir, papa, "papa", "hunter22", "admin")
    accounts.create_account(people_dir, maman, "maman", "hunter22", "family")

    accounts.set_role(people_dir, maman, "admin")
    assert accounts.get_account(people_dir, maman).role == "admin"

    accounts.set_role(people_dir, papa, "family")
    assert accounts.get_account(people_dir, papa).role == "family"


def test_set_role_refuses_to_demote_the_only_admin(people_dir):
    papa = people.create_person(people_dir, "Papa")
    accounts.create_account(people_dir, papa, "papa", "hunter22", "admin")
    with pytest.raises(ValueError):
        accounts.set_role(people_dir, papa, "family")
    assert accounts.get_account(people_dir, papa).role == "admin"


def test_set_role_ignores_a_disabled_admin_when_counting(people_dir):
    """A disabled admin doesn't count as 'remaining' — they can't do
    anything anyway, so demoting the last *active* admin must still be
    refused even if a disabled one also has the admin role."""
    papa = people.create_person(people_dir, "Papa")
    maman = people.create_person(people_dir, "Maman")
    accounts.create_account(people_dir, papa, "papa", "hunter22", "admin")
    accounts.create_account(people_dir, maman, "maman", "hunter22", "admin")
    accounts.set_status(people_dir, maman, "disabled")

    with pytest.raises(ValueError):
        accounts.set_role(people_dir, papa, "family")


def test_set_role_rejects_bad_role(people_dir):
    papa = people.create_person(people_dir, "Papa")
    accounts.create_account(people_dir, papa, "papa", "hunter22", "family")
    with pytest.raises(ValueError):
        accounts.set_role(people_dir, papa, "superuser")


def test_set_role_rejects_unknown_person(people_dir):
    with pytest.raises(FileNotFoundError):
        accounts.set_role(people_dir, "nobody", "admin")


def test_set_person_moves_account_json_and_leaves_old_person_unbound(people_dir):
    duplicate = people.create_person(people_dir, "Papa (new)")
    real = people.create_person(people_dir, "Papa")
    account = accounts.create_account(people_dir, duplicate, "papa", "hunter22", "admin")

    accounts.set_person(people_dir, duplicate, real)

    assert accounts.get_account(people_dir, duplicate) is None
    moved = accounts.get_account(people_dir, real)
    assert moved is not None
    assert moved.person_slug == real
    assert moved.username == account.username
    assert moved.role == account.role
    assert moved.password_hash == account.password_hash


def test_set_person_is_a_noop_for_the_same_slug(people_dir):
    papa = people.create_person(people_dir, "Papa")
    accounts.create_account(people_dir, papa, "papa", "hunter22", "admin")
    accounts.set_person(people_dir, papa, papa)
    assert accounts.get_account(people_dir, papa).username == "papa"


def test_set_person_rejects_a_target_that_already_has_an_account(people_dir):
    papa = people.create_person(people_dir, "Papa")
    maman = people.create_person(people_dir, "Maman")
    accounts.create_account(people_dir, papa, "papa", "hunter22", "admin")
    accounts.create_account(people_dir, maman, "maman", "hunter22", "family")

    with pytest.raises(ValueError):
        accounts.set_person(people_dir, papa, maman)
    assert accounts.get_account(people_dir, papa).username == "papa"
    assert accounts.get_account(people_dir, maman).username == "maman"


def test_set_person_rejects_unknown_slugs(people_dir):
    papa = people.create_person(people_dir, "Papa")
    accounts.create_account(people_dir, papa, "papa", "hunter22", "admin")

    with pytest.raises(FileNotFoundError):
        accounts.set_person(people_dir, papa, "nobody")
    with pytest.raises(FileNotFoundError):
        accounts.set_person(people_dir, "nobody", papa)


def test_set_password_changes_hash_and_bumps_session_version(people_dir):
    papa = people.create_person(people_dir, "Papa")
    account = accounts.create_account(people_dir, papa, "papa", "hunter22", "family")
    assert account.session_version == 0

    accounts.set_password(people_dir, papa, "new-password1")
    updated = accounts.get_account(people_dir, papa)
    assert updated.session_version == 1
    assert accounts.verify_login(people_dir, "papa", "new-password1") is not None
    assert accounts.verify_login(people_dir, "papa", "hunter22") is None


def test_set_password_rejects_short_password(people_dir):
    papa = people.create_person(people_dir, "Papa")
    accounts.create_account(people_dir, papa, "papa", "hunter22", "family")
    with pytest.raises(ValueError):
        accounts.set_password(people_dir, papa, "short")


def test_set_password_rejects_unknown_person(people_dir):
    with pytest.raises(FileNotFoundError):
        accounts.set_password(people_dir, "nobody", "new-password1")


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


# --- pending requests (FEATURES.md F19 Phase 2) -----------------------------


def test_create_pending_request_round_trips(stories_dir):
    pending = accounts.create_pending_request(stories_dir, "papa", "hunter22", "Papa", "note here")
    assert pending.username == "papa"
    assert pending.display_name == "Papa"
    assert pending.note == "note here"
    assert pending.password_hash != "hunter22"

    fetched = accounts.get_pending(stories_dir, "papa")
    assert fetched.username == "papa"
    assert fetched.display_name == "Papa"


def test_create_pending_request_lowercases_username_and_blank_note(stories_dir):
    pending = accounts.create_pending_request(stories_dir, "PaPa", "hunter22", "Papa", "  ")
    assert pending.username == "papa"
    assert pending.note is None


def test_create_pending_request_rejects_bad_username(stories_dir):
    with pytest.raises(ValueError):
        accounts.create_pending_request(stories_dir, "Not Valid", "hunter22", "Papa")


def test_create_pending_request_rejects_short_password(stories_dir):
    with pytest.raises(ValueError):
        accounts.create_pending_request(stories_dir, "papa", "short", "Papa")


def test_create_pending_request_rejects_blank_display_name(stories_dir):
    with pytest.raises(ValueError):
        accounts.create_pending_request(stories_dir, "papa", "hunter22", "  ")


def test_create_pending_request_rejects_username_taken_by_bound_account(stories_dir, people_dir):
    slug = people.create_person(people_dir, "Papa")
    accounts.create_account(people_dir, slug, "papa", "hunter22", "admin")
    with pytest.raises(ValueError):
        accounts.create_pending_request(stories_dir, "papa", "hunter22", "Someone Else")


def test_create_pending_request_rejects_username_already_pending(stories_dir):
    accounts.create_pending_request(stories_dir, "papa", "hunter22", "Papa")
    with pytest.raises(ValueError):
        accounts.create_pending_request(stories_dir, "papa", "hunter22", "Someone Else")


def test_list_pending_empty_and_ordered(stories_dir):
    assert accounts.list_pending(stories_dir) == []
    accounts.create_pending_request(stories_dir, "papa", "hunter22", "Papa")
    accounts.create_pending_request(stories_dir, "maman", "hunter22", "Maman")
    assert [p.username for p in accounts.list_pending(stories_dir)] == ["papa", "maman"]


def test_get_pending_unknown_returns_none(stories_dir):
    assert accounts.get_pending(stories_dir, "nobody") is None


def test_reject_pending_removes_it(stories_dir):
    accounts.create_pending_request(stories_dir, "papa", "hunter22", "Papa")
    accounts.reject_pending(stories_dir, "papa")
    assert accounts.get_pending(stories_dir, "papa") is None


def test_reject_pending_unknown_username_is_a_noop(stories_dir):
    accounts.reject_pending(stories_dir, "nobody")  # does not raise


def test_approve_pending_creates_new_person(stories_dir, people_dir):
    accounts.create_pending_request(stories_dir, "papa", "hunter22", "Papa")
    account = accounts.approve_pending(stories_dir, "papa", "admin", new_person_name="Papa")

    assert account.role == "admin"
    assert account.username == "papa"
    fetched = accounts.get_account(people_dir, account.person_slug)
    assert fetched.username == "papa"
    assert accounts.get_pending(stories_dir, "papa") is None


def test_approve_pending_binds_to_existing_person(stories_dir, people_dir):
    milo = people.create_person(people_dir, "Milo")
    accounts.create_pending_request(stories_dir, "milo", "hunter22", "Milo")
    account = accounts.approve_pending(stories_dir, "milo", "family", person_slug=milo)
    assert account.person_slug == milo


def test_approve_pending_rejects_unknown_username(stories_dir):
    with pytest.raises(FileNotFoundError):
        accounts.approve_pending(stories_dir, "nobody", "family", new_person_name="Someone")


def test_approve_pending_rejects_bad_role(stories_dir):
    accounts.create_pending_request(stories_dir, "papa", "hunter22", "Papa")
    with pytest.raises(ValueError):
        accounts.approve_pending(stories_dir, "papa", "superuser", new_person_name="Papa")


def test_approve_pending_rejects_both_person_args(stories_dir, people_dir):
    milo = people.create_person(people_dir, "Milo")
    accounts.create_pending_request(stories_dir, "milo", "hunter22", "Milo")
    with pytest.raises(ValueError):
        accounts.approve_pending(
            stories_dir, "milo", "family", person_slug=milo, new_person_name="Milo"
        )


def test_approve_pending_rejects_neither_person_arg(stories_dir):
    accounts.create_pending_request(stories_dir, "papa", "hunter22", "Papa")
    with pytest.raises(ValueError):
        accounts.approve_pending(stories_dir, "papa", "family")


def test_approve_pending_rejects_person_already_bound(stories_dir, people_dir):
    milo = people.create_person(people_dir, "Milo")
    accounts.create_account(people_dir, milo, "milo-existing", "hunter22", "family")
    accounts.create_pending_request(stories_dir, "milo", "hunter22", "Milo")
    with pytest.raises(ValueError):
        accounts.approve_pending(stories_dir, "milo", "family", person_slug=milo)


def test_is_username_reserved_across_pending_and_bound(stories_dir, people_dir):
    assert accounts.is_username_reserved(stories_dir, "papa") is False
    accounts.create_pending_request(stories_dir, "papa", "hunter22", "Papa")
    assert accounts.is_username_reserved(stories_dir, "papa") is True

    slug = people.create_person(people_dir, "Maman")
    accounts.create_account(people_dir, slug, "maman", "hunter22", "family")
    assert accounts.is_username_reserved(stories_dir, "maman") is True
