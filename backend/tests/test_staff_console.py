from app.database import get_db
from app.security import hash_password
from app.models import PlatformAdmin
from .conftest import signup

PLATFORM_EMAIL = "ops@firemex.io"
PLATFORM_PASS = "PlatformOps2026!"


async def _platform_login(client):
    db = get_db()
    await db.platform_admins.insert_one(
        PlatformAdmin(email=PLATFORM_EMAIL, name="Ops", password_hash=hash_password(PLATFORM_PASS)).model_dump()
    )
    await client.post("/platform/auth/login", json={"email": PLATFORM_EMAIL, "password": PLATFORM_PASS})


# ── Plans ────────────────────────────────────────────────────────────────────

async def test_platform_plans_list_and_edit(client):
    await _platform_login(client)
    plans = (await client.get("/platform/plans")).json()["plans"]
    assert {p["plan_id"] for p in plans} == {"trial", "starter", "pro"}

    res = await client.patch("/platform/plans/starter", json={"price_usd": 79, "max_cameras": 8, "features": ["A", "B"]})
    assert res.status_code == 200
    body = res.json()
    assert body["price_usd"] == 79 and body["max_cameras"] == 8 and body["features"] == ["A", "B"]


async def test_plan_edit_reflects_in_customer_billing(client, client2):
    # Staff raises the Starter camera limit; a customer's billing status shows it.
    await _platform_login(client)
    await client.patch("/platform/plans/starter", json={"max_cameras": 9})

    await signup(client2, org_name="Cust Co", email="cust@firemex.io")
    status = (await client2.get("/billing/status")).json()
    assert status["plans"]["starter"]["max_cameras"] == 9


async def test_customer_cannot_edit_plans(client):
    await signup(client)
    assert (await client.patch("/platform/plans/starter", json={"price_usd": 1})).status_code == 401


# ── Billing / pipelines ──────────────────────────────────────────────────────

async def test_platform_billing_shape(client):
    await _platform_login(client)
    body = (await client.get("/platform/billing")).json()
    assert "mrr_usd" in body and "customers" in body and "status_counts" in body


async def test_platform_pipelines_shape(client):
    await _platform_login(client)
    body = (await client.get("/platform/pipelines")).json()
    assert "model" in body and "pipelines" in body and "online" in body


# ── Complaints ───────────────────────────────────────────────────────────────

async def test_customer_submits_and_sees_own_complaint(client):
    await signup(client)
    res = await client.post("/support/complaints", json={"subject": "Test", "message": "Something is wrong", "category": "technical"})
    assert res.status_code == 200
    mine = (await client.get("/support/complaints")).json()
    assert len(mine) == 1 and mine[0]["subject"] == "Test"


async def test_complaint_is_org_scoped(client, client2):
    await signup(client, org_name="A", email="a@firemex.io")
    await signup(client2, org_name="B", email="b@firemex.io")
    await client.post("/support/complaints", json={"subject": "A issue", "message": "x"})
    # Org B must not see org A's complaint.
    assert (await client2.get("/support/complaints")).json() == []


async def test_staff_sees_and_resolves_complaint(client, client2):
    await signup(client2, org_name="Cust", email="cust@firemex.io")
    await client2.post("/support/complaints", json={"subject": "Night false alarms", "message": "headlights"})

    await _platform_login(client)
    listing = (await client.get("/platform/complaints")).json()
    assert listing["open_count"] == 1
    cid = listing["complaints"][0]["complaint_id"]

    res = await client.patch(f"/platform/complaints/{cid}", json={"status": "resolved", "staff_note": "fixed"})
    assert res.status_code == 200 and res.json()["status"] == "resolved"

    # Customer now sees the staff note + resolved status.
    mine = (await client2.get("/support/complaints")).json()
    assert mine[0]["status"] == "resolved" and mine[0]["staff_note"] == "fixed"


async def test_customer_cannot_read_platform_complaints(client):
    await signup(client)
    assert (await client.get("/platform/complaints")).status_code == 401
