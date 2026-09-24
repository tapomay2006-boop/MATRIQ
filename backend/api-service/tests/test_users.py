async def test_create_and_fetch_user(client):
    payload = {
        "email": "sangik@example.com",
        "full_name": "Sangik Ghosh",
        "password": "supersecret123",
    }
    created = await client.post("/api/v1/users", json=payload)
    assert created.status_code == 201
    user = created.json()
    assert user["email"] == payload["email"]

    fetched = await client.get(f"/api/v1/users/{user['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == user["id"]


async def test_duplicate_email_conflicts(client):
    payload = {"email": "dupe@example.com", "password": "supersecret123"}
    first = await client.post("/api/v1/users", json=payload)
    assert first.status_code == 201
    second = await client.post("/api/v1/users", json=payload)
    assert second.status_code == 409
