"""Tests for FEATURES.md F19 Phase 3: the HTTP surface of delegated
write-links — creating/revoking a link from an account, and the
/w/<token> -> /w/write delegate flow itself."""

import pytest

from app import storage, write_links
from tests.conftest import _bootstrap_admin, _login, _people_dir


@pytest.fixture
def accounts_app(app_factory):
    return app_factory(ACCOUNTS_ENABLED=True)


@pytest.fixture
def accounts_client(accounts_app):
    return accounts_app.test_client()


def _create_link(client, **extra):
    data = {"label": "for a story"}
    data.update(extra)
    return client.post("/account/write-links", data=data)


def _extract_token(url):
    return url.rsplit("/w/", 1)[1]


def _link_url(resp):
    """Pull the just-created share link's URL out of account_write_links.html."""
    html = resp.data.decode()
    start = html.index("http://") if "http://" in html else html.index("/w/")
    end = html.index("<", start)
    return html[start:end].strip()


# --- creating/listing/revoking links ----------------------------------------


def test_write_links_page_requires_login(accounts_client):
    resp = accounts_client.get("/account/write-links")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_write_links_page_404s_when_accounts_disabled(auth_client):
    # Logged in via the plain shared password (accounts mode off), so
    # login_required passes and the route's own ACCOUNTS_ENABLED guard is
    # what's actually being exercised here.
    assert auth_client.get("/account/write-links").status_code == 404


def test_create_link_shows_the_url_once(accounts_client, accounts_app):
    _bootstrap_admin(accounts_client)
    _login(accounts_client, "papa", "hunter22")

    resp = _create_link(accounts_client, label="for the recital")
    html = resp.data.decode()
    assert "/w/" in html
    assert "for the recital" in html

    slug = write_links.list_all_active(_people_dir(accounts_app))[0].person_slug
    links = write_links.list_links(_people_dir(accounts_app), slug)
    assert len(links) == 1
    assert links[0].label == "for the recital"


def test_create_link_defaults_to_single_use(accounts_client, accounts_app):
    _bootstrap_admin(accounts_client)
    _login(accounts_client, "papa", "hunter22")
    _create_link(accounts_client)  # single_use checkbox omitted -> unchecked

    links = write_links.list_all_active(_people_dir(accounts_app))
    assert links[0].single_use is False


def test_create_link_single_use_checkbox_checked(accounts_client, accounts_app):
    _bootstrap_admin(accounts_client)
    _login(accounts_client, "papa", "hunter22")
    _create_link(accounts_client, single_use="1")

    links = write_links.list_all_active(_people_dir(accounts_app))
    assert links[0].single_use is True


def test_owner_can_revoke_own_link(accounts_client, accounts_app):
    _bootstrap_admin(accounts_client)
    _login(accounts_client, "papa", "hunter22")
    _create_link(accounts_client)
    link = write_links.list_all_active(_people_dir(accounts_app))[0]

    resp = accounts_client.post(f"/account/write-links/{link.person_slug}/{link.id}/revoke")
    assert resp.status_code == 302
    assert write_links.list_all_active(_people_dir(accounts_app)) == []


def test_non_owner_family_account_cannot_revoke_someone_elses_link(accounts_client, accounts_app):
    _bootstrap_admin(accounts_client)
    _login(accounts_client, "papa", "hunter22")
    _create_link(accounts_client)
    link = write_links.list_all_active(_people_dir(accounts_app))[0]

    from app import people
    milo = people.create_person(_people_dir(accounts_app), "Milo")
    from app import accounts as accounts_module
    accounts_module.create_account(_people_dir(accounts_app), milo, "milo", "milosecret1", "family")

    other_client = accounts_app.test_client()
    _login(other_client, "milo", "milosecret1")
    resp = other_client.post(f"/account/write-links/{link.person_slug}/{link.id}/revoke")
    assert resp.status_code == 404
    assert len(write_links.list_all_active(_people_dir(accounts_app))) == 1


def test_admin_can_revoke_someone_elses_link(accounts_client, accounts_app):
    _bootstrap_admin(accounts_client)
    _login(accounts_client, "papa", "hunter22")

    from app import people
    milo = people.create_person(_people_dir(accounts_app), "Milo")
    from app import accounts as accounts_module
    accounts_module.create_account(_people_dir(accounts_app), milo, "milo", "milosecret1", "family")

    milo_client = accounts_app.test_client()
    _login(milo_client, "milo", "milosecret1")
    _create_link(milo_client)
    link = write_links.list_all_active(_people_dir(accounts_app))[0]

    resp = accounts_client.post(f"/account/write-links/{link.person_slug}/{link.id}/revoke")
    assert resp.status_code == 302
    assert write_links.list_all_active(_people_dir(accounts_app)) == []


# --- the delegate flow -------------------------------------------------------


def test_valid_link_opens_delegate_write_form(accounts_client, accounts_app):
    _bootstrap_admin(accounts_client)
    _login(accounts_client, "papa", "hunter22")
    resp = _create_link(accounts_client)
    token = _extract_token(_link_url(resp))

    delegate_client = accounts_app.test_client()
    resp = delegate_client.get(f"/w/{token}", follow_redirects=True)
    assert resp.status_code == 200
    assert b"Write for Papa" in resp.data


