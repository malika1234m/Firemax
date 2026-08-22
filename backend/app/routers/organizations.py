from fastapi import APIRouter, Depends, HTTPException
from app.models import (DeploymentModeUpdate, OrganizationPublic, OrganizationUpdate,
                        UserPublic)
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
