"""Plans, payment and invoices.

Stripe is the source of truth for money; this database mirrors what a webhook
told it, so the add-on's licence check never waits on Stripe.

    POST /billing/checkout-session   first paid plan: Stripe Checkout
    POST /billing/subscription       change plan, billing period or cameras
    POST /billing/cancel | /resume   cancel at period end, or undo that
    POST /billing/portal-session     card details, in Stripe's portal
    GET  /billing/invoices           what was paid, newest first

Prices are created in Stripe on startup from the plan catalog. Each Stripe price
is named after its amount (lookup key firemex_<plan>_<interval>_<cents>), so a
price edited in the staff console becomes a NEW Stripe price for new customers
while existing subscribers stay on what they agreed to.

Changing cameras: adding is charged straight away, prorated, because the extra
cameras start working straight away. Removing takes effect at renewal, so
nobody is refunded for a camera they already had for most of the month.
"""
import logging
from datetime import datetime, timedelta, timezone

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request

from app import account_events, subscription
from app.config import settings
from app.database import get_db
from app.models import OrganizationPublic, UserPublic
from app.plans import INTERVALS, clamp_cameras, get_plan, list_plans, price_cents
from app.security import get_current_user, require_admin

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/billing", tags=["billing"])

# (plan_id, interval) -> Stripe Price id, filled by bootstrap_prices_sync().
_price_ids: dict[tuple[str, str], str] = {}


def stripe_configured() -> bool:
    return bool(settings.STRIPE_SECRET_KEY)


def lookup_key(plan: dict, interval: str) -> str:
    return f"firemex_{plan['plan_id']}_{interval}_{price_cents(plan, interval)}"


def _ensure_price(plan: dict, interval: str) -> str | None:
    key = lookup_key(plan, interval)
    existing = stripe.Price.list(lookup_keys=[key], limit=1)
    if existing.data:
        return existing.data[0].id
    unit = "per camera" if plan.get("per_camera") else ""
    product = stripe.Product.create(name=f"FiremeX {plan['label']} {unit}".strip(),
                                    metadata={"plan_id": plan["plan_id"]})
    price = stripe.Price.create(
        product=product.id, unit_amount=price_cents(plan, interval), currency="usd",
        recurring={"interval": interval}, lookup_key=key,
        metadata={"plan_id": plan["plan_id"], "interval": interval})
    logger.info("[stripe] created price %s for %s/%s", price.id, plan["plan_id"], interval)
    return price.id


async def _price_id(plan: dict, interval: str) -> str:
    cached = _price_ids.get((plan["plan_id"], interval))
    if cached:
        return cached
    stripe.api_key = settings.STRIPE_SECRET_KEY
    try:
        pid = _ensure_price(plan, interval)
    except Exception:
        logger.exception("[stripe] could not prepare price for %s/%s", plan["plan_id"], interval)
        raise HTTPException(status_code=503, detail="Checkout isn't ready yet — please try again in a moment.")
    _price_ids[(plan["plan_id"], interval)] = pid
    return pid


def bootstrap_prices_sync():
    """Create a Stripe Price for every purchasable plan and interval at startup.
    Uses the default catalog: the live one is checked again at checkout."""
    if not stripe_configured():
        return
    from app.plans import DEFAULT_PLANS
    stripe.api_key = settings.STRIPE_SECRET_KEY
    for plan in DEFAULT_PLANS.values():
        if not plan["purchasable"]:
            continue
        for interval in INTERVALS:
            try:
                _price_ids[(plan["plan_id"], interval)] = _ensure_price(plan, interval)
            except Exception:
                logger.exception("[stripe] failed to bootstrap price for %s/%s", plan["plan_id"], interval)


def _plan_public(p: dict) -> dict:
    return {
        "plan_id": p["plan_id"], "label": p["label"], "order": p.get("order", 0),
        "purchasable": p["purchasable"], "per_camera": p["per_camera"],
        "price_month_usd": p["price_month_usd"], "price_year_usd": p["price_year_usd"],
        "cameras": p["cameras"], "min_cameras": p["min_cameras"], "max_cameras": p["max_cameras"],
        "max_users": p["max_users"], "max_installs": p["max_installs"],
        "features": p.get("features", []),
    }


