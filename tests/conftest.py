import pytest

from app import create_app


@pytest.fixture
def stories_dir(tmp_path):
    d = tmp_path / "stories"
    d.mkdir()
    return d


@pytest.fixture
def app(stories_dir):
    application = create_app(
        test_config={
            "STORIES_DIR": stories_dir,
            "TESTING": True,
            "PASSWORD": "test-password",
            "SECRET_KEY": "test-secret-key",
        }
    )
    return application


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def auth_client(client):
    client.post("/login", data={"password": "test-password"})
    return client
