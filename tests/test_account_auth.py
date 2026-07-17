"""Tests for FEATURES.md F19 Phase 1: login/admin-route behavior when
STORYBOOK_ACCOUNTS is on (bootstrap, per-account login, admin-only routes,
immediate lockout on disable). With the flag off, behavior is untouched —
covered implicitly by the rest of the suite, which never sets it."""

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


def _bootstrap_admin(accounts_client, username="papa", password="hunter22"):
    """Log in with the shared password (first-ever account) and create the
    first admin account through the bootstrap flow, leaving the client
    logged in as that new account."""
    accounts_client.post("/login", data={"password": "test-password"})
    return accounts_client.post(
        "/admin/accounts/new",
        data={"new_person_name": "Papa", "username": username, "password": password},
    )


# --- default (flag off) --------------------------------------------------


def test_login_page_has_no_username_field_when_accounts_disabled(client):
    resp = client.get("/login")
    assert b'name="username"' not in resp.data
    assert b"No accounts yet" not in resp.data


# --- bootstrap -------------------------------------------------------------


def test_login_page_shows_bootstrap_note_when_accounts_enabled_and_none_exist(accounts_client):
    resp = accounts_client.get("/login")
    assert b"No accounts yet" in resp.data
    assert b'name="username"' not in resp.data


def test_bootstrap_password_redirects_to_new_account_page(accounts_client):
    resp = accounts_client.post("/login", data={"password": "test-password"})
    assert resp.status_code == 302
    assert "/admin/accounts/new" in resp.headers["Location"]


def test_bootstrap_creates_first_admin_bound_to_new_person(accounts_client, accounts_app):
    _bootstrap_admin(accounts_client)

    account = accounts.get_account_by_username(_people_dir(accounts_app), "papa")
    assert account is not None
    assert account.role == "admin"
    assert account.status == "active"

    # The bootstrap session was upgraded in place — already logged in as
    # the new account, no second login required.
    resp = accounts_client.get("/admin/accounts")
    assert resp.status_code == 200


def test_shared_password_stops_working_once_an_account_exists(accounts_client):
    _bootstrap_admin(accounts_client)
    accounts_client.post("/logout")

    resp = accounts_client.get("/login")
    assert b'name="username"' in resp.data

    resp = accounts_client.post("/login", data={"password": "test-password"})
    assert b"Incorrect username or password" in resp.data


# --- per-account login -----------------------------------------------------


def test_family_account_can_log_in_and_out(accounts_client, accounts_app):
    _bootstrap_admin(accounts_client)  # creates admin "papa", logs client in as papa
    accounts_client.post(
        "/admin/accounts/new",
        data={"new_person_name": "Maman", "username": "maman", "password": "hunter22", "role": "family"},
    )
    accounts_client.post("/logout")

    resp = accounts_client.post("/login", data={"username": "maman", "password": "hunter22"})
    assert resp.status_code == 302
    resp = accounts_client.get("/")
    assert resp.status_code == 200


def test_login_rejects_wrong_password(accounts_client):
    _bootstrap_admin(accounts_client)
    accounts_client.post("/logout")
    resp = accounts_client.post("/login", data={"username": "papa", "password": "wrong"})
    assert b"Incorrect username or password" in resp.data


# --- admin-only routes -------------------------------------------------------


def test_family_account_gets_404_on_admin_routes(accounts_client):
    _bootstrap_admin(accounts_client)
    accounts_client.post(
        "/admin/accounts/new",
        data={"new_person_name": "Maman", "username": "maman", "password": "hunter22", "role": "family"},
    )
    accounts_client.post("/logout")
    accounts_client.post("/login", data={"username": "maman", "password": "hunter22"})

    assert accounts_client.get("/admin/accounts").status_code == 404
    assert accounts_client.get("/admin/accounts/new").status_code == 404


def test_logged_out_visitor_redirected_to_login_on_admin_routes(accounts_client):
    resp = accounts_client.get("/admin/accounts")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_admin_accounts_page_lists_bound_accounts(accounts_client):
    _bootstrap_admin(accounts_client)
    resp = accounts_client.get("/admin/accounts")
    html = resp.data.decode()
    assert "papa" in html
    assert "admin" in html


def test_admin_can_bind_account_to_existing_unbound_person(accounts_client, accounts_app):
    _bootstrap_admin(accounts_client)
    from app import people

    milo = people.create_person(_people_dir(accounts_app), "Milo")

    resp = accounts_client.post(
        "/admin/accounts/new",
        data={"person_slug": milo, "username": "milo", "password": "hunter22", "role": "family"},
    )
    assert resp.status_code == 302
    account = accounts.get_account(_people_dir(accounts_app), milo)
    assert account is not None
    assert account.username == "milo"


def test_admin_new_account_rejects_duplicate_username(accounts_client):
    _bootstrap_admin(accounts_client)
    resp = accounts_client.post(
        "/admin/accounts/new",
        data={"new_person_name": "Maman", "username": "papa", "password": "hunter22", "role": "family"},
    )
    assert resp.status_code == 200
    assert b"already taken" in resp.data


def test_admin_new_account_rejects_no_person_selected(accounts_client):
    _bootstrap_admin(accounts_client)
    resp = accounts_client.post(
        "/admin/accounts/new",
        data={"username": "someone", "password": "hunter22", "role": "family"},
    )
    assert resp.status_code == 200
    assert b"Pick an existing family member" in resp.data


# --- disable takes effect immediately --------------------------------------


def test_disabling_account_locks_out_an_active_session_immediately(accounts_app):
    admin_client = accounts_app.test_client()
    _bootstrap_admin(admin_client)
    admin_client.post(
        "/admin/accounts/new",
        data={"new_person_name": "Maman", "username": "maman", "password": "hunter22", "role": "family"},
    )

    family_client = accounts_app.test_client()
    family_client.post("/login", data={"username": "maman", "password": "hunter22"})
    assert family_client.get("/").status_code == 200

    slug = _slug_for(accounts_app, "maman")
    admin_client.post(f"/admin/accounts/{slug}/disable")

    resp = family_client.get("/")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def _slug_for(accounts_app, username):
    people_dir = _people_dir(accounts_app)
    return accounts.get_account_by_username(people_dir, username).person_slug


def test_admin_disable_and_enable_routes(accounts_client, accounts_app):
    _bootstrap_admin(accounts_client)
    accounts_client.post(
        "/admin/accounts/new",
        data={"new_person_name": "Maman", "username": "maman", "password": "hunter22", "role": "family"},
    )
    slug = _slug_for(accounts_app, "maman")

    resp = accounts_client.post(f"/admin/accounts/{slug}/disable")
    assert resp.status_code == 302
    assert accounts.get_account(_people_dir(accounts_app), slug).status == "disabled"

    resp = accounts_client.post(f"/admin/accounts/{slug}/enable")
    assert resp.status_code == 302
    assert accounts.get_account(_people_dir(accounts_app), slug).status == "active"
