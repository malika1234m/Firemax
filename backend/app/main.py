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


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.JWT_SECRET == DEFAULT_JWT_SECRET:
        logger.warning(
            "JWT_SECRET is still the default placeholder — every login session is "
            "signed with a publicly-known key. Set a real JWT_SECRET in backend/.env "
            "before exposing this server beyond localhost."
        )

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
        online_sites = await get_db().sites.count_documents({"status": "online"})

    return {
        "status": "ok" if db_connected else "degraded",
        "database_connected": db_connected,
        "online_sites": online_sites,
    }
