from .conftest import auth, register


def test_chats_are_saved_listed_and_private(client):
    a = register(client)
    msgs = [{"role": "user", "content": "Selam"}, {"role": "assistant", "content": "Merhaba!", "images": ["https://x/y.png"]}]
    r = client.put("/api/chats/c1", json={"title": "Selam", "messages": msgs}, headers=auth(a))
    assert r.status_code == 200
    client.put("/api/chats/c2", json={"title": "İkinci", "messages": msgs[:1]}, headers=auth(a))
    listed = client.get("/api/chats", headers=auth(a)).json()
    assert [c["id"] for c in listed] == ["c2", "c1"]
    assert client.get("/api/chats/c1", headers=auth(a)).json()["messages"] == msgs

    b = register(client, email="baska@ornek.com")
    assert client.get("/api/chats", headers=auth(b)).json() == []
    assert client.get("/api/chats/c1", headers=auth(b)).status_code == 404
    assert client.put("/api/chats/c1", json={"title": "x", "messages": []}, headers=auth(b)).status_code == 404

    client.put("/api/chats/c1", json={"title": "Güncel", "messages": msgs}, headers=auth(a))
    assert client.get("/api/chats", headers=auth(a)).json()[0]["title"] == "Güncel"
    assert client.delete("/api/chats/c1", headers=auth(a)).status_code == 204
    assert [c["id"] for c in client.get("/api/chats", headers=auth(a)).json()] == ["c2"]
