from fastapi import APIRouter, Depends, HTTPException
from app.models import UserPublic, UserCreateByAdmin, UserRoleUpdate, User, NotificationPrefsUpdate
from app.plans import get_plan_limits
from app.database import get_db
from app.security import get_current_user, require_admin, hash_password

router = APIRouter(prefix="/users", tags=["users"])

VALID_ROLES = {"admin", "operator"}


@router.get("/", response_model=list[UserPublic])
async def list_users(admin: UserPublic = Depends(require_admin)):
    db = get_db()
    users = await db.users.find({"org_id": admin.org_id}).sort("created_at", 1).to_list(200)
    return [UserPublic(**u) for u in users]


@router.patch("/me/preferences", response_model=UserPublic)
async def update_my_preferences(body: NotificationPrefsUpdate, user: UserPublic = Depends(get_current_user)):
    db = get_db()
    updates = {f"notification_prefs.{k}": v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    result = await db.users.find_one_and_update(
        {"user_id": user.user_id}, {"$set": updates}, return_document=True
    )
    return UserPublic(**result)


@router.post("/", response_model=UserPublic)
async def add_user(body: UserCreateByAdmin, admin: UserPublic = Depends(require_admin)):
    if body.role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"role must be one of {sorted(VALID_ROLES)}")

    db = get_db()
    email = body.email.strip().lower()
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=409, detail="An account with this email already exists")

    org = await db.organizations.find_one({"org_id": admin.org_id})
    limits = await get_plan_limits(org["plan"])
    seat_count = await db.users.count_documents({"org_id": admin.org_id})
    if seat_count >= limits["max_users"]:
        raise HTTPException(
            status_code=402,
            detail=f"Your {limits['label']} plan is limited to {limits['max_users']} users. Upgrade to add more.",
        )

    user = User(
        org_id=admin.org_id,
        name=body.name.strip(),
        email=email,
        password_hash=hash_password(body.password),
        role=body.role,
    )
    await db.users.insert_one(user.model_dump())
    return UserPublic(**user.model_dump())


@router.patch("/{user_id}/role", response_model=UserPublic)
async def update_role(user_id: str, body: UserRoleUpdate, admin: UserPublic = Depends(require_admin)):
    if body.role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"role must be one of {sorted(VALID_ROLES)}")

    db = get_db()
    target = await db.users.find_one({"user_id": user_id, "org_id": admin.org_id})
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    if target["role"] == "admin" and body.role != "admin":
        remaining_admins = await db.users.count_documents({"org_id": admin.org_id, "role": "admin"})
        if remaining_admins <= 1:
            raise HTTPException(status_code=400, detail="Cannot demote the last remaining admin")

    await db.users.update_one({"user_id": user_id}, {"$set": {"role": body.role}})
    updated = await db.users.find_one({"user_id": user_id})
    return UserPublic(**updated)


@router.delete("/{user_id}")
async def remove_user(user_id: str, admin: UserPublic = Depends(require_admin)):
    db = get_db()
    target = await db.users.find_one({"user_id": user_id, "org_id": admin.org_id})
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    if user_id == admin.user_id:
        raise HTTPException(status_code=400, detail="You cannot delete your own account")

    if target["role"] == "admin":
        remaining_admins = await db.users.count_documents({"org_id": admin.org_id, "role": "admin"})
        if remaining_admins <= 1:
            raise HTTPException(status_code=400, detail="Cannot delete the last remaining admin")

    await db.users.delete_one({"user_id": user_id})
    return {"status": "deleted"}
