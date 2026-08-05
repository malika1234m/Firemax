import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from app.config import settings

# Point at an isolated database before anything else touches Motor, so
# tests never read or write the real firemax database.
settings.DB_NAME = "firemax_test"

from app.main import app                       # noqa: E402
from app.database import connect_db, close_db, get_db   # noqa: E402
from app.rate_limit import _attempts            # noqa: E402

TEST_COLLECTIONS = ["users", "alerts", "cameras", "shifts", "authority_contacts", "organizations", "password_reset_tokens", "demo_requests", "platform_admins", "plans", "complaints", "sites"]


@pytest_asyncio.fixture(autouse=True)
async def db():
    # Detection runs on edge agents now; the cloud API starts no pipelines, so
    # there's nothing local to tear down beyond the test database.
    await connect_db()
    database = get_db()
    yield database
    for name in TEST_COLLECTIONS:
        await database[name].delete_many({})
    _attempts.clear()
    await close_db()


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def client2():
    """A second, independent session — its own cookie jar — for testing
    cross-organization isolation (two different companies' admins)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def signup(client, org_name="Acme Fire Safety", name="Jordan Soto", email="jordan@firemex.io", password="testpass123"):
    return await client.post("/auth/signup", json={
        "org_name": org_name, "name": name, "email": email, "password": password,
    })