@router.get("/plans")
async def public_plans():
    """Public plan catalog for the pricing section — no auth."""
    return {"plans": [_plan_public(p) for p in await list_plans()]}


@router.get("/status")
async def billing_status(user: UserPublic = Depends(get_current_user)):
    db = get_db()
    org = await subscription.refresh(db, await db.organizations.find_one({"org_id": user.org_id}))
    plans = await list_plans()
    current = next((p for p in plans if p["plan_id"] == org.get("plan")), plans[0])
    installs = await db.licence_activations.find(
        {"org_id": user.org_id, "removed": {"$ne": True}}).to_list(100)
    in_use = [i["cameras_in_use"] for i in installs if i.get("cameras_in_use") is not None]
    return {
        "org": OrganizationPublic(**org),
        "subscription": await subscription.summary(db, org),
        "usage": {
            "users": await db.users.count_documents({"org_id": user.org_id}),
            "installs": len(installs),
            # Only add-ons from 1.7.0 report this; None means "not known yet".
            "cameras_in_use": sum(in_use) if in_use else None,
        },
        "limits": {"max_users": current["max_users"], "max_installs": current["max_installs"],
                   "label": current["label"]},
        "stripe_configured": stripe_configured(),
        "has_billing_account": bool(org.get("stripe_customer_id")),
        "has_subscription": bool(org.get("stripe_subscription_id"))
                            and org.get("subscription_status") in ("active", "past_due"),
        "plans": {p["plan_id"]: _plan_public(p) for p in plans},
    }


def _ts(value) -> str | None:
    return datetime.fromtimestamp(value, tz=timezone.utc).isoformat() if value else None


@router.get("/invoices")
async def list_invoices(admin: UserPublic = Depends(require_admin)):
    """Invoices, newest first. From Stripe when it is reachable (it has the PDFs);
    otherwise the payments our webhook recorded, so history never goes blank."""
    db = get_db()
    org = await db.organizations.find_one({"org_id": admin.org_id})
    local = await db.payments.find({"org_id": admin.org_id}, {"_id": 0}).sort("created", -1).to_list(100)

    rows = None
    if stripe_configured() and org.get("stripe_customer_id"):
        stripe.api_key = settings.STRIPE_SECRET_KEY
        try:
            result = stripe.Invoice.list(customer=org["stripe_customer_id"], limit=100)
            rows = [_invoice_row(inv) for inv in result.get("data", [])
                    if inv.get("status") != "draft"]
        except Exception:
            logger.exception("[stripe] could not list invoices for org %s", admin.org_id)
    if rows is None:
        rows = [{**r, "created": r["created"].replace(tzinfo=timezone.utc).isoformat()
                 if isinstance(r.get("created"), datetime) else r.get("created")} for r in local]
    # Sorted here rather than trusted from the source: the page promises
    # newest first, and a merged or cached list may not arrive that way.
    rows.sort(key=lambda r: r["created"] or "", reverse=True)
    return {"invoices": rows}


def _invoice_row(inv) -> dict:
    line = ((inv.get("lines") or {}).get("data") or [{}])[0]
    period = line.get("period") or {}
    return {
        "id": inv.get("id"), "number": inv.get("number"),
        "created": _ts(inv.get("created")),
        "description": line.get("description"),
        "period_start": _ts(period.get("start")), "period_end": _ts(period.get("end")),
        "amount_usd": (inv.get("amount_paid") if inv.get("status") == "paid"
                       else inv.get("amount_due") or 0) / 100,
        "currency": (inv.get("currency") or "usd").upper(),
        "status": inv.get("status"),
        "url": inv.get("hosted_invoice_url"), "pdf": inv.get("invoice_pdf"),
    }


async def _checkout_plan(body: dict) -> tuple[dict, str, int]:
    plan = await get_plan(body.get("plan") or "")
    if plan["plan_id"] != body.get("plan") or not plan["purchasable"]:
        raise HTTPException(status_code=400, detail="Choose the Home or Pro plan.")
    interval = body.get("interval") or "month"
    if interval not in INTERVALS:
        raise HTTPException(status_code=400, detail="Billing period must be monthly or yearly.")
    return plan, interval, clamp_cameras(plan, body.get("cameras"))


