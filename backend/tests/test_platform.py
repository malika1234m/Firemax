from app.database import get_db
from app.security import hash_password, COOKIE_NAME, PLATFORM_COOKIE_NAME
from app.models import PlatformAdmin
from .conftest import signup

PLATFORM_EMAIL = "ops@firemex.io"
PLATFORM_PASS = "PlatformOps2026!"


async def _make_platform_admin():
    db = get_db()
    admin = PlatformAdmin(email=PLATFORM_EMAIL, name="Ops", password_hash=hash_password(PLATFORM_PASS))
    await db.platform_admins.insert_one(admin.model_dump())


# ── Isolation: the customer surface can never reach the platform console ─────

async def test_unauthenticated_cannot_access_platform(client):
    assert (await client.get("/platform/overview")).status_code == 401
    assert (await client.get("/platform/tenants")).status_code == 401


async def test_customer_admin_cannot_access_platform(client):
    # A fully authenticated CUSTOMER admin must still be denied the vendor console.
    await signup(client)
    assert client.cookies.get(COOKIE_NAME)                      # has a customer session
    assert (await client.get("/platform/overview")).status_code == 401
    assert (await client.get("/platform/tenants")).status_code == 401


async def test_platform_admin_cannot_use_customer_endpoints(client):
    # And the reverse: a platform session grants no customer/admin powers.
    await _make_platform_admin()
    res = await client.post("/platform/auth/login", json={"email": PLATFORM_EMAIL, "password": PLATFORM_PASS})
    assert res.status_code == 200
    assert client.cookies.get(PLATFORM_COOKIE_NAME)
    # Customer admin endpoints read a different cookie → platform session is a nobody there.
    assert (await client.get("/users/")).status_code == 401
    assert (await client.get("/auth/me")).status_code == 401


# ── Platform auth + aggregation ──────────────────────────────────────────────

async def test_platform_login_wrong_password(client):
    await _make_platform_admin()
    res = await client.post("/platform/auth/login", json={"email": PLATFORM_EMAIL, "password": "nope"})
    assert res.status_code == 401


async def test_platform_overview_shape(client):
    await _make_platform_admin()
    await client.post("/platform/auth/login", json={"email": PLATFORM_EMAIL, "password": PLATFORM_PASS})
    body = (await client.get("/platform/overview")).json()
    assert body["status"] in ("operational", "degraded")
    assert "companies" in body["fleet"] and "cameras" in body["fleet"]
    assert "database_connected" in body["infra"]
    assert body["uptime_seconds"] >= 0


async def test_platform_tenants_is_cross_tenant(client, client2):
    # Two separate companies exist; the platform console sees BOTH (unlike any
    # customer endpoint, which would see only its own org).
    await signup(client, org_name="Alpha Co", email="alpha@firemex.io")
    await signup(client2, org_name="Beta Co", email="beta@firemex.io")
    await _make_platform_admin()

    await client.post("/platform/auth/login", json={"email": PLATFORM_EMAIL, "password": PLATFORM_PASS})
    body = (await client.get("/platform/tenants")).json()
    names = {t["name"] for t in body["tenants"]}
    assert {"Alpha Co", "Beta Co"}.issubset(names)
