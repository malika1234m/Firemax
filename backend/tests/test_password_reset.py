from app.database import get_db
from .conftest import signup


async def test_forgot_password_same_response_for_unknown_email(client):
    res = await client.post("/auth/forgot-password", json={"email": "nobody@nowhere.io"})
    assert res.status_code == 200
    assert res.json()["status"] == "if_account_exists_email_sent"


async def test_forgot_password_creates_token_for_known_email(client):
    await signup(client)
    res = await client.post("/auth/forgot-password", json={"email": "jordan@firemex.io"})
    assert res.status_code == 200
    assert res.json()["status"] == "if_account_exists_email_sent"

    db = get_db()
    token = await db.password_reset_tokens.find_one({})
    assert token is not None
    assert token["used"] is False


async def test_reset_password_with_valid_token(client):
    await signup(client)
    await client.post("/auth/forgot-password", json={"email": "jordan@firemex.io"})

    db = get_db()
    token = await db.password_reset_tokens.find_one({})

    res = await client.post("/auth/reset-password", json={"token": token["token"], "new_password": "brandnewpass123"})
    assert res.status_code == 200

    await client.post("/auth/logout")
    res = await client.post("/auth/login", json={"email": "jordan@firemex.io", "password": "brandnewpass123"})
    assert res.status_code == 200

    # old password no longer works
    await client.post("/auth/logout")
    res = await client.post("/auth/login", json={"email": "jordan@firemex.io", "password": "testpass123"})
    assert res.status_code == 401


async def test_reset_password_token_cannot_be_reused(client):
    await signup(client)
    await client.post("/auth/forgot-password", json={"email": "jordan@firemex.io"})

    db = get_db()
    token = await db.password_reset_tokens.find_one({})

    res = await client.post("/auth/reset-password", json={"token": token["token"], "new_password": "firstnewpass123"})
    assert res.status_code == 200

    res = await client.post("/auth/reset-password", json={"token": token["token"], "new_password": "secondnewpass123"})
    assert res.status_code == 400


async def test_reset_password_rejects_unknown_token(client):
    res = await client.post("/auth/reset-password", json={"token": "not-a-real-token", "new_password": "newpassword123"})
    assert res.status_code == 400


async def test_reset_password_rejects_expired_token(client):
    from datetime import datetime, timedelta
    await signup(client)

    db = get_db()
    user = await db.users.find_one({"email": "jordan@firemex.io"})
    expired = {
        "token": "expired-token-abc",
        "user_id": user["user_id"],
        "expires_at": datetime.utcnow() - timedelta(minutes=5),
        "used": False,
        "created_at": datetime.utcnow() - timedelta(hours=2),
    }
    await db.password_reset_tokens.insert_one(expired)

    res = await client.post("/auth/reset-password", json={"token": "expired-token-abc", "new_password": "newpassword123"})
    assert res.status_code == 400
