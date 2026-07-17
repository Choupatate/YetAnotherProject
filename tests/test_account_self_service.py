"""Tests for FEATURES.md F19 Phase 4 follow-up: self-service password
change, admin password reset, and admin role promotion/demotion — the two
gaps identified after Phase 4 ("everything's web-accessible, no need to
touch account.json by hand") that this round closes."""

import pytest

from app import accounts


@pytest.fixture
def accounts_app(app_factory):
    return app_factory(ACCOUNTS_ENABLED=True)


@pytest.fixture
def accounts_client(accounts_app):
    return accounts_app.test_client()


def _people_dir(accounts_app):
    return accounts_app.config["STORIES_DIR"] / "people"


def _bootstrap_admin(client, username="papa", password="hunter22"):
    return client.post(
        "/request-account",
        data={
            "display_name": "Papa", "username": username, "password": password,
            "invite_code": "test-password", "note": "",
        },
    )


def _login(client, username, password):
    return client.post("/login", data={"username": username, "password": password})


def _create_family_account(accounts_app, username, password, name="Maman"):
    from app import people as people_module

    slug = people_module.create_person(_people_dir(accounts_app), name)
    accounts.create_account(_people_dir(accounts_app), slug, username, password, "family")
    return slug


# --- /account hub ------------------------------------------------------------


def test_account_home_requires_login(accounts_client):
    resp = accounts_client.get("/account")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_account_home_404s_when_accounts_disabled(auth_client):
    assert auth_client.get("/account").status_code == 404


def test_account_home_links_to_password_and_write_links(accounts_client):
    _bootstrap_admin(accounts_client)
    _login(accounts_client, "papa", "hunter22")
    resp = accounts_client.get("/account")
    html = resp.data.decode()
    assert "/account/password" in html
    assert "/account/write-links" in html


# --- self-service password change --------------------------------------------


def test_change_password_requires_current_password(accounts_client):
    _bootstrap_admin(accounts_client)
    _login(accounts_client, "papa", "hunter22")
    resp = accounts_client.post(
        "/account/password",
        data={"current_password": "wrong", "new_password": "new-password1", "confirm_password": "new-password1"},
    )
    assert b"Current password is incorrect" in resp.data


def test_change_password_requires_matching_confirmation(accounts_client):
    _bootstrap_admin(accounts_client)
    _login(accounts_client, "papa", "hunter22")
    resp = accounts_client.post(
        "/account/password",
        data={"current_password": "hunter22", "new_password": "new-password1", "confirm_password": "different1"},
    )
    assert b"don&#39;t match" in resp.data


def test_change_password_succeeds_and_new_password_works(accounts_client, accounts_app):
    _bootstrap_admin(accounts_client)
    _login(accounts_client, "papa", "hunter22")
    resp = accounts_client.post(
        "/account/password",
        data={"current_password": "hunter22", "new_password": "new-password1", "confirm_password": "new-password1"},
    )
    assert b"has been changed" in resp.data
    assert accounts.verify_login(_people_dir(accounts_app), "papa", "new-password1") is not None


def test_change_password_keeps_the_current_session_logged_in(accounts_client):
    _bootstrap_admin(accounts_client)
    _login(accounts_client, "papa", "hunter22")
    accounts_client.post(
        "/account/password",
        data={"current_password": "hunter22", "new_password": "new-password1", "confirm_password": "new-password1"},
    )
    # The session that made the change is still valid immediately after.
    resp = accounts_client.get("/account")
    assert resp.status_code == 200


def test_change_password_logs_out_other_open_sessions(accounts_app):
    client_a = accounts_app.test_client()
    client_b = accounts_app.test_client()
    _bootstrap_admin(client_a)
    _login(client_a, "papa", "hunter22")
    _login(client_b, "papa", "hunter22")
    assert client_b.get("/").status_code == 200

    client_a.post(
        "/account/password",
        data={"current_password": "hunter22", "new_password": "new-password1", "confirm_password": "new-password1"},
    )

    resp = client_b.get("/")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


# --- admin password reset -----------------------------------------------------


def test_admin_can_reset_someones_password_without_knowing_it(accounts_client, accounts_app):
    _bootstrap_admin(accounts_client)
    _login(accounts_client, "papa", "hunter22")
    slug = _create_family_account(accounts_app, "maman", "hunter22")

    resp = accounts_client.post(
        f"/admin/accounts/{slug}/reset-password",
        data={"new_password": "new-password1", "confirm_password": "new-password1"},
    )
    assert resp.status_code == 302
    assert accounts.verify_login(_people_dir(accounts_app), "maman", "new-password1") is not None
    assert accounts.verify_login(_people_dir(accounts_app), "maman", "hunter22") is None


