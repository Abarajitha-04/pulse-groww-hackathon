"""
End-to-end tests through the real HTTP layer (FastAPI TestClient) rather
than calling service functions directly — this is what catches bugs the
unit tests structurally can't: a wrong status code, a missing field in a
response model, a dependency wired up incorrectly, or (as found and fixed
during this hardening pass, see docs/DECISIONS.md) the refresh-token
reuse-detection cascade not actually revoking every session.
"""


def _signup(client, email="user@example.com", password="hunter22"):
    return client.post("/auth/signup", json={"email": email, "password": password})


def test_signup_returns_access_and_refresh_tokens(api_client):
    resp = _signup(api_client)
    assert resp.status_code == 201
    body = resp.json()
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["token_type"] == "bearer"


def test_duplicate_signup_is_rejected(api_client):
    _signup(api_client)
    resp = _signup(api_client)
    assert resp.status_code == 400


def test_login_with_wrong_password_is_rejected(api_client):
    _signup(api_client)
    resp = api_client.post("/auth/login", json={"email": "user@example.com", "password": "wrong"})
    assert resp.status_code == 401


def test_login_for_nonexistent_user_gives_same_error_as_wrong_password(api_client):
    """Account-enumeration guard: both cases must be indistinguishable."""
    resp = api_client.post("/auth/login", json={"email": "ghost@example.com", "password": "x"})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Incorrect email or password"


def test_authed_endpoint_rejects_missing_token(api_client):
    resp = api_client.get("/users/me")
    assert resp.status_code == 401


def test_authed_endpoint_works_with_valid_access_token(api_client):
    tokens = _signup(api_client).json()
    resp = api_client.get("/users/me", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert resp.status_code == 200
    assert resp.json()["email"] == "user@example.com"


def test_refresh_rotates_token_and_old_one_stops_working(api_client):
    tokens = _signup(api_client).json()

    refreshed = api_client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert refreshed.status_code == 200
    new_tokens = refreshed.json()
    assert new_tokens["refresh_token"] != tokens["refresh_token"]

    # The old refresh token must no longer work at all.
    reused = api_client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert reused.status_code == 401


def test_refresh_token_reuse_revokes_the_new_token_too(api_client):
    """The theft-detection cascade: presenting an already-rotated-away
    refresh token must revoke every session for that user, including the
    one that superseded it — otherwise a stolen-then-used-by-attacker
    scenario leaves the legitimate user's new session still valid, which
    defeats the point of detecting the reuse at all."""
    tokens = _signup(api_client).json()
    refreshed = api_client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]}).json()

    # Reusing the original (now-revoked) token trips the reuse detector.
    reuse_resp = api_client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert reuse_resp.status_code == 401
    assert "reuse" in reuse_resp.json()["detail"].lower()

    # The token issued by the legitimate refresh must ALSO now be dead.
    resp = api_client.post("/auth/refresh", json={"refresh_token": refreshed["refresh_token"]})
    assert resp.status_code == 401


def test_logout_revokes_the_refresh_token(api_client):
    tokens = _signup(api_client).json()
    logout_resp = api_client.post("/auth/logout", json={"refresh_token": tokens["refresh_token"]})
    assert logout_resp.status_code == 200

    resp = api_client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert resp.status_code == 401


def test_password_reset_flow_and_old_sessions_are_revoked(api_client, monkeypatch):
    tokens = _signup(api_client).json()

    captured = {}

    def fake_send(email, raw_token):
        captured["token"] = raw_token

    monkeypatch.setattr("app.api.auth.send_password_reset_email", fake_send)

    resp = api_client.post("/auth/request-password-reset", json={"email": "user@example.com"})
    assert resp.status_code == 200
    assert "token" in captured

    reset_resp = api_client.post(
        "/auth/reset-password", json={"token": captured["token"], "new_password": "newpassword123"}
    )
    assert reset_resp.status_code == 200

    # Old refresh token must be dead after a password reset.
    old_session_resp = api_client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert old_session_resp.status_code == 401

    # New password works, old one doesn't.
    assert api_client.post("/auth/login", json={"email": "user@example.com", "password": "hunter22"}).status_code == 401
    assert (
        api_client.post("/auth/login", json={"email": "user@example.com", "password": "newpassword123"}).status_code
        == 200
    )


def test_password_reset_request_gives_same_response_for_unknown_email(api_client):
    """Must not leak whether an email is registered."""
    resp = api_client.post("/auth/request-password-reset", json={"email": "nobody@example.com"})
    assert resp.status_code == 200
    assert "sent" in resp.json()["message"].lower()


def test_security_headers_are_present(api_client):
    resp = api_client.get("/health")
    assert resp.headers["x-content-type-options"] == "nosniff"
    assert resp.headers["x-frame-options"] == "DENY"


def test_request_id_is_echoed_back(api_client):
    resp = api_client.get("/health", headers={"X-Request-ID": "trace-abc-123"})
    assert resp.headers["x-request-id"] == "trace-abc-123"
