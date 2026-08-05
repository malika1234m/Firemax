from app.database import get_db
from app.security import COOKIE_NAME
from .conftest import signup


async def test_old_session_rejected_after_password_change(client):
    await signup(client)
    old_cookie = client.cookies.get(COOKIE_NAME)
    assert old_cookie

    # Change the password — client's cookie jar refreshes to the new version.
    res = await client.post("/auth/change-password", json={
        "current_password": "testpass123", "new_password": "newpassword123",
    })
    assert res.status_code == 200

    # The acting session (refreshed cookie) still works.
    assert (await client.get("/auth/me")).status_code == 200

    # A request replaying the OLD cookie (e.g. a stolen/leaked one) is rejected.
    res = await client.get("/auth/me", cookies={COOKIE_NAME: old_cookie})
    assert res.status_code == 401


async def test_all_sessions_die_after_password_reset(client):
    await signup(client)
    old_cookie = client.cookies.get(COOKIE_NAME)

    await client.post("/auth/forgot-password", json={"email": "jordan@firemex.io"})
    db = get_db()
    token = (await db.password_reset_tokens.find_one({}))["token"]
    res = await client.post("/auth/reset-password", json={"token": token, "new_password": "resetpass123"})
    assert res.status_code == 200

    # The pre-reset session must no longer be valid.
    res = await client.get("/auth/me", cookies={COOKIE_NAME: old_cookie})
    assert res.status_code == 401


async def test_login_wrong_password_and_unknown_email_both_401(client):
    await signup(client)
    # Known email, wrong password
    r1 = await client.post("/auth/login", json={"email": "jordan@firemex.io", "password": "totally-wrong"})
    # Unknown email
    r2 = await client.post("/auth/login", json={"email": "ghost@nowhere.io", "password": "totally-wrong"})
    assert r1.status_code == 401 and r2.status_code == 401
    # Identical error body — no oracle distinguishing the two cases.
    assert r1.json() == r2.json()
