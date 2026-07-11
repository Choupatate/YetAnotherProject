import pytest

from app import create_app


def test_missing_secret_key_with_password_raises(monkeypatch, tmp_path):
    monkeypatch.setenv("STORYBOOK_PASSWORD", "prod-password")
    monkeypatch.delenv("STORYBOOK_SECRET_KEY", raising=False)
    monkeypatch.setenv("STORYBOOK_STORIES_DIR", str(tmp_path))

    with pytest.raises(RuntimeError, match="STORYBOOK_SECRET_KEY"):
        create_app()


def test_dev_mode_without_password_or_secret_does_not_raise(monkeypatch, tmp_path):
    monkeypatch.delenv("STORYBOOK_PASSWORD", raising=False)
    monkeypatch.delenv("STORYBOOK_SECRET_KEY", raising=False)
    monkeypatch.setenv("STORYBOOK_STORIES_DIR", str(tmp_path))

    app = create_app()
    assert app.config["DEV_MODE"] is True


def test_password_and_secret_key_both_set_does_not_raise(monkeypatch, tmp_path):
    monkeypatch.setenv("STORYBOOK_PASSWORD", "prod-password")
    monkeypatch.setenv("STORYBOOK_SECRET_KEY", "a-real-secret")
    monkeypatch.setenv("STORYBOOK_STORIES_DIR", str(tmp_path))

    app = create_app()
    assert app.config["PASSWORD"] == "prod-password"


def test_session_cookie_hardening_defaults(monkeypatch, tmp_path):
    monkeypatch.delenv("STORYBOOK_COOKIE_SECURE", raising=False)
    monkeypatch.setenv("STORYBOOK_STORIES_DIR", str(tmp_path))

    app = create_app()
    assert app.config["SESSION_COOKIE_HTTPONLY"] is True
    assert app.config["SESSION_COOKIE_SAMESITE"] == "Lax"
    assert app.config["SESSION_COOKIE_SECURE"] is False


def test_session_cookie_secure_env_var(monkeypatch, tmp_path):
    monkeypatch.setenv("STORYBOOK_COOKIE_SECURE", "1")
    monkeypatch.setenv("STORYBOOK_STORIES_DIR", str(tmp_path))

    app = create_app()
    assert app.config["SESSION_COOKIE_SECURE"] is True


def test_max_content_length_set(tmp_path, monkeypatch):
    monkeypatch.setenv("STORYBOOK_STORIES_DIR", str(tmp_path))
    app = create_app()
    assert app.config["MAX_CONTENT_LENGTH"] == 128 * 1024 * 1024
