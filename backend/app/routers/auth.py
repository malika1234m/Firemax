import logging
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Response
from app.database import get_db
from app.config import settings
from app.models import (
    SignupRequest, LoginRequest, UserPublic, User, Organization, ChangePasswordRequest,
    ForgotPasswordRequest, ResetPasswordRequest, PasswordResetToken,
)
from app.security import (
    hash_password, verify_password, create_session_token,
    get_current_user, COOKIE_NAME,
)
from app.rate_limit import rate_limiter
from app.services.notifications import send_password_reset_email

logger = logging.getLogger(__name__)

TRIAL_DAYS = 14
RESET_TOKEN_TTL_MINUTES = 60

router = APIRouter(prefix="/auth", tags=["auth"])

# Deliberately generous but bounded: stops credential-stuffing / mass account
# creation without locking out a real user who fat-fingers a password.
LOGIN_LIMIT  = Depends(rate_limiter(max_attempts=8, window_seconds=60))
SIGNUP_LIMIT = Depends(rate_limiter(max_attempts=5, window_seconds=3600))
CHANGE_PASSWORD_LIMIT = Depends(rate_limiter(max_attempts=5, window_seconds=300))
FORGOT_PASSWORD_LIMIT = Depends(rate_limiter(max_attempts=5, window_seconds=900))
RESET_PASSWORD_LIMIT  = Depends(rate_limiter(max_attempts=10, window_seconds=900))

# A bcrypt hash of a throwaway value. When a login names an email that doesn't
# exist, we verify against this so the response takes the same ~time as a real
# (wrong-password) attempt — closing the login timing side-channel that would
# otherwise let an attacker enumerate which emails are registered.
_DUMMY_HASH = hash_password("timing-equalizer-not-a-real-password")


def _set_session_cookie(response: Response, user_id: str, token_version: int = 0):
    response.set_cookie(
        key=COOKIE_NAME,
        value=create_session_token(user_id, token_version),
        max_age=settings.JWT_EXPIRE_HOURS * 3600,
        httponly=True,
        samesite="lax",
        secure=settings.COOKIE_SECURE,
        path="/",
    )


@router.post("/signup", response_model=UserPublic, dependencies=[SIGNUP_LIMIT])
async def signup(body: SignupRequest, response: Response):
    """Every signup creates a brand-new organization — there is no such thing
    as joining an existing one this way. To add teammates to an org, its
    admin creates their account from the Users page (POST /users/)."""
    db = get_db()
    email = body.email.strip().lower()

    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=409, detail="An account with this email already exists")

    org = Organization(
        name=body.org_name.strip(),
        plan="trial",
        subscription_status="trialing",
        trial_ends_at=datetime.utcnow() + timedelta(days=TRIAL_DAYS),
    )
    await db.organizations.insert_one(org.model_dump())

    user = User(
        org_id=org.org_id,
        name=body.name.strip(),
        email=email,
        password_hash=hash_password(body.password),
        role="admin",
    )
    await db.users.insert_one(user.model_dump())

    _set_session_cookie(response, user.user_id, user.token_version)
    return UserPublic(**user.model_dump())


@router.post("/login", response_model=UserPublic, dependencies=[LOGIN_LIMIT])
async def login(body: LoginRequest, response: Response):
    db = get_db()
    email = body.email.strip().lower()
    user = await db.users.find_one({"email": email})

    # Always run a bcrypt verify (against a dummy hash for unknown emails) so
    # the timing is indistinguishable whether or not the email exists.
    password_ok = verify_password(body.password, user["password_hash"] if user else _DUMMY_HASH)
    if not user or not password_ok:
        raise HTTPException(status_code=401, detail="Incorrect email or password")

    _set_session_cookie(response, user["user_id"], user.get("token_version", 0))
    return UserPublic(**user)


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"status": "logged_out"}


@router.get("/me", response_model=UserPublic)
async def me(user: UserPublic = Depends(get_current_user)):
    return user


@router.post("/change-password", dependencies=[CHANGE_PASSWORD_LIMIT])
async def change_password(body: ChangePasswordRequest, response: Response, user: UserPublic = Depends(get_current_user)):
    db = get_db()
    current = await db.users.find_one({"user_id": user.user_id})
    if not verify_password(body.current_password, current["password_hash"]):
        raise HTTPException(status_code=401, detail="Current password is incorrect")

    # Bump token_version so every previously-issued session (e.g. a stolen
    # cookie) is invalidated, then re-issue a fresh cookie for THIS session so
    # the user who just changed their own password stays signed in here.
    new_version = current.get("token_version", 0) + 1
    await db.users.update_one(
        {"user_id": user.user_id},
        {"$set": {"password_hash": hash_password(body.new_password), "token_version": new_version}},
    )
    _set_session_cookie(response, user.user_id, new_version)
    return {"status": "password_changed"}


@router.post("/forgot-password", dependencies=[FORGOT_PASSWORD_LIMIT])
async def forgot_password(body: ForgotPasswordRequest):
    """Always returns the same response whether or not the email exists, so
    this endpoint can't be used to enumerate registered accounts."""
    db = get_db()
    email = body.email.strip().lower()
    user = await db.users.find_one({"email": email})

    if user:
        token = PasswordResetToken(
            user_id=user["user_id"],
            expires_at=datetime.utcnow() + timedelta(minutes=RESET_TOKEN_TTL_MINUTES),
        )
        await db.password_reset_tokens.insert_one(token.model_dump())
        reset_link = f"{settings.FRONTEND_URL}/reset-password?token={token.token}"
        sent = await send_password_reset_email(email, reset_link)
        if not sent:
            logger.info(f"[dev] SMTP not configured — password reset link for {email}: {reset_link}")

    return {"status": "if_account_exists_email_sent"}


@router.post("/reset-password", dependencies=[RESET_PASSWORD_LIMIT])
async def reset_password(body: ResetPasswordRequest):
    db = get_db()
    record = await db.password_reset_tokens.find_one({"token": body.token})

    if not record or record["used"] or record["expires_at"] < datetime.utcnow():
        raise HTTPException(status_code=400, detail="This reset link is invalid or has expired")

    # Bump token_version to kill every existing session — a password reset is
    # exactly the "I've been compromised" case where lingering sessions must die.
    await db.users.update_one(
        {"user_id": record["user_id"]},
        {"$set": {"password_hash": hash_password(body.new_password)}, "$inc": {"token_version": 1}},
    )
    await db.password_reset_tokens.update_one({"token": body.token}, {"$set": {"used": True}})
    return {"status": "password_reset"}
