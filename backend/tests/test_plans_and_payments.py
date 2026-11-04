"""Camera plans, the trial's end, payments and sharing — end to end.

Stripe is replaced by a recorder: the webhook's signature check returns the
event it was given, and API calls are captured so the tests can assert what
would have been sent.
"""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
import stripe

from app.config import settings

from .conftest import signup
from .test_licence import INSTALL_A, _check, _claims, _key


@pytest.fixture
def fake_stripe(monkeypatch):
    calls = []
    monkeypatch.setattr(settings, "STRIPE_SECRET_KEY", "sk_test_fake")
    monkeypatch.setattr(stripe.Webhook, "construct_event", staticmethod(lambda payload, sig, secret: _events.pop(0)))
    monkeypatch.setattr(stripe.Price, "list", staticmethod(lambda **kw: SimpleNamespace(data=[SimpleNamespace(id=f"price_{kw['lookup_keys'][0]}")])))
    monkeypatch.setattr(stripe.Customer, "create", staticmethod(lambda **kw: SimpleNamespace(id="cus_1")))

    def checkout(**kw):
        calls.append(("checkout", kw))
        return SimpleNamespace(url="https://checkout.stripe.test/s")
    monkeypatch.setattr(stripe.checkout.Session, "create", staticmethod(checkout))
    monkeypatch.setattr(stripe.Subscription, "retrieve", staticmethod(
        lambda sid: {"id": sid, "items": {"data": [{"id": "si_1", "quantity": _sub_qty[0]}]}}))
    monkeypatch.setattr(stripe.Subscription, "modify", staticmethod(lambda sid, **kw: calls.append(("modify", kw))))
    invoices = []
    monkeypatch.setattr(stripe.Invoice, "list", staticmethod(lambda **kw: {"data": list(invoices)}))
    from app.routers import billing
    billing._price_ids.clear()
    return SimpleNamespace(calls=calls, invoices=invoices)


_events: list = []
_sub_qty = [5]
_n = [0]


async def _send(client, kind, obj):
    _n[0] += 1
    _events.append({"id": f"evt_{_n[0]}", "type": kind, "data": {"object": obj}})
    res = await client.post("/billing/webhook", content=b"{}", headers={"stripe-signature": "t"})
    assert res.status_code == 200
    return res.json()


async def _org(db):
    return await db.organizations.find_one({"name": "Acme Fire Safety"})


async def _subscribe_pro(client, db, cameras=12, interval="month"):
    org = await _org(db)
    await db.organizations.update_one({"org_id": org["org_id"]}, {"$set": {"stripe_customer_id": "cus_1"}})
    await _send(client, "checkout.session.completed", {
        "customer": "cus_1", "subscription": "sub_1",
        "metadata": {"org_id": org["org_id"], "plan": "pro", "interval": interval, "cameras": str(cameras)}})


# ── Trial ────────────────────────────────────────────────────────────────────

async def test_trial_ends_after_14_days_and_drops_to_one_camera(client, db):
    await signup(client)
    key = await _key(client)
    assert (await client.post("/licence/validate", json=_check(key))).json()["max_cameras"] == 4

    # 14 days pass.
    await db.organizations.update_one({"licence_key": key},
                                      {"$set": {"trial_ends_at": datetime.utcnow() - timedelta(minutes=1)}})
    body = (await client.post("/licence/validate", json=_check(key))).json()
    assert body["valid"] is False and body["max_cameras"] == 1
    assert "trial has ended" in body["reason"]

    status = (await client.get("/billing/status")).json()
    assert status["subscription"]["state"] == "free" and status["subscription"]["trial_ended"] is True
    assert status["org"]["plan"] == "free"
    # The customer is told, once.
    events = [e["message"] for e in (await client.get("/organizations/me/activity")).json()]
    assert sum("free trial ended" in m for m in events) == 1


async def test_trial_counts_down(client, db):
    await signup(client)
    await db.organizations.update_one({"name": "Acme Fire Safety"},
                                      {"$set": {"trial_ends_at": datetime.utcnow() + timedelta(days=2, hours=3)}})
    sub = (await client.get("/billing/status")).json()["subscription"]
    assert sub["state"] == "trial" and sub["trial_days_left"] == 3


# ── Paying ───────────────────────────────────────────────────────────────────

async def test_checkout_sends_cameras_as_quantity_and_clamps_them(client, fake_stripe):
    await signup(client)
    res = await client.post("/billing/checkout-session", json={"plan": "pro", "interval": "year", "cameras": 500})
    assert res.status_code == 200
    kind, kw = fake_stripe.calls[-1]
    assert kw["line_items"][0]["quantity"] == 64                # Pro's ceiling
    assert kw["line_items"][0]["price"] == "price_firemex_pro_year_3000"
    assert kw["subscription_data"]["metadata"]["interval"] == "year"

    await client.post("/billing/checkout-session", json={"plan": "starter", "interval": "month", "cameras": 9})
    assert fake_stripe.calls[-1][1]["line_items"][0] == {"price": "price_firemex_starter_month_900", "quantity": 1}


