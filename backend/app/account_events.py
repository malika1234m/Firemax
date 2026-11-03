"""Account activity shown on the customer's Overview page.

Only events about the ACCOUNT are recorded here — tokens, Home Assistant
installations, subscription and payments. Detection events never are: fire
detection lives in the customer's Home Assistant, and the website deliberately
knows nothing about cameras or alerts.
"""
from datetime import datetime, timezone

KINDS = {
    "token_generated",
    "token_revoked",
    "ha_connected",
    "ha_removed",
    "subscription_changed",
    "payment_completed",
    "setup_completed",
}


async def record(db, org_id: str, kind: str, message: str) -> None:
    assert kind in KINDS, kind
    await db.account_events.insert_one({
        "org_id": org_id, "kind": kind, "message": message,
        "at": datetime.now(timezone.utc),
    })


async def recent(db, org_id: str, limit: int = 20) -> list[dict]:
    # _id breaks ties: events written in the same millisecond (revoking the old
    # token, then generating the new one) keep the order they happened in.
    rows = await db.account_events.find({"org_id": org_id}) \
        .sort([("at", -1), ("_id", -1)]).to_list(limit)
    return [{k: v for k, v in r.items() if k != "_id"} for r in rows]
