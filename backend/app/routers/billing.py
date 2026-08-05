import logging
from datetime import datetime
import stripe
from fastapi import APIRouter, Depends, HTTPException, Request

from app.config import settings
from app.database import get_db
from app.models import UserPublic, OrganizationPublic, PLAN_LIMITS
from app.plans import get_plan_limits, list_plans
from app.security import get_current_user, require_admin

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/billing", tags=["billing"])

# Monthly USD prices, in cents. Products/Prices are created (idempotently, via
# lookup_key) in Stripe on server startup — no dashboard access needed.
PLAN_PRICING = {
    "starter": {"amount": 4900,  "lookup_key": "firemex_starter_monthly"},
    "pro":     {"amount": 19900, "lookup_key": "firemex_pro_monthly"},
}

# plan -> Stripe Price ID, populated by bootstrap_prices() at startup.
_price_ids: dict[str, str] = {}


def stripe_configured() -> bool:
    return bool(settings.STRIPE_SECRET_KEY)


def bootstrap_prices_sync():
    """Idempotently ensure a Stripe Product+Price exists for each paid plan.
    Safe to call on every startup — looks up by lookup_key before creating."""
    if not stripe_configured():
        return
    stripe.api_key = settings.STRIPE_SECRET_KEY
    for plan, cfg in PLAN_PRICING.items():
        try:
            existing = stripe.Price.list(lookup_keys=[cfg["lookup_key"]], limit=1)
            if existing.data:
                _price_ids[plan] = existing.data[0].id
                continue
            product = stripe.Product.create(name=f"FiremeX {PLAN_LIMITS[plan]['label']}")
            price = stripe.Price.create(
                product=product.id,
                unit_amount=cfg["amount"],
                currency="usd",
                recurring={"interval": "month"},
                lookup_key=cfg["lookup_key"],
            )
            _price_ids[plan] = price.id
            logger.info(f"[stripe] Bootstrapped price for {plan}: {price.id}")
        except Exception:
            logger.exception(f"[stripe] Failed to bootstrap price for plan '{plan}'")


@router.get("/plans")
async def public_plans():
    """Public plan catalog for the marketing/pricing section — no auth. Reflects
    whatever the staff have set in the platform console (app/plans.py)."""
    plans = await list_plans()
    return {
        "plans": [
            {
                "plan_id": p["plan_id"], "label": p["label"], "price_usd": p["price_usd"],
                "max_cameras": p["max_cameras"], "max_users": p["max_users"],
                "features": p.get("features", []), "order": p.get("order", 0),
            }
            for p in plans
        ],
    }


@router.get("/status")
async def billing_status(user: UserPublic = Depends(get_current_user)):
    db = get_db()
    org = await db.organizations.find_one({"org_id": user.org_id})
    camera_count = await db.cameras.count_documents({"org_id": user.org_id})
    user_count = await db.users.count_documents({"org_id": user.org_id})

    # Plan catalog is DB-backed and staff-editable (see app/plans.py).
    plans = await list_plans()
    by_id = {p["plan_id"]: p for p in plans}
    current = by_id.get(org["plan"], by_id.get("trial"))

    return {
        "org": OrganizationPublic(**org),
        "usage": {"cameras": camera_count, "users": user_count},
        "limits": {"max_cameras": current["max_cameras"], "max_users": current["max_users"], "label": current["label"]},
        "stripe_configured": stripe_configured(),
        "plans": {
            p["plan_id"]: {
                "max_cameras": p["max_cameras"], "max_users": p["max_users"],
                "label": p["label"], "amount_usd": p["price_usd"], "features": p.get("features", []),
            }
            for p in plans if p["plan_id"] in PLAN_PRICING
        },
    }


@router.post("/checkout-session")
async def create_checkout_session(body: dict, admin: UserPublic = Depends(require_admin)):
    if not stripe_configured():
        raise HTTPException(status_code=503, detail="Billing is not configured yet — set STRIPE_SECRET_KEY in backend/.env")

    plan = body.get("plan")
    if plan not in PLAN_PRICING:
        raise HTTPException(status_code=400, detail=f"plan must be one of {list(PLAN_PRICING)}")

    price_id = _price_ids.get(plan)
    if not price_id:
        raise HTTPException(status_code=503, detail="Stripe price isn't ready yet — try again in a moment")

    stripe.api_key = settings.STRIPE_SECRET_KEY
    db = get_db()
    org = await db.organizations.find_one({"org_id": admin.org_id})

    customer_id = org.get("stripe_customer_id")
    if not customer_id:
        customer = stripe.Customer.create(name=org["name"], email=admin.email, metadata={"org_id": admin.org_id})
        customer_id = customer.id
        await db.organizations.update_one({"org_id": admin.org_id}, {"$set": {"stripe_customer_id": customer_id}})

    session = stripe.checkout.Session.create(
        customer=customer_id,
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=f"{settings.FRONTEND_URL}/billing?checkout=success",
        cancel_url=f"{settings.FRONTEND_URL}/billing?checkout=cancelled",
        metadata={"org_id": admin.org_id, "plan": plan},
    )
    return {"url": session.url}


@router.post("/portal-session")
async def create_portal_session(admin: UserPublic = Depends(require_admin)):
    if not stripe_configured():
        raise HTTPException(status_code=503, detail="Billing is not configured yet")

    db = get_db()
    org = await db.organizations.find_one({"org_id": admin.org_id})
    if not org.get("stripe_customer_id"):
        raise HTTPException(status_code=400, detail="No billing account yet — subscribe to a plan first")

    stripe.api_key = settings.STRIPE_SECRET_KEY
    session = stripe.billing_portal.Session.create(
        customer=org["stripe_customer_id"],
        return_url=f"{settings.FRONTEND_URL}/billing",
    )
    return {"url": session.url}


@router.post("/webhook")
async def stripe_webhook(request: Request):
    """Stripe calls this directly (not through the browser) — auth is the
    signature, not a session cookie. Requires `stripe listen --forward-to
    localhost:8000/billing/webhook` for local testing."""
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
    data = event["data"]["object"]

    if event["type"] == "checkout.session.completed":
        org_id = data.get("metadata", {}).get("org_id")
        plan = data.get("metadata", {}).get("plan")
        if org_id and plan:
            await db.organizations.update_one(
                {"org_id": org_id},
                {"$set": {
                    "plan": plan,
                    "subscription_status": "active",
                    "stripe_subscription_id": data.get("subscription"),
                }},
            )
            logger.info(f"[stripe] org {org_id} subscribed to {plan}")

    elif event["type"] in ("customer.subscription.updated", "customer.subscription.deleted"):
        customer_id = data.get("customer")
        status = data.get("status")   # active | past_due | canceled | ...
        update = {"subscription_status": status}
        if event["type"] == "customer.subscription.deleted" or status == "canceled":
            update["plan"] = "trial"
        current_period_end = data.get("current_period_end")
        if current_period_end:
            update["current_period_end"] = datetime.utcfromtimestamp(current_period_end)
        await db.organizations.update_one({"stripe_customer_id": customer_id}, {"$set": update})
        logger.info(f"[stripe] subscription update for customer {customer_id}: {status}")

    return {"status": "ok"}
