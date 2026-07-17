"""Tests for FEATURES.md F19 Phase 1+2: login/admin-route behavior when
STORYBOOK_ACCOUNTS is on (the request/approve queue, per-account login,
admin-only routes, immediate lockout on disable). With the flag off,
behavior is untouched — covered implicitly by the rest of the suite,
which never sets it."""

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


def _request_account(client, username="papa", password="hunter22", display_name="Papa",
                      invite_code="test-password", note=""):
    return client.post(
        "/request-account",
        data={
            "display_name": display_name, "username": username, "password": password,
            "invite_code": invite_code, "note": note,
        },
    )


def _bootstrap_admin(client, username="papa", password="hunter22"):
    """Submit the very first request, which auto-approves as admin, leaving
    the client logged out (the request flow never logs anyone in) — caller
    logs in afterward if needed."""
    return _request_account(client, username=username, password=password, display_name="Papa")


def _login(client, username, password):
    return client.post("/login", data={"username": username, "password": password})


def _slug_for(accounts_app, username):
    people_dir = _people_dir(accounts_app)
    return accounts.get_account_by_username(people_dir, username).person_slug


# --- default (flag off) --------------------------------------------------


def test_login_page_has_no_username_field_when_accounts_disabled(client):
    resp = client.get("/login")
    assert b'name="username"' not in resp.data


def test_request_account_404s_when_accounts_disabled(client):
    assert client.get("/request-account").status_code == 404


# --- request/approve flow ---------------------------------------------------


def test_login_page_shows_request_link_when_accounts_enabled(accounts_client):
    resp = accounts_client.get("/login")
    assert b"request the first one" in resp.data
    assert b'name="username"' in resp.data


def test_first_request_auto_approves_as_admin(accounts_client, accounts_app):
    resp = _bootstrap_admin(accounts_client)
    assert resp.status_code == 200
    assert b"created as admin" in resp.data

    account = accounts.get_account_by_username(_people_dir(accounts_app), "papa")
    assert account is not None
    assert account.role == "admin"
    assert account.status == "active"
    assert accounts.list_pending(accounts_app.config["STORIES_DIR"]) == []


def test_first_request_creates_a_person_from_display_name(accounts_client, accounts_app):
    _bootstrap_admin(accounts_client)
    from app import people

    names = [p.name for p in people.list_people(_people_dir(accounts_app))]
    assert "Papa" in names


def test_second_request_goes_to_pending_queue_not_auto_approved(accounts_client, accounts_app):
    _bootstrap_admin(accounts_client)
    resp = _request_account(accounts_client, username="maman", display_name="Maman", password="mamansecret1")
    assert resp.status_code == 200
    assert b"admin will review" in resp.data

    pending = accounts.list_pending(accounts_app.config["STORIES_DIR"])
    assert [p.username for p in pending] == ["maman"]
    assert accounts.get_account_by_username(_people_dir(accounts_app), "maman") is None


def test_request_account_rejects_wrong_invite_code(accounts_client, accounts_app):
    resp = _request_account(accounts_client, invite_code="wrong-code")
    assert b"Incorrect invite code" in resp.data
    assert accounts.list_pending(accounts_app.config["STORIES_DIR"]) == []


def test_request_account_rejects_short_password(accounts_client):
    resp = _request_account(accounts_client, password="short")
    assert b"least 8 characters" in resp.data


def test_request_account_rejects_duplicate_username_across_pending(accounts_client):
    _bootstrap_admin(accounts_client)
    resp = _request_account(accounts_client, username="papa", display_name="Someone Else")
    assert b"already taken" in resp.data


def test_admin_approves_pending_request_binding_to_new_person(accounts_client, accounts_app):
    _bootstrap_admin(accounts_client)
    _request_account(accounts_client, username="maman", display_name="Maman", password="mamansecret1")
    _login(accounts_client, "papa", "hunter22")

    resp = accounts_client.post(
        "/admin/accounts/pending/maman",
        data={"new_person_name": "Maman", "role": "family"},
    )
    assert resp.status_code == 302

    account = accounts.get_account_by_username(_people_dir(accounts_app), "maman")
    assert account is not None
    assert account.role == "family"
    assert accounts.list_pending(accounts_app.config["STORIES_DIR"]) == []


def test_admin_approves_pending_request_binding_to_existing_person(accounts_client, accounts_app):
    _bootstrap_admin(accounts_client)
    from app import people

    milo = people.create_person(_people_dir(accounts_app), "Milo")
    _request_account(accounts_client, username="milo", display_name="Milo", password="milosecret1")
    _login(accounts_client, "papa", "hunter22")

    resp = accounts_client.post(
        "/admin/accounts/pending/milo",
        data={"person_slug": milo, "role": "family"},
    )
    assert resp.status_code == 302
    account = accounts.get_account(_people_dir(accounts_app), milo)
    assert account is not None
    assert account.username == "milo"


def test_admin_rejects_pending_request(accounts_client, accounts_app):
    _bootstrap_admin(accounts_client)
    _request_account(accounts_client, username="maman", display_name="Maman", password="mamansecret1")
    _login(accounts_client, "papa", "hunter22")

    resp = accounts_client.post("/admin/accounts/pending/maman/reject")
    assert resp.status_code == 302
    assert accounts.list_pending(accounts_app.config["STORIES_DIR"]) == []
    assert accounts.get_account_by_username(_people_dir(accounts_app), "maman") is None


