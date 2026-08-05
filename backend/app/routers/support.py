from fastapi import APIRouter, Depends
from app.models import Complaint, ComplaintCreate, UserPublic
from app.database import get_db
from app.security import get_current_user
from app.rate_limit import rate_limiter

router = APIRouter(prefix="/support", tags=["support"])

VALID_CATEGORIES = {"general", "billing", "detection", "technical", "other"}
COMPLAINT_LIMIT = Depends(rate_limiter(max_attempts=10, window_seconds=3600))


@router.post("/complaints", response_model=Complaint, dependencies=[COMPLAINT_LIMIT])
async def submit_complaint(body: ComplaintCreate, user: UserPublic = Depends(get_current_user)):
    db = get_db()
    org = await db.organizations.find_one({"org_id": user.org_id})
    complaint = Complaint(
        org_id=user.org_id,
        org_name=org["name"] if org else "",
        user_id=user.user_id,
        user_name=user.name,
        user_email=user.email,
        subject=body.subject.strip(),
        message=body.message.strip(),
        category=body.category if body.category in VALID_CATEGORIES else "general",
    )
    await db.complaints.insert_one(complaint.model_dump())
    return complaint


@router.get("/complaints", response_model=list[Complaint])
async def my_complaints(user: UserPublic = Depends(get_current_user)):
    # Scoped to the caller's org — a company sees the tickets it has filed.
    db = get_db()
    items = await db.complaints.find({"org_id": user.org_id}).sort("created_at", -1).to_list(200)
    return [Complaint(**c) for c in items]
