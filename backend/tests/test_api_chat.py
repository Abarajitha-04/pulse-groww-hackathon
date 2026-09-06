def _auth_headers(client, email="chat-api@example.com"):
    resp = client.post("/auth/signup", json={"email": email, "password": "hunter22"})
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def test_chat_requires_auth(api_client):
    resp = api_client.post("/chat", json={"message": "hi"})
    assert resp.status_code == 401


def test_chat_round_trip_and_history(api_client):
    headers = _auth_headers(api_client)

    resp = api_client.post("/chat", json={"message": "how is my watchlist?"}, headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["ai_generated"] is False  # no GROQ_API_KEY in the test environment
    assert isinstance(body["reply"], str) and body["reply"]

    history = api_client.get("/chat/history", headers=headers).json()
    assert [m["role"] for m in history] == ["user", "assistant"]


def test_chat_history_is_scoped_per_user(api_client):
    headers_a = _auth_headers(api_client, "chat-a@example.com")
    headers_b = _auth_headers(api_client, "chat-b@example.com")

    api_client.post("/chat", json={"message": "hello from A"}, headers=headers_a)

    history_b = api_client.get("/chat/history", headers=headers_b).json()
    assert history_b == []


def test_clear_chat_history(api_client):
    headers = _auth_headers(api_client)
    api_client.post("/chat", json={"message": "hi"}, headers=headers)

    clear_resp = api_client.delete("/chat/history", headers=headers)
    assert clear_resp.status_code == 204

    assert api_client.get("/chat/history", headers=headers).json() == []


def test_empty_message_is_rejected(api_client):
    headers = _auth_headers(api_client)
    resp = api_client.post("/chat", json={"message": ""}, headers=headers)
    assert resp.status_code == 422
