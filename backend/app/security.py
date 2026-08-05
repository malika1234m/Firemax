import hashlib
import secrets
from datetime import datetime, timedelta, timezone
import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request

from app.config import settings
from app.database import get_db
from app.models import UserPublic

COOKIE_NAME = "firemex_session"
# Platform (vendor) sessions use a SEPARATE cookie and a scoped token so a
# customer session can never be mistaken for a platform-admin session.
PLATFORM_COOKIE_NAME = "firemex_platform_session"
PLATFORM_SCOPE = "platform"
JWT_ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except ValueError:
        return False


def create_session_token(user_id: str, token_version: int = 0) -> str:
    payload = {
        "sub": user_id,
        "ver": token_version,
        "exp": datetime.now(timezone.utc) + timedelta(hours=settings.JWT_EXPIRE_HOURS),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_session_token(token: str) -> dict | None:
    """Returns the decoded claims dict, or None if the token is invalid/expired.
    Callers that only need the user id can read ['sub']."""
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None


async def get_current_user(request: Request) -> UserPublic:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[len("Bearer "):]

    claims = decode_session_token(token) if token else None
    user_id = claims.get("sub") if claims else None
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    db = get_db()
    user = await db.users.find_one({"user_id": user_id})
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    # Reject tokens issued before the last password change/reset. Tokens
    # predating this feature have no "ver" claim (treated as 0), matching the
    # default token_version, so existing valid sessions keep working.
    if claims.get("ver", 0) != user.get("token_version", 0):
        raise HTTPException(status_code=401, detail="Session expired — please sign in again")

    return UserPublic(**user)


async def require_admin(user: UserPublic = Depends(get_current_user)) -> UserPublic:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


# ── Platform (vendor) super-admin ────────────────────────────────────────────

def create_platform_token(admin_id: str) -> str:
    payload = {
        "sub": admin_id,
        "scope": PLATFORM_SCOPE,
        "exp": datetime.now(timezone.utc) + timedelta(hours=settings.JWT_EXPIRE_HOURS),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=JWT_ALGORITHM)


async def require_platform_admin(request: Request) -> dict:
    """Guards the /platform console. Only a token carrying the platform scope,
    read from the dedicated platform cookie, and matching a row in
    platform_admins passes — a customer session (different cookie, no scope,
    no matching row) can never reach these endpoints."""
    token = request.cookies.get(PLATFORM_COOKIE_NAME)
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[len("Bearer "):]

    claims = decode_session_token(token) if token else None
    if not claims or claims.get("scope") != PLATFORM_SCOPE:
        raise HTTPException(status_code=401, detail="Platform authentication required")

    db = get_db()
    admin = await db.platform_admins.find_one({"admin_id": claims.get("sub")})
    if not admin:
        raise HTTPException(status_code=401, detail="Platform authentication required")
    return admin


# ── Edge-agent authentication ────────────────────────────────────────────────
# Each site's agent presents a high-entropy enrollment token. We store only its
# SHA-256 (no brute-force risk on a 256-bit random token, so a fast hash is
# fine) and look the site up by that hash — the raw token is shown once at
# creation and lives only in the agent's config.

def generate_agent_token() -> str:
    return secrets.token_urlsafe(32)


def hash_agent_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


async def require_agent(request: Request) -> dict:
    raw = request.headers.get("x-agent-token")
    if not raw:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            raw = auth_header[len("Bearer "):]
    if not raw:
        raise HTTPException(status_code=401, detail="Agent token required")

    db = get_db()
    site = await db.sites.find_one({"token_hash": hash_agent_token(raw)})
    if not site:
        raise HTTPException(status_code=401, detail="Invalid agent token")
    return site