def test_invalid_token_shows_not_valid_page(accounts_client):
    _bootstrap_admin(accounts_client)
    resp = accounts_client.get("/w/not-a-real-token")
    assert resp.status_code == 404
    assert b"isn't valid anymore" in resp.data


def test_write_link_route_404s_when_accounts_disabled(client):
    assert client.get("/w/whatever").status_code == 404


def test_delegate_submits_a_story(accounts_client, accounts_app):
    _bootstrap_admin(accounts_client)
    _login(accounts_client, "papa", "hunter22")
    resp = _create_link(accounts_client, single_use="1")
    token = _extract_token(_link_url(resp))

    delegate_client = accounts_app.test_client()
    delegate_client.get(f"/w/{token}")
    resp = delegate_client.post(
        "/w/write", data={"title": "A memory", "date": "2026-01-01", "markdown": "Grandma told this."}
    )
    assert resp.status_code == 200
    assert b"has been added" in resp.data

    stories = storage.list_stories(accounts_app.config["STORIES_DIR"])
    assert len(stories) == 1
    assert stories[0].title == "A memory"
    assert stories[0].author == "Papa"


def test_single_use_link_cannot_be_used_twice(accounts_client, accounts_app):
    _bootstrap_admin(accounts_client)
    _login(accounts_client, "papa", "hunter22")
    resp = _create_link(accounts_client, single_use="1")
    token = _extract_token(_link_url(resp))

    delegate_client = accounts_app.test_client()
    delegate_client.get(f"/w/{token}")
    delegate_client.post(
        "/w/write", data={"title": "First", "date": "2026-01-01", "markdown": "..."}
    )
    # The same session, after single use, is locked out immediately.
    resp = delegate_client.get("/w/write")
    assert resp.status_code == 404
    # And the token itself is now dead too.
    resp = delegate_client.get(f"/w/{token}")
    assert resp.status_code == 404


def test_multi_use_link_can_submit_a_second_story(accounts_client, accounts_app):
    _bootstrap_admin(accounts_client)
    _login(accounts_client, "papa", "hunter22")
    resp = _create_link(accounts_client)  # single_use omitted -> multi-use
    token = _extract_token(_link_url(resp))

    delegate_client = accounts_app.test_client()
    delegate_client.get(f"/w/{token}")
    delegate_client.post(
        "/w/write", data={"title": "First", "date": "2026-01-01", "markdown": "..."}
    )
    resp = delegate_client.get("/w/write")
    assert resp.status_code == 200

    delegate_client.post(
        "/w/write", data={"title": "Second", "date": "2026-01-02", "markdown": "..."}
    )
    stories = storage.list_stories(accounts_app.config["STORIES_DIR"])
    assert len(stories) == 2


def test_revoked_link_locks_out_delegate_session_immediately(accounts_client, accounts_app):
    _bootstrap_admin(accounts_client)
    _login(accounts_client, "papa", "hunter22")
    resp = _create_link(accounts_client)
    token = _extract_token(_link_url(resp))
    link = write_links.list_all_active(_people_dir(accounts_app))[0]

    delegate_client = accounts_app.test_client()
    delegate_client.get(f"/w/{token}")
    assert delegate_client.get("/w/write").status_code == 200

    accounts_client.post(f"/account/write-links/{link.person_slug}/{link.id}/revoke")

    resp = delegate_client.get("/w/write")
    assert resp.status_code == 404


def test_delegate_session_cannot_reach_protected_routes(accounts_client, accounts_app):
    _bootstrap_admin(accounts_client)
    _login(accounts_client, "papa", "hunter22")
    resp = _create_link(accounts_client)
    token = _extract_token(_link_url(resp))

    delegate_client = accounts_app.test_client()
    delegate_client.get(f"/w/{token}")

    resp = delegate_client.get("/")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]
    assert delegate_client.get("/admin/accounts").status_code in (302, 404)


def test_opening_a_link_clears_an_existing_real_session(accounts_client, accounts_app):
    _bootstrap_admin(accounts_client)
    _login(accounts_client, "papa", "hunter22")
    assert accounts_client.get("/admin/accounts").status_code == 200

    resp = _create_link(accounts_client)
    token = _extract_token(_link_url(resp))

    accounts_client.get(f"/w/{token}")
    resp = accounts_client.get("/admin/accounts")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_delegate_write_missing_title_shows_error(accounts_client, accounts_app):
    _bootstrap_admin(accounts_client)
    _login(accounts_client, "papa", "hunter22")
    resp = _create_link(accounts_client)
    token = _extract_token(_link_url(resp))

    delegate_client = accounts_app.test_client()
    delegate_client.get(f"/w/{token}")
    resp = delegate_client.post(
        "/w/write", data={"title": "", "date": "2026-01-01", "markdown": "..."}
    )
    assert b"Enter a title" in resp.data
    assert storage.list_stories(accounts_app.config["STORIES_DIR"]) == []
