def test_index_redirects_to_login_when_unauthenticated(client):
    resp = client.get("/")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_correct_password_logs_in_and_redirects_to_timeline(client):
    resp = client.post("/login", data={"password": "test-password"})
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/")

    resp = client.get("/")
    assert resp.status_code == 200


def test_wrong_password_shows_error_and_stays_logged_out(client):
    resp = client.post("/login", data={"password": "nope"}, follow_redirects=True)
    assert resp.status_code == 200
    assert b"Incorrect password" in resp.data

    resp = client.get("/")
    assert resp.status_code == 302


def test_login_redirect_preserves_next_param(client):
    resp = client.get("/story/2026-01-01-something")
    assert resp.status_code == 302
    assert "next=" in resp.headers["Location"]


def test_logout_clears_session(auth_client):
    resp = auth_client.get("/")
    assert resp.status_code == 200

    auth_client.post("/logout")
    resp = auth_client.get("/")
    assert resp.status_code == 302
