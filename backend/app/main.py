import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import connect_db, close_db, get_db
from app.routers import cameras, alerts, ws, users, home_assistant, auth, shifts, authorities, billing, organizations, demo, platform, support, sites, agent
from app.routers.billing import bootstrap_prices_sync

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DEFAULT_JWT_SECRET = "dev-insecure-secret-change-me"


async def _bootstrap_platform_admin():
    """Create the internal FiremeX platform super-admin from env on startup if
    configured and not already present. There is no self-serve signup for this
    identity — it's provisioned out-of-band by us, never by a customer."""
    if not (settings.PLATFORM_ADMIN_EMAIL and settings.PLATFORM_ADMIN_PASSWORD):
        return
    from app.security import hash_password
    from app.models import PlatformAdmin
    db = get_db()
    email = settings.PLATFORM_ADMIN_EMAIL.strip().lower()
    if await db.platform_admins.find_one({"email": email}):
        return
    admin = PlatformAdmin(
        email=email, name="FiremeX Platform Admin",
        password_hash=hash_password(settings.PLATFORM_ADMIN_PASSWORD),
    )
    await db.platform_admins.insert_one(admin.model_dump())
    logger.info(f"[platform] Bootstrapped platform admin: {email}")


def _production_config_problems() -> list[str]:
    """Configuration that is merely noisy in development but unsafe once the
    server is reachable from the internet. Returns a human-readable list."""
    problems = []

    if settings.JWT_SECRET == DEFAULT_JWT_SECRET:
        problems.append(
            "JWT_SECRET is the default placeholder — sessions would be signed with a "
            "publicly-known key. Generate one: python -c \"import secrets; print(secrets.token_urlsafe(48))\""
        )
    if not settings.COOKIE_SECURE:
        problems.append(
            "COOKIE_SECURE is false — the session cookie would be sent over plaintext HTTP."
        )
    if not settings.SECRETS_ENCRYPTION_KEY:
        problems.append(
            "SECRETS_ENCRYPTION_KEY is unset — per-org Home Assistant tokens cannot be "
            "encrypted at rest, and saving an HA connection will fail."
        )
    if settings.FRONTEND_URL.startswith("http://"):
        problems.append(
            f"FRONTEND_URL is plaintext ({settings.FRONTEND_URL}) — the dashboard forces "
            "wss:// for the live feed, so it must be served over https://."
        )
    local = [o for o in settings.CORS_ORIGINS if "localhost" in o or "127.0.0.1" in o]
    if local:
        problems.append(f"CORS_ORIGINS still contains development origins: {local}")

    return problems


@asynccontextmanager
async def lifespan(app: FastAPI):
    problems = _production_config_problems()
    if settings.ENVIRONMENT == "production":
        # Refuse to start rather than come up subtly insecure.
        if problems:
            raise RuntimeError(
                "Refusing to start with ENVIRONMENT=production and unsafe configuration:\n  - "
                + "\n  - ".join(problems)
            )
        logger.info("[config] Production configuration checks passed.")
    else:
        for problem in problems:
            logger.warning(f"[config] {problem}")

    await connect_db()
    await _bootstrap_platform_admin()
    from app.plans import seed_plans
    await seed_plans()

    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, bootstrap_prices_sync)

    # Detection no longer runs in the cloud — each site's edge agent runs it on
    # the customer's own network and reports events/health via /agent/*. The
    # cloud is now a pure control plane (no OpenCV/YOLO in this process).
    yield

    await close_db()


app = FastAPI(title="Firemax API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(cameras.router)
app.include_router(alerts.router)
app.include_router(ws.router)
app.include_router(users.router)
app.include_router(home_assistant.router)
app.include_router(shifts.router)
app.include_router(authorities.router)
app.include_router(billing.router)
app.include_router(organizations.router)
app.include_router(demo.router)
app.include_router(platform.router)
app.include_router(support.router)
app.include_router(sites.router)
app.include_router(agent.router)


@app.get("/health")
async def health():
    try:
        await get_db().command("ping")
        db_connected = True
    except Exception:
        db_connected = False

    online_sites = 0
    if db_connected:
        # By recent heartbeat — the stored "online" flag is set on heartbeat and
        # never cleared, so counting it would report dead agents as healthy.
        from datetime import datetime, timedelta
        from app.models import SITE_OFFLINE_AFTER_SECONDS
        online_sites = await get_db().sites.count_documents({
            "last_seen_at": {"$gte": datetime.utcnow() - timedelta(seconds=SITE_OFFLINE_AFTER_SECONDS)}
        })

    return {
        "status": "ok" if db_connected else "degraded",
        "database_connected": db_connected,
        "online_sites": online_sites,
    }