@router.post("/checkout-session")
async def create_checkout_session(body: dict, admin: UserPublic = Depends(require_admin)):
    if not stripe_configured():
        raise HTTPException(status_code=503, detail="Card payments aren't switched on yet — please contact us to change your plan.")
    plan, interval, cameras = await _checkout_plan(body)

    db = get_db()
    org = await db.organizations.find_one({"org_id": admin.org_id})
    if org.get("stripe_subscription_id") and org.get("subscription_status") in ("active", "past_due"):
        # A second Checkout would start a second subscription and charge twice.
        raise HTTPException(status_code=409, detail="You already have a subscription — change it instead.")

    back = "/welcome" if body.get("return_to") == "welcome" else "/billing"
    price_id = await _price_id(plan, interval)
    stripe.api_key = settings.STRIPE_SECRET_KEY

    customer_id = org.get("stripe_customer_id")
    if not customer_id:
        customer = stripe.Customer.create(name=org["name"], email=admin.email, metadata={"org_id": admin.org_id})
        customer_id = customer.id
        await db.organizations.update_one({"org_id": admin.org_id}, {"$set": {"stripe_customer_id": customer_id}})

    meta = {"org_id": admin.org_id, "plan": plan["plan_id"], "interval": interval, "cameras": str(cameras)}
    session = stripe.checkout.Session.create(
        customer=customer_id,
        mode="subscription",
        line_items=[{"price": price_id, "quantity": cameras if plan["per_camera"] else 1}],
        success_url=f"{settings.FRONTEND_URL}{back}?checkout=success",
        cancel_url=f"{settings.FRONTEND_URL}{back}?checkout=cancelled",
        metadata=meta,
        subscription_data={"metadata": meta},
        allow_promotion_codes=True,
    )
    return {"url": session.url}


def _live_subscription(org: dict):
    if not stripe_configured():
        raise HTTPException(status_code=503, detail="Card payments aren't switched on yet — please contact us.")
    if not org.get("stripe_subscription_id") or org.get("subscription_status") not in ("active", "past_due"):
        raise HTTPException(status_code=400, detail="There's no paid subscription to change — choose a plan first.")
    stripe.api_key = settings.STRIPE_SECRET_KEY
    return stripe.Subscription.retrieve(org["stripe_subscription_id"])


@router.post("/subscription")
async def change_subscription(body: dict, admin: UserPublic = Depends(require_admin)):
    """Switch plan, billing period or number of cameras on a running subscription."""
    plan, interval, cameras = await _checkout_plan(body)
    db = get_db()
    org = await db.organizations.find_one({"org_id": admin.org_id})
    sub = _live_subscription(org)
    item = sub["items"]["data"][0]
    old_qty = item.get("quantity") or 1
    new_qty = cameras if plan["per_camera"] else 1
    same_price = (org.get("plan") == plan["plan_id"] and org.get("billing_interval") == interval)

    if same_price and new_qty == old_qty:
        return {"changed": False}
    # More cameras, or a bigger plan: start now and charge the difference now.
    # Fewer cameras on the same plan: keep what was paid for until renewal.
    reducing = same_price and new_qty < old_qty
    items = [{"id": item["id"], "price": await _price_id(plan, interval), "quantity": new_qty}]
    if reducing:
        stripe.Subscription.modify(sub["id"], items=items, proration_behavior="none")
    else:
        # The upgrade is only applied once its invoice is paid: with a declined
        # card Stripe keeps the old plan and nothing here changes. The database
        # follows from customer.subscription.updated, never from this request,
        # so no camera is granted before the money arrives.
        stripe.Subscription.modify(sub["id"], items=items, proration_behavior="always_invoice",
                                   payment_behavior="pending_if_incomplete")
    await account_events.record(
        db, admin.org_id, "subscription_changed",
        f"{admin.name} changed the plan to {plan['label']}"
        + (f" with {cameras} cameras" if plan["per_camera"] else "")
        + (", billed yearly" if interval == "year" else ", billed monthly")
        + (" — takes effect at renewal" if reducing else ""))
    return {"changed": True, "effective": "renewal" if reducing else "after_payment"}