def test_non_admin_gets_404_reviewing_pending(accounts_client, accounts_app):
    _bootstrap_admin(accounts_client)
    _request_account(accounts_client, username="maman", display_name="Maman", password="mamansecret1")
    from app import people

    milo = people.create_person(_people_dir(accounts_app), "Milo")
    accounts.create_account(_people_dir(accounts_app), milo, "milo", "milosecret1", "family")

    _login(accounts_client, "milo", "milosecret1")
    assert accounts_client.get("/admin/accounts/pending/maman").status_code == 404
    assert accounts_client.post("/admin/accounts/pending/maman/reject").status_code == 404


def test_review_unknown_pending_username_404s(accounts_client):
    _bootstrap_admin(accounts_client)
    _login(accounts_client, "papa", "hunter22")
    assert accounts_client.get("/admin/accounts/pending/nobody").status_code == 404


# --- shared password no longer logs anyone in --------------------------------


def test_shared_password_never_logs_in_when_accounts_enabled(accounts_client):
    resp = accounts_client.post("/login", data={"password": "test-password"})
    assert b"Incorrect username or password" in resp.data


def test_shared_password_never_logs_in_after_accounts_exist(accounts_client):
    _bootstrap_admin(accounts_client)
    resp = accounts_client.post("/login", data={"password": "test-password"})
    assert b"Incorrect username or password" in resp.data


# --- per-account login -----------------------------------------------------


def test_family_account_can_log_in_and_out(accounts_client):
    _bootstrap_admin(accounts_client)
    _request_account(accounts_client, username="maman", display_name="Maman", password="mamansecret1")
    _login(accounts_client, "papa", "hunter22")
    accounts_client.post(
        "/admin/accounts/pending/maman", data={"new_person_name": "Maman", "role": "family"}
    )
    accounts_client.post("/logout")

    resp = _login(accounts_client, "maman", "mamansecret1")
    assert resp.status_code == 302
    resp = accounts_client.get("/")
    assert resp.status_code == 200


def test_login_rejects_wrong_password(accounts_client):
    _bootstrap_admin(accounts_client)
    accounts_client.post("/logout")
    resp = _login(accounts_client, "papa", "wrong")
    assert b"Incorrect username or password" in resp.data


# --- admin-only routes -------------------------------------------------------


def test_family_account_gets_404_on_admin_routes(accounts_client, accounts_app):
    _bootstrap_admin(accounts_client)
    from app import people

    milo = people.create_person(_people_dir(accounts_app), "Milo")
    accounts.create_account(_people_dir(accounts_app), milo, "milo", "milosecret1", "family")
    _login(accounts_client, "milo", "milosecret1")

    assert accounts_client.get("/admin/accounts").status_code == 404
    assert accounts_client.get("/admin/accounts/new").status_code == 404


def test_logged_out_visitor_redirected_to_login_on_admin_routes(accounts_client):
    resp = accounts_client.get("/admin/accounts")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_admin_accounts_page_lists_bound_accounts(accounts_client):
    _bootstrap_admin(accounts_client)
    _login(accounts_client, "papa", "hunter22")
    resp = accounts_client.get("/admin/accounts")
    html = resp.data.decode()
    assert "papa" in html
    assert "admin" in html


def test_admin_can_bind_account_to_existing_unbound_person(accounts_client, accounts_app):
    _bootstrap_admin(accounts_client)
    _login(accounts_client, "papa", "hunter22")
    from app import people

    milo = people.create_person(_people_dir(accounts_app), "Milo")
    resp = accounts_client.post(
        "/admin/accounts/new",
        data={"person_slug": milo, "username": "milo", "password": "milosecret1", "role": "family"},
    )
    assert resp.status_code == 302
    account = accounts.get_account(_people_dir(accounts_app), milo)
    assert account is not None
    assert account.username == "milo"


def test_admin_new_account_rejects_duplicate_username(accounts_client):
    _bootstrap_admin(accounts_client)
    _login(accounts_client, "papa", "hunter22")
    resp = accounts_client.post(
        "/admin/accounts/new",
        data={"new_person_name": "Maman", "username": "papa", "password": "hunter22", "role": "family"},
    )
    assert resp.status_code == 200
    assert b"already taken" in resp.data


def test_admin_new_account_rejects_no_person_selected(accounts_client):
    _bootstrap_admin(accounts_client)
    _login(accounts_client, "papa", "hunter22")
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
    _login(admin_client, "papa", "hunter22")
    admin_client.post(
        "/admin/accounts/new",
        data={"new_person_name": "Maman", "username": "maman", "password": "hunter22", "role": "family"},
    )

    family_client = accounts_app.test_client()
    _login(family_client, "maman", "hunter22")
    assert family_client.get("/").status_code == 200

    slug = _slug_for(accounts_app, "maman")
    admin_client.post(f"/admin/accounts/{slug}/disable")

    resp = family_client.get("/")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_admin_disable_and_enable_routes(accounts_client, accounts_app):
    _bootstrap_admin(accounts_client)
    _login(accounts_client, "papa", "hunter22")
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
