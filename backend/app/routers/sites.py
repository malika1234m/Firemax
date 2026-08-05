from fastapi import APIRouter, Depends, HTTPException
from app.models import Site, SiteCreate, SitePublic, UserPublic
from app.database import get_db
from app.security import require_admin, generate_agent_token, hash_agent_token

router = APIRouter(prefix="/sites", tags=["sites"])


@router.get("/", response_model=list[SitePublic])
async def list_sites(admin: UserPublic = Depends(require_admin)):
    db = get_db()
    sites = await db.sites.find({"org_id": admin.org_id}).sort("created_at", 1).to_list(200)
    return [SitePublic(**s) for s in sites]


@router.post("/")
async def create_site(body: SiteCreate, admin: UserPublic = Depends(require_admin)):
    """Creates a site and returns its enrollment token ONCE. The token is what
    the edge agent uses to authenticate; it's stored hashed and never shown
    again — rotate it if lost."""
    db = get_db()
    raw = generate_agent_token()
    site = Site(org_id=admin.org_id, name=body.name.strip(), token_hash=hash_agent_token(raw))
    await db.sites.insert_one(site.model_dump())
    return {"site": SitePublic(**site.model_dump()), "enrollment_token": raw}


@router.post("/{site_id}/rotate-token")
async def rotate_token(site_id: str, admin: UserPublic = Depends(require_admin)):
    db = get_db()
    raw = generate_agent_token()
    result = await db.sites.find_one_and_update(
        {"site_id": site_id, "org_id": admin.org_id},
        {"$set": {"token_hash": hash_agent_token(raw)}},
        return_document=True,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Site not found")
    return {"site": SitePublic(**result), "enrollment_token": raw}


@router.delete("/{site_id}")
async def delete_site(site_id: str, admin: UserPublic = Depends(require_admin)):
    db = get_db()
    result = await db.sites.delete_one({"site_id": site_id, "org_id": admin.org_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Site not found")
    return {"status": "deleted"}
