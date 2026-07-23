"""Tests that CSRF protection (Flask-WTF's CSRFProtect, wired in
app/__init__.py) is actually active — every other test in the suite
disables it via BASE_TEST_CONFIG's WTF_CSRF_ENABLED=False (conftest.py)
so the other ~687 tests aren't about proving this; these are.
"""

import re

import pytest

from app import create_app


@pytest.fixture
def csrf_app(stories_dir):
    """The real default: CSRF left on, unlike every other fixture in the
    suite. Deliberately does not go through BASE_TEST_CONFIG."""
    return create_app(test_config={
        "TESTING": True,
        "STORIES_DIR": stories_dir,
        "PASSWORD": "test-password",
        "SECRET_KEY": "test-secret-key",
    })


@pytest.fixture
def csrf_client(csrf_app):
    return csrf_app.test_client()


def _extract_token(html):
    match = re.search(r'name="csrf_token" value="([^"]+)"', html)
    return match.group(1) if match else None


def _extract_meta_token(html):
    match = re.search(r'name="csrf-token" content="([^"]+)"', html)
    return match.group(1) if match else None


def test_login_page_renders_a_real_csrf_token(csrf_client):
    html = csrf_client.get("/login").data.decode()
    token = _extract_token(html)
    assert token is not None
    assert len(token) > 20  # a real signed token, not a placeholder/empty string


def test_get_requests_are_unaffected_by_csrf(csrf_client):
    """Safe methods are never checked — only POST/PUT/PATCH/DELETE."""
    resp = csrf_client.get("/login")
    assert resp.status_code == 200


def test_post_without_csrf_token_is_rejected(csrf_client):
    resp = csrf_client.post("/login", data={"password": "test-password"})
    assert resp.status_code == 400


def test_post_with_valid_csrf_token_succeeds(csrf_client):
    html = csrf_client.get("/login").data.decode()
    token = _extract_token(html)
    resp = csrf_client.post(
        "/login", data={"password": "test-password", "csrf_token": token}
    )
    assert resp.status_code == 302  # redirected to the timeline, login accepted


def test_post_with_wrong_csrf_token_is_rejected(csrf_client):
    csrf_client.get("/login")
    resp = csrf_client.post(
        "/login", data={"password": "test-password", "csrf_token": "not-a-real-token"}
    )
    assert resp.status_code == 400


def test_json_api_post_without_csrf_header_is_rejected(csrf_client):
    """The /api/* JSON routes are session-cookie-authenticated the same as
    every HTML page, so they need the same protection — checked via the
    X-CSRFToken header instead of a form field (see app/static/js/csrf.js)."""
    html = csrf_client.get("/login").data.decode()
    token = _extract_token(html)
    csrf_client.post("/login", data={"password": "test-password", "csrf_token": token})

    resp = csrf_client.post(
        "/api/stories",
        json={"title": "Title", "date": "2026-01-01", "markdown": ""},
    )
    assert resp.status_code == 400


def test_json_api_post_with_csrf_header_succeeds(csrf_client):
    html = csrf_client.get("/login").data.decode()
    token = _extract_token(html)
    csrf_client.post("/login", data={"password": "test-password", "csrf_token": token})

    # auth.py's login() calls session.clear() on success (anti session-fixation),
    # which invalidates the pre-login token above — fetch a fresh one post-login.
    home_html = csrf_client.get("/").data.decode()
    fresh_token = _extract_meta_token(home_html)

    resp = csrf_client.post(
        "/api/stories",
        json={"title": "Title", "date": "2026-01-01", "markdown": ""},
        headers={"X-CSRFToken": fresh_token},
    )
    assert resp.status_code == 200
