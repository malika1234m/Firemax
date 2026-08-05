from fastapi import APIRouter, Depends, HTTPException
from app.models import OrganizationPublic, OrganizationUpdate, UserPublic
from app.database import get_db
from app.security import get_current_user, require_admin

router = APIRouter(prefix="/organizations", tags=["organizations"])


@router.get("/me", response_model=OrganizationPublic)
async def my_organization(user: UserPublic = Depends(get_current_user)):
    db = get_db()
    org = await db.organizations.find_one({"org_id": user.org_id})
    return OrganizationPublic(**org)


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