def test_admin_reset_password_rejects_mismatched_confirmation(accounts_client, accounts_app):
    _bootstrap_admin(accounts_client)
    _login(accounts_client, "papa", "hunter22")
    slug = _create_family_account(accounts_app, "maman", "hunter22")

    resp = accounts_client.post(
        f"/admin/accounts/{slug}/reset-password",
        data={"new_password": "new-password1", "confirm_password": "different1"},
    )
    assert b"don&#39;t match" in resp.data
    assert accounts.verify_login(_people_dir(accounts_app), "maman", "hunter22") is not None


def test_admin_reset_password_invalidates_that_accounts_open_sessions(accounts_app):
    admin_client = accounts_app.test_client()
    _bootstrap_admin(admin_client)
    _login(admin_client, "papa", "hunter22")
    slug = _create_family_account(accounts_app, "maman", "hunter22")

    maman_client = accounts_app.test_client()
    _login(maman_client, "maman", "hunter22")
    assert maman_client.get("/").status_code == 200

    admin_client.post(
        f"/admin/accounts/{slug}/reset-password",
        data={"new_password": "new-password1", "confirm_password": "new-password1"},
    )
    resp = maman_client.get("/")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_non_admin_gets_404_resetting_someones_password(accounts_client, accounts_app):
    _bootstrap_admin(accounts_client)
    slug = _create_family_account(accounts_app, "maman", "hunter22")
    _login(accounts_client, "maman", "hunter22")
    resp = accounts_client.get(f"/admin/accounts/{slug}/reset-password")
    assert resp.status_code == 404


def test_reset_password_unknown_person_404s(accounts_client):
    _bootstrap_admin(accounts_client)
    _login(accounts_client, "papa", "hunter22")
    resp = accounts_client.get("/admin/accounts/nobody/reset-password")
    assert resp.status_code == 404


# --- admin role change ---------------------------------------------------------


def test_admin_can_promote_a_family_account_to_admin(accounts_client, accounts_app):
    _bootstrap_admin(accounts_client)
    _login(accounts_client, "papa", "hunter22")
    slug = _create_family_account(accounts_app, "maman", "hunter22")

    resp = accounts_client.post(f"/admin/accounts/{slug}/role", data={"role": "admin"})
    assert resp.status_code == 302
    assert accounts.get_account(_people_dir(accounts_app), slug).role == "admin"


def test_admin_can_demote_an_admin_when_another_remains(accounts_client, accounts_app):
    _bootstrap_admin(accounts_client)
    _login(accounts_client, "papa", "hunter22")
    slug = _create_family_account(accounts_app, "maman", "hunter22")
    accounts.set_role(_people_dir(accounts_app), slug, "admin")

    papa_slug = accounts.get_account_by_username(_people_dir(accounts_app), "papa").person_slug
    resp = accounts_client.post(f"/admin/accounts/{papa_slug}/role", data={"role": "family"})
    assert resp.status_code == 302
    assert accounts.get_account(_people_dir(accounts_app), papa_slug).role == "family"


def test_demoting_the_only_admin_fails_gracefully_not_a_500(accounts_client, accounts_app):
    _bootstrap_admin(accounts_client)
    _login(accounts_client, "papa", "hunter22")
    papa_slug = accounts.get_account_by_username(_people_dir(accounts_app), "papa").person_slug

    resp = accounts_client.post(f"/admin/accounts/{papa_slug}/role", data={"role": "family"})
    assert resp.status_code == 302
    assert accounts.get_account(_people_dir(accounts_app), papa_slug).role == "admin"
    # The error surfaces on the accounts page rather than a 500.
    resp = accounts_client.get("/admin/accounts", follow_redirects=True)
    assert b"only remaining admin" in resp.data


def test_disabling_the_only_admin_fails_gracefully_not_a_500(accounts_client, accounts_app):
    _bootstrap_admin(accounts_client)
    _login(accounts_client, "papa", "hunter22")
    papa_slug = accounts.get_account_by_username(_people_dir(accounts_app), "papa").person_slug

    resp = accounts_client.post(f"/admin/accounts/{papa_slug}/disable")
    assert resp.status_code == 302
    assert accounts.get_account(_people_dir(accounts_app), papa_slug).status == "active"
    resp = accounts_client.get("/admin/accounts", follow_redirects=True)
    assert b"only remaining admin" in resp.data


def test_non_admin_gets_404_changing_role(accounts_client, accounts_app):
    _bootstrap_admin(accounts_client)
    slug = _create_family_account(accounts_app, "maman", "hunter22")
    _login(accounts_client, "maman", "hunter22")
    resp = accounts_client.post(f"/admin/accounts/{slug}/role", data={"role": "admin"})
    assert resp.status_code == 404


def test_role_change_rejects_invalid_role(accounts_client, accounts_app):
    _bootstrap_admin(accounts_client)
    _login(accounts_client, "papa", "hunter22")
    slug = _create_family_account(accounts_app, "maman", "hunter22")

    resp = accounts_client.post(f"/admin/accounts/{slug}/role", data={"role": "superuser"})
    assert resp.status_code == 302
    assert accounts.get_account(_people_dir(accounts_app), slug).role == "family"
