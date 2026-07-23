"""Tests for FEATURES.md F9: home-screen install (manifest, no service worker)."""

from app import create_app


def test_manifest_returns_valid_json_with_default_title(client):
    resp = client.get("/manifest.webmanifest")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["name"] == "Storybook"
    assert data["short_name"] == "Storybook"
    assert data["display"] == "standalone"
    assert data["start_url"] == "/"
    assert len(data["icons"]) == 2


def test_manifest_uses_configured_title(tmp_path, monkeypatch):
    monkeypatch.setenv("STORYBOOK_STORIES_DIR", str(tmp_path))
    monkeypatch.setenv("STORYBOOK_TITLE", "Le livre de Milo")
    app = create_app()
    client = app.test_client()

    resp = client.get("/manifest.webmanifest")
    data = resp.get_json()
    assert data["name"] == "Le livre de Milo"
    assert data["short_name"] == "Le livre de Milo"


def test_manifest_accessible_without_login(client):
    resp = client.get("/manifest.webmanifest")
    assert resp.status_code == 200


def test_head_contains_manifest_and_icon_links(auth_client):
    resp = auth_client.get("/")
    html = resp.data.decode()
    assert 'rel="manifest"' in html
    assert 'rel="apple-touch-icon"' in html
    assert html.count('name="theme-color"') == 2


def test_nav_brand_and_title_use_configured_app_title(tmp_path, monkeypatch):
    monkeypatch.setenv("STORYBOOK_STORIES_DIR", str(tmp_path))
    monkeypatch.setenv("STORYBOOK_TITLE", "Le livre de Milo")
    monkeypatch.setenv("STORYBOOK_PASSWORD", "test-password")
    monkeypatch.setenv("STORYBOOK_SECRET_KEY", "test-secret")
    app = create_app()
    app.config["WTF_CSRF_ENABLED"] = False
    client = app.test_client()
    client.post("/login", data={"password": "test-password"})

    resp = client.get("/")
    html = resp.data.decode()
    assert "Le livre de Milo" in html
    assert "<title>Le livre de Milo</title>" in html