async def test_checkout_refuses_trial_and_unknown_period(client, fake_stripe):
    await signup(client)
    assert (await client.post("/billing/checkout-session", json={"plan": "trial"})).status_code == 400
    assert (await client.post("/billing/checkout-session", json={"plan": "pro", "interval": "week"})).status_code == 400


async def test_paid_pro_plan_signs_the_bought_cameras_into_the_licence(client, db, fake_stripe):
    await signup(client)
    key = await _key(client)
    await _subscribe_pro(client, db, cameras=12, interval="year")
    body = (await client.post("/licence/validate", json=_check(key))).json()
    assert body["valid"] is True and _claims(body["entitlement"])["max_cameras"] == 12
    sub = (await client.get("/billing/status")).json()["subscription"]
    assert (sub["plan"], sub["state"], sub["cameras"], sub["interval"]) == ("pro", "active", 12, "year")
    # A second checkout would mean a second subscription and a double charge.
    assert (await client.post("/billing/checkout-session", json={"plan": "pro"})).status_code == 409


async def test_adding_cameras_charges_now_removing_waits_for_renewal(client, db, fake_stripe):
    await signup(client)
    await _subscribe_pro(client, db, cameras=12)
    _sub_qty[0] = 12

    res = await client.post("/billing/subscription", json={"plan": "pro", "interval": "month", "cameras": 20})
    assert res.json() == {"changed": True, "effective": "after_payment"}
    sent = fake_stripe.calls[-1][1]
    assert sent["proration_behavior"] == "always_invoice"
    # Not granted until Stripe says the extra cameras were paid for.
    assert sent["payment_behavior"] == "pending_if_incomplete"
    assert (await _org(db))["cameras"] == 12
    await _send(client, "customer.subscription.updated", {
        "id": "sub_1", "customer": "cus_1", "status": "active",
        "items": {"data": [{"quantity": 20, "price": {"metadata": {"plan_id": "pro"}, "recurring": {"interval": "month"}}}]}})
    assert (await _org(db))["cameras"] == 20

    _sub_qty[0] = 20
    res = await client.post("/billing/subscription", json={"plan": "pro", "interval": "month", "cameras": 8})
    assert res.json()["effective"] == "renewal"
    assert fake_stripe.calls[-1][1]["proration_behavior"] == "none"
    assert (await _org(db))["cameras"] == 20      # still paid for until renewal


async def test_cancel_keeps_access_until_the_period_ends(client, db, fake_stripe):
    await signup(client)
    key = await _key(client)
    await _subscribe_pro(client, db)
    assert (await client.post("/billing/cancel")).json() == {"cancel_at_period_end": True}
    assert fake_stripe.calls[-1][1] == {"cancel_at_period_end": True}
    assert (await client.post("/licence/validate", json=_check(key))).json()["valid"] is True

    # The period ends: Stripe deletes the subscription.
    await _send(client, "customer.subscription.deleted", {"id": "sub_1", "customer": "cus_1"})
    body = (await client.post("/licence/validate", json=_check(key))).json()
    assert body["valid"] is False and body["max_cameras"] == 1


async def test_failed_payment_keeps_cameras_for_seven_days_then_one(client, db, fake_stripe):
    await signup(client)
    key = await _key(client)
    await _subscribe_pro(client, db, cameras=10)
    await _send(client, "invoice.payment_failed", {"customer": "cus_1", "amount_due": 3000})

    sub = (await client.get("/billing/status")).json()["subscription"]
    assert sub["state"] == "grace" and sub["grace_until"]
    assert (await client.post("/licence/validate", json=_check(key))).json()["max_cameras"] == 10

    await db.organizations.update_one({"stripe_customer_id": "cus_1"},
                                      {"$set": {"grace_until": datetime.utcnow() - timedelta(seconds=1)}})
    assert (await client.post("/licence/validate", json=_check(key))).json()["max_cameras"] == 1

    # The retry succeeds: everything comes back.
    await _send(client, "invoice.paid", {"id": "in_9", "customer": "cus_1", "amount_paid": 3000,
                                         "status": "paid", "created": 1_790_000_000})
    assert (await client.post("/licence/validate", json=_check(key))).json()["max_cameras"] == 10


async def test_replayed_webhook_is_applied_once(client, db, fake_stripe):
    await signup(client)
    await _subscribe_pro(client, db)
    await _send(client, "invoice.payment_failed", {"customer": "cus_1", "amount_due": 1500})
    first = (await _org(db))["grace_until"]
    _events.append({"id": f"evt_{_n[0]}", "type": "invoice.payment_failed",
                    "data": {"object": {"customer": "cus_1", "amount_due": 1500}}})
    res = await client.post("/billing/webhook", content=b"{}", headers={"stripe-signature": "t"})
    assert res.json() == {"status": "duplicate"}
    assert (await _org(db))["grace_until"] == first