@router.post("/cancel")
async def cancel_subscription(admin: UserPublic = Depends(require_admin)):
    """Cancel at the end of the period already paid for — no fee, no phone call."""
    db = get_db()
    org = await db.organizations.find_one({"org_id": admin.org_id})
    sub = _live_subscription(org)
    stripe.Subscription.modify(sub["id"], cancel_at_period_end=True)
    await db.organizations.update_one({"org_id": admin.org_id}, {"$set": {"cancel_at_period_end": True}})
    await account_events.record(db, admin.org_id, "subscription_changed",
                                f"{admin.name} cancelled the subscription. It stays active until the end of the period.")
    return {"cancel_at_period_end": True}


@router.post("/resume")
async def resume_subscription(admin: UserPublic = Depends(require_admin)):
    db = get_db()
    org = await db.organizations.find_one({"org_id": admin.org_id})
    sub = _live_subscription(org)
    stripe.Subscription.modify(sub["id"], cancel_at_period_end=False)
    await db.organizations.update_one({"org_id": admin.org_id}, {"$set": {"cancel_at_period_end": False}})
    await account_events.record(db, admin.org_id, "subscription_changed",
                                f"{admin.name} kept the subscription — it will renew as normal.")
    return {"cancel_at_period_end": False}


@router.post("/portal-session")
async def create_portal_session(admin: UserPublic = Depends(require_admin)):
    if not stripe_configured():
        raise HTTPException(status_code=503, detail="Billing is not configured yet")
    db = get_db()
    org = await db.organizations.find_one({"org_id": admin.org_id})
    if not org.get("stripe_customer_id"):
        raise HTTPException(status_code=400, detail="There's no payment set up yet — choose a paid plan first.")
    stripe.api_key = settings.STRIPE_SECRET_KEY
    session = stripe.billing_portal.Session.create(
        customer=org["stripe_customer_id"], return_url=f"{settings.FRONTEND_URL}/billing")
    return {"url": session.url}


# ── Webhook ─────────────────────────────────────────────────────────────────

def _sub_fields(sub: dict) -> dict:
    """Plan, period, cameras and renewal date from a Stripe subscription."""
    items = (sub.get("items") or {}).get("data") or [{}]
    item = items[0]
    price = item.get("price") or {}
    meta = {**(price.get("metadata") or {}), **(sub.get("metadata") or {})}
    # Newer Stripe API versions keep the period on the item, older on the sub.
    period_end = sub.get("current_period_end") or item.get("current_period_end")
    fields = {
        "stripe_subscription_id": sub.get("id"),
        "subscription_status": sub.get("status"),
        "cancel_at_period_end": bool(sub.get("cancel_at_period_end")),
    }
    plan_id = (price.get("metadata") or {}).get("plan_id") or meta.get("plan")
    if plan_id:
        fields["plan"] = plan_id
    interval = (price.get("recurring") or {}).get("interval") or meta.get("interval")
    if interval:
        fields["billing_interval"] = interval
    if item.get("quantity") and plan_id == "pro":
        fields["cameras"] = int(item["quantity"])
    elif plan_id:
        fields["cameras"] = None
    if period_end:
        fields["current_period_end"] = datetime.utcfromtimestamp(period_end)
    return fields


@router.post("/webhook")
async def stripe_webhook(request: Request):
    """Stripe calls this directly — auth is the signature, not a cookie.
    Each event is applied once: Stripe retries, and a replayed "payment failed"
    must not restart a grace period."""
    if not stripe_configured():
        raise HTTPException(status_code=503, detail="Billing is not configured")

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")
    stripe.api_key = settings.STRIPE_SECRET_KEY
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, settings.STRIPE_WEBHOOK_SECRET)
    except (ValueError, stripe.SignatureVerificationError):
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    db = get_db()
    if await db.stripe_events.find_one({"event_id": event["id"]}):
        return {"status": "duplicate"}
    await db.stripe_events.insert_one({"event_id": event["id"], "type": event["type"],
                                       "received_at": datetime.utcnow()})
    await apply_event(db, event)
    return {"status": "ok"}


