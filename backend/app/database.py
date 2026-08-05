from motor.motor_asyncio import AsyncIOMotorClient
from app.config import settings

client: AsyncIOMotorClient = None
db = None


async def connect_db():
    global client, db
    client = AsyncIOMotorClient(settings.MONGODB_URL)
    db = client[settings.DB_NAME]
    await db.organizations.create_index("org_id", unique=True)
    await db.organizations.create_index("stripe_customer_id")

    await db.alerts.create_index("timestamp")
    await db.alerts.create_index("org_id")
    await db.cameras.create_index("camera_id", unique=True)
    await db.cameras.create_index("org_id")
    await db.users.create_index("user_id", unique=True)
    await db.users.create_index("email", unique=True)
    await db.users.create_index("org_id")
    await db.shifts.create_index("user_id")
    await db.shifts.create_index("start_time")
    await db.shifts.create_index("org_id")
    await db.authority_contacts.create_index("org_id")

    # Password reset tokens: fast lookup by token, and a TTL index so expired
    # tokens are purged automatically instead of lingering in the DB forever.
    await db.password_reset_tokens.create_index("token", unique=True)
    await db.password_reset_tokens.create_index("expires_at", expireAfterSeconds=0)

    await db.platform_admins.create_index("admin_id", unique=True)
    await db.platform_admins.create_index("email", unique=True)

    await db.sites.create_index("site_id", unique=True)
    await db.sites.create_index("org_id")
    await db.sites.create_index("token_hash", unique=True)

    await db.plans.create_index("plan_id", unique=True)
    await db.complaints.create_index("org_id")
    await db.complaints.create_index("status")
    await db.complaints.create_index("created_at")


async def close_db():
    global client
    if client:
        client.close()


def get_db():
    return db