async def test_billing_history_is_newest_first(client, db, fake_stripe):
    await signup(client)
    await _subscribe_pro(client, db)
    for i, ts in enumerate((1_780_000_000, 1_790_000_000, 1_785_000_000)):
        fake_stripe.invoices.append({"id": f"in_{i}", "number": f"FMX-{i}", "created": ts, "status": "paid",
                                     "amount_paid": 1500, "currency": "usd",
                                     "lines": {"data": [{"description": "5 × FiremeX Pro per camera",
                                                         "period": {"start": ts, "end": ts + 2_592_000}}]}})
    rows = (await client.get("/billing/invoices")).json()["invoices"]
    assert [r["number"] for r in rows] == ["FMX-1", "FMX-2", "FMX-0"]
    assert rows[0]["amount_usd"] == 15 and rows[0]["period_end"] and rows[0]["description"]


async def test_billing_history_falls_back_to_recorded_payments(client, db, fake_stripe, monkeypatch):
    await signup(client)
    await _subscribe_pro(client, db)
    for i, ts in enumerate((1_780_000_000, 1_790_000_000)):
        await _send(client, "invoice.paid", {"id": f"in_{i}", "number": f"FMX-{i}", "customer": "cus_1",
                                             "amount_paid": 1500, "status": "paid", "created": ts})

    def down(**kw):
        raise stripe.APIConnectionError("down")
    monkeypatch.setattr(stripe.Invoice, "list", staticmethod(down))
    rows = (await client.get("/billing/invoices")).json()["invoices"]
    assert [r["number"] for r in rows] == ["FMX-1", "FMX-0"]


# ── Sharing ──────────────────────────────────────────────────────────────────

def _check_seq(key, seq, install=INSTALL_A):
    return {**_check(key, install), "addon_version": "1.7.0", "lease_seq": seq}


async def test_each_lease_carries_the_next_sequence_number(client):
    await signup(client)
    key = await _key(client)
    seqs = []
    seq = None
    for _ in range(3):
        body = (await client.post("/licence/validate", json=_check_seq(key, seq))).json()
        seq = _claims(body["entitlement"])["seq"]
        seqs.append(seq)
    assert seqs == [1, 2, 3]


async def test_a_copied_installation_is_refused_and_the_owner_told(client):
    """Two machines with the same /data both start holding lease 1, and from
    then on leapfrog each other: every check one of them makes is stale."""
    await signup(client)
    key = await _key(client)
    seq = lambda body: _claims(body["entitlement"])["seq"]
    first = seq((await client.post("/licence/validate", json=_check_seq(key, None))).json())

    a = seq((await client.post("/licence/validate", json=_check_seq(key, first))).json())
    # B's first stale check could be a lost reply, so it is let through...
    b_body = (await client.post("/licence/validate", json=_check_seq(key, first))).json()
    assert b_body["valid"] is True
    # ...but now A is stale too: a second stale check in two days is a copy.
    a_body = (await client.post("/licence/validate", json=_check_seq(key, a))).json()
    assert a_body["valid"] is False and "another machine" in a_body["reason"]
    # One copy keeps working; the licence never covers two.
    assert (await client.post("/licence/validate", json=_check_seq(key, seq(b_body)))).json()["valid"] is True
    assert (await client.post("/licence/validate", json=_check_seq(key, a))).json()["valid"] is False

    events = [e["message"] for e in (await client.get("/organizations/me/activity")).json()]
    assert sum("two machines" in m for m in events) == 1
    assert (await client.get("/licence/me/activations")).json()[0]["clone_suspected_at"]


async def test_one_lost_reply_is_not_a_clone(client):
    await signup(client)
    key = await _key(client)
    s1 = _claims((await client.post("/licence/validate", json=_check_seq(key, None))).json()["entitlement"])["seq"]
    await client.post("/licence/validate", json=_check_seq(key, s1))      # reply lost: add-on still holds s1
    body = (await client.post("/licence/validate", json=_check_seq(key, s1))).json()
    assert body["valid"] is True
    # ...and it carries on normally from there.
    s = _claims(body["entitlement"])["seq"]
    assert (await client.post("/licence/validate", json=_check_seq(key, s))).json()["valid"] is True


async def test_add_on_reports_cameras_in_use(client):
    await signup(client)
    key = await _key(client)
    await client.post("/licence/validate", json={**_check_seq(key, None), "cameras_in_use": 3})
    assert (await client.get("/billing/status")).json()["usage"]["cameras_in_use"] == 3


async def test_lease_is_thirty_days(client):
    await signup(client)
    key = await _key(client)
    claims = _claims((await client.post("/licence/validate", json=_check(key))).json()["entitlement"])
    assert claims["exp"] - claims["iat"] == 30 * 86400


async def test_a_copy_cannot_dodge_the_check_by_sending_no_number(client):
    await signup(client)
    key = await _key(client)
    seq = lambda body: _claims(body["entitlement"])["seq"]
    s1 = seq((await client.post("/licence/validate", json=_check_seq(key, None))).json())
    s2 = seq((await client.post("/licence/validate", json=_check_seq(key, s1))).json())
    # A copy leaves the number out, twice: that is two stale checks.
    await client.post("/licence/validate", json=_check_seq(key, None))
    body = (await client.post("/licence/validate", json=_check_seq(key, None))).json()
    assert body["valid"] is False and "another machine" in body["reason"]
    assert s2 > s1
