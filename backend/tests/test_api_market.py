from datetime import datetime, timezone

from app.services import cache


def _auth_headers(client, email="market-user@example.com"):
    resp = client.post("/auth/signup", json={"email": email, "password": "hunter22"})
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def test_quote_endpoint_404s_when_no_data_yet(api_client):
    headers = _auth_headers(api_client)
    resp = api_client.get("/market/quote/NOSUCHSTOCK.NS", headers=headers)
    assert resp.status_code == 404


def test_quote_endpoint_returns_cached_quote(api_client):
    headers = _auth_headers(api_client)
    now = datetime.now(timezone.utc)
    cache.set_latest("QUOTETEST.NS", {
        "symbol": "QUOTETEST.NS", "price": 250.5, "volume": 1000,
        "open": 248, "high": 252, "low": 247, "prev_close": 249,
        "exchange_ts": now, "source": "test",
    })

    resp = api_client.get("/market/quote/QUOTETEST.NS", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["price"] == 250.5
    assert body["stale"] is False


def test_history_endpoint_returns_points_for_watched_symbol(api_client):
    headers = _auth_headers(api_client)
    wl = api_client.post("/watchlists", json={"name": "WL"}, headers=headers).json()
    api_client.post(f"/watchlists/{wl['id']}/items", json={"symbol": "HISTTEST.NS"}, headers=headers)

    resp = api_client.get("/market/history/HISTTEST.NS", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["symbol"] == "HISTTEST.NS"
    assert resp.json()["points"] == []  # no PriceSnapshot rows ingested in this test


def test_digest_endpoint_falls_back_without_groq_key(api_client):
    headers = _auth_headers(api_client)
    wl = api_client.post("/watchlists", json={"name": "WL"}, headers=headers).json()
    api_client.post(f"/watchlists/{wl['id']}/items", json={"symbol": "DIGESTTEST.NS"}, headers=headers)

    resp = api_client.get(f"/watchlists/{wl['id']}/digest", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["ai_generated"] is False
    assert body["content"]


def test_mark_seen_updates_watermark_so_delta_is_no_longer_first_view(api_client):
    headers = _auth_headers(api_client)
    wl = api_client.post("/watchlists", json={"name": "WL"}, headers=headers).json()
    api_client.post(f"/watchlists/{wl['id']}/items", json={"symbol": "SEENTEST.NS"}, headers=headers)

    now = datetime.now(timezone.utc)
    cache.set_latest("SEENTEST.NS", {
        "symbol": "SEENTEST.NS", "price": 100.0, "volume": 500, "exchange_ts": now, "source": "test",
    })

    before = api_client.get(f"/watchlists/{wl['id']}/changes", headers=headers).json()
    assert before[0]["significant"] is True  # first view

    mark_resp = api_client.post(f"/watchlists/{wl['id']}/mark-seen", headers=headers)
    assert mark_resp.status_code == 204

    after = api_client.get(f"/watchlists/{wl['id']}/changes", headers=headers).json()
    assert after[0]["significant"] is False
    assert after[0]["last_seen_price"] == 100.0


def test_natural_language_add_falls_back_to_keyword_matching(api_client):
    headers = _auth_headers(api_client)
    wl = api_client.post("/watchlists", json={"name": "WL"}, headers=headers).json()

    resp = api_client.post(
        f"/watchlists/{wl['id']}/items/natural-language", json={"query": "add banking stocks"}, headers=headers
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ai_generated"] is False
    # Whatever the keyword fallback matches, it must never silently fail —
    # either it found symbols or it explains why not, never a 500.
    assert "explanation" in body
