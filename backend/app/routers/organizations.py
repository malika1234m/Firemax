from fastapi import APIRouter, Depends, HTTPException
from app import account_events
from app.models import (AccountEventPublic, DeploymentModeUpdate, OnboardingUpdate,
                        OrganizationPublic, OrganizationUpdate, UserPublic)
from app.database import get_db
from app.security import get_current_user, require_admin

router = APIRouter(prefix="/organizations", tags=["organizations"])


@router.get("/me", response_model=OrganizationPublic)
async def my_organization(user: UserPublic = Depends(get_current_user)):
    db = get_db()
    org = await db.organizations.find_one({"org_id": user.org_id})
    return OrganizationPublic(**org)


@router.put("/me/deployment-mode", response_model=OrganizationPublic)
async def set_deployment_mode(body: DeploymentModeUpdate,
                              admin: UserPublic = Depends(require_admin)):
    """Record how this customer runs FiremeX — the Home Assistant add-on or the
    standalone edge agent.

    Deliberately re-settable: someone who starts with the add-on and later moves
    to dedicated hardware should not need support to change it, and the only
    thing it drives is which setup guide they see.
    """
    db = get_db()
    result = await db.organizations.find_one_and_update(
        {"org_id": admin.org_id},
        {"$set": {"deployment_mode": body.deployment_mode}},
        return_document=True,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Organization not found")
    return OrganizationPublic(**result)


@router.put("/me/onboarding", response_model=OrganizationPublic)
async def save_onboarding(body: OnboardingUpdate, admin: UserPublic = Depends(require_admin)):
    """Remember how far first-time setup got, so it can be resumed later.

    Setting up means the Home Assistant add-on — the only way FiremeX runs for
    customers of this website — so the deployment mode is recorded with it.
    """
    db = get_db()
    org = await db.organizations.find_one({"org_id": admin.org_id})
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    update = {"onboarding_step": body.step}
    if org.get("deployment_mode", "unset") == "unset":
        update["deployment_mode"] = "home_assistant"
    first_completion = body.completed and not org.get("onboarding_completed")
    if body.completed:
        update["onboarding_completed"] = True
    result = await db.organizations.find_one_and_update(
        {"org_id": admin.org_id}, {"$set": update}, return_document=True)
    if first_completion:
        await account_events.record(db, admin.org_id, "setup_completed",
                                    f"{admin.name} finished setting up FiremeX")
    return OrganizationPublic(**result)


@router.get("/me/activity", response_model=list[AccountEventPublic])
async def my_activity(user: UserPublic = Depends(get_current_user)):
    """Recent account events: tokens, Home Assistant connections, subscription
    and payments. Never detections — those belong to Home Assistant."""
    return [AccountEventPublic(**e) for e in await account_events.recent(get_db(), user.org_id)]


@router.patch("/me", response_model=OrganizationPublic)
async def update_my_organization(body: OrganizationUpdate, admin: UserPublic = Depends(require_admin)):
    db = get_db()
    updates = {k: v.strip() if isinstance(v, str) else v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    result = await db.organizations.find_one_and_update(
        {"org_id": admin.org_id}, {"$set": updates}, return_document=True
    )
    # Detection-tuning changes propagate to each site's edge agent on its next
    # /agent/config poll — no live push from the cloud is needed.
    return OrganizationPublic(**result)
