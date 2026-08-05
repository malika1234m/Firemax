from fastapi import APIRouter, Depends, HTTPException
from app.models import AuthorityContact, AuthorityContactCreate, UserPublic
from app.database import get_db
from app.security import get_current_user, require_admin

router = APIRouter(prefix="/authorities", tags=["authorities"])

VALID_METHODS = {"sms", "call", "both"}


@router.get("/", response_model=list[AuthorityContact])
async def list_contacts(user: UserPublic = Depends(get_current_user)):
    db = get_db()
    contacts = await db.authority_contacts.find({"org_id": user.org_id}).sort("created_at", 1).to_list(50)
    return [AuthorityContact(**c) for c in contacts]


@router.post("/", response_model=AuthorityContact)
async def add_contact(body: AuthorityContactCreate, admin: UserPublic = Depends(require_admin)):
    if body.notify_via not in VALID_METHODS:
        raise HTTPException(status_code=400, detail=f"notify_via must be one of {sorted(VALID_METHODS)}")
    db = get_db()
    contact = AuthorityContact(org_id=admin.org_id, **body.model_dump())
    await db.authority_contacts.insert_one(contact.model_dump())
    return contact


@router.delete("/{contact_id}")
async def remove_contact(contact_id: str, admin: UserPublic = Depends(require_admin)):
    db = get_db()
    result = await db.authority_contacts.delete_one({"contact_id": contact_id, "org_id": admin.org_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Contact not found")
    return {"status": "deleted"}