async def apply_event(db, event: dict):
    kind = event["type"]
    data = event["data"]["object"]

    if kind == "checkout.session.completed":
        meta = data.get("metadata") or {}
        org_id = meta.get("org_id")
        if not org_id or not meta.get("plan"):
            return
        plan = await get_plan(meta["plan"])
        cameras = clamp_cameras(plan, meta.get("cameras"))
        await db.organizations.update_one({"org_id": org_id}, {"$set": {
            "plan": plan["plan_id"], "subscription_status": "active",
            "billing_interval": meta.get("interval", "month"),
            "cameras": cameras if plan["per_camera"] else None,
            "stripe_subscription_id": data.get("subscription"),
            "stripe_customer_id": data.get("customer"),
            "cancel_at_period_end": False, "grace_until": None, "plan_source": "stripe",
        }})
        await account_events.record(
            db, org_id, "subscription_changed",
            f"Subscribed to {plan['label']}" + (f" with {cameras} cameras" if plan["per_camera"] else "")
            + (", billed yearly" if meta.get("interval") == "year" else ", billed monthly"))

    elif kind in ("customer.subscription.created", "customer.subscription.updated"):
        org = await db.organizations.find_one({"stripe_customer_id": data.get("customer")})
        if not org:
            return
        fields = _sub_fields(data)
        if fields["subscription_status"] == "active":
            fields["grace_until"] = None
        elif fields["subscription_status"] == "past_due" and not org.get("grace_until"):
            # Usually set by invoice.payment_failed; Stripe does not promise
            # which of the two events arrives first.
            fields["grace_until"] = datetime.utcnow() + timedelta(days=subscription.PAST_DUE_GRACE_DAYS)
        await db.organizations.update_one({"org_id": org["org_id"]},
                                          {"$set": {**fields, "plan_source": "stripe"}})
        if org.get("subscription_status") != fields["subscription_status"]:
            await account_events.record(db, org["org_id"], "subscription_changed",
                                        f"Subscription is now {fields['subscription_status'].replace('_', ' ')}")

    elif kind == "customer.subscription.deleted":
        org = await db.organizations.find_one({"stripe_customer_id": data.get("customer")})
        if not org or org.get("stripe_subscription_id") not in (None, data.get("id")):
            return   # an old subscription ending must not cancel the current one
        await db.organizations.update_one({"org_id": org["org_id"]}, {"$set": {
            "plan": "free", "subscription_status": "canceled", "cameras": None,
            "cancel_at_period_end": False, "grace_until": None, "stripe_subscription_id": None}})
        await account_events.record(db, org["org_id"], "subscription_changed",
                                    "Subscription ended. FiremeX now watches 1 camera.")

    elif kind == "invoice.paid":
        org = await db.organizations.find_one({"stripe_customer_id": data.get("customer")})
        if not org:
            return
        amount = (data.get("amount_paid") or 0) / 100
        row = _invoice_row(data)
        await db.payments.update_one(
            {"id": row["id"]},
            {"$set": {**row, "org_id": org["org_id"],
                      "created": datetime.fromtimestamp(data.get("created") or 0, tz=timezone.utc).replace(tzinfo=None)}},
            upsert=True)
        if org.get("subscription_status") == "past_due":
            await db.organizations.update_one({"org_id": org["org_id"]},
                                              {"$set": {"subscription_status": "active", "grace_until": None}})
        if amount > 0:
            await account_events.record(db, org["org_id"], "payment_completed",
                                        f"Payment of ${amount:.2f} received")

    elif kind == "invoice.payment_failed":
        org = await db.organizations.find_one({"stripe_customer_id": data.get("customer")})
        if not org:
            return
        grace = org.get("grace_until") or datetime.utcnow() + timedelta(days=subscription.PAST_DUE_GRACE_DAYS)
        await db.organizations.update_one({"org_id": org["org_id"]},
                                          {"$set": {"subscription_status": "past_due", "grace_until": grace}})
        await account_events.record(
            db, org["org_id"], "subscription_changed",
            f"A payment of ${(data.get('amount_due') or 0) / 100:.2f} failed. Update your card by "
            f"{grace.strftime('%d %b')} to keep all your cameras.")
