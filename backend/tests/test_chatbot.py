def test_chatbot_health(client):
    res = client.get("/api/v1/chatbot/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ready"


def test_chatbot_message(client, auth_headers):
    res = client.post(
        "/api/v1/chatbot/chat",
        json={"message": "How do I submit a claim?"},
        headers=auth_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert "response" in data
    assert len(data["response"]) > 0
