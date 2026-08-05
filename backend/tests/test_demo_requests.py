from app.database import get_db


async def test_demo_request_succeeds_with_required_fields(client):
    res = await client.post("/demo-requests/", json={
        "name": "Jamie Rivera", "email": "jamie@example.com", "company": "Rivera Warehousing",
    })
    assert res.status_code == 200
    assert res.json()["status"] == "received"


async def test_demo_request_is_persisted(client):
    await client.post("/demo-requests/", json={
        "name": "Jamie Rivera", "email": "jamie@example.com", "company": "Rivera Warehousing",
        "phone": "+15551234567", "message": "Interested in the Pro plan.",
    })
    db = get_db()
    saved = await db.demo_requests.find_one({"email": "jamie@example.com"})
    assert saved is not None
    assert saved["company"] == "Rivera Warehousing"
    assert saved["message"] == "Interested in the Pro plan."


async def test_demo_request_rejects_missing_fields(client):
    res = await client.post("/demo-requests/", json={"name": "Jamie Rivera"})
    assert res.status_code == 422


async def test_demo_request_is_rate_limited(client):
    for _ in range(5):
        res = await client.post("/demo-requests/", json={
            "name": "Jamie Rivera", "email": "jamie@example.com", "company": "Rivera Warehousing",
        })
        assert res.status_code == 200

    res = await client.post("/demo-requests/", json={
        "name": "Jamie Rivera", "email": "jamie@example.com", "company": "Rivera Warehousing",
    })
    assert res.status_code == 429


async def test_demo_request_does_not_require_authentication(client):
    res = await client.post("/demo-requests/", json={
        "name": "Anon Visitor", "email": "anon@example.com", "company": "Anon Co",
    })
    assert res.status_code == 200
