def _signup_and_auth_headers(client, email="wl-user@example.com"):
    resp = client.post("/auth/signup", json={"email": email, "password": "hunter22"})
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_create_and_list_watchlists(api_client):
    headers = _signup_and_auth_headers(api_client)

    create_resp = api_client.post("/watchlists", json={"name": "Tech Stocks"}, headers=headers)
    assert create_resp.status_code == 201
    watchlist_id = create_resp.json()["id"]

    list_resp = api_client.get("/watchlists", headers=headers)
    assert list_resp.status_code == 200
    assert any(wl["id"] == watchlist_id for wl in list_resp.json())


def test_watchlists_are_scoped_per_user(api_client):
    """One user must never see another user's watchlists — a basic
    authorization boundary that's easy to accidentally break by querying
    Watchlist without filtering on user_id."""
    headers_a = _signup_and_auth_headers(api_client, "a@example.com")
    headers_b = _signup_and_auth_headers(api_client, "b@example.com")

    api_client.post("/watchlists", json={"name": "A's list"}, headers=headers_a)

    b_lists = api_client.get("/watchlists", headers=headers_b).json()
    assert all(wl["name"] != "A's list" for wl in b_lists)


def test_cannot_access_another_users_watchlist_by_id(api_client):
    headers_a = _signup_and_auth_headers(api_client, "a2@example.com")
    headers_b = _signup_and_auth_headers(api_client, "b2@example.com")

    wl = api_client.post("/watchlists", json={"name": "A2's list"}, headers=headers_a).json()

    resp = api_client.get(f"/watchlists/{wl['id']}/items", headers=headers_b)
    assert resp.status_code == 404


def test_add_and_remove_watchlist_item(api_client):
    headers = _signup_and_auth_headers(api_client)
    wl = api_client.post("/watchlists", json={"name": "WL"}, headers=headers).json()

    add_resp = api_client.post(
        f"/watchlists/{wl['id']}/items", json={"symbol": "RELIANCE.NS", "exchange": "NSE"}, headers=headers
    )
    assert add_resp.status_code == 201
    assert add_resp.json()["symbol"] == "RELIANCE.NS"

    items = api_client.get(f"/watchlists/{wl['id']}/items", headers=headers).json()
    assert len(items) == 1

    del_resp = api_client.delete(f"/watchlists/{wl['id']}/items/RELIANCE.NS", headers=headers)
    assert del_resp.status_code == 204

    items_after = api_client.get(f"/watchlists/{wl['id']}/items", headers=headers).json()
    assert len(items_after) == 0


def test_changes_endpoint_returns_a_delta_per_item(api_client):
    headers = _signup_and_auth_headers(api_client)
    wl = api_client.post("/watchlists", json={"name": "WL"}, headers=headers).json()
    api_client.post(f"/watchlists/{wl['id']}/items", json={"symbol": "TCS.NS"}, headers=headers)

    resp = api_client.get(f"/watchlists/{wl['id']}/changes", headers=headers)
    assert resp.status_code == 200
    deltas = resp.json()
    assert len(deltas) == 1
    assert deltas[0]["symbol"] == "TCS.NS"
    # No live cache data in this test environment — must degrade to a safe
    # "not significant" default, never a crash or a fabricated number.
    assert deltas[0]["significant"] is False
