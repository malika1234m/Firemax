from fastapi import APIRouter, Depends, HTTPException
from app.models import Shift, ShiftCreate, UserPublic
from app.database import get_db
from app.security import get_current_user, require_admin

router = APIRouter(prefix="/shifts", tags=["shifts"])


@router.get("/", response_model=list[Shift])
async def list_shifts(user: UserPublic = Depends(get_current_user)):
    db = get_db()
    # Admins see the full org schedule; operators only see their own assigned shifts.
    query = {"org_id": user.org_id} if user.role == "admin" else {"org_id": user.org_id, "user_id": user.user_id}
    shifts = await db.shifts.find(query).sort("start_time", 1).to_list(500)
    return [Shift(**s) for s in shifts]


@router.post("/", response_model=Shift)
async def add_shift(body: ShiftCreate, admin: UserPublic = Depends(require_admin)):
    db = get_db()
    target_user = await db.users.find_one({"user_id": body.user_id, "org_id": admin.org_id})
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    if body.end_time <= body.start_time:
        raise HTTPException(status_code=400, detail="end_time must be after start_time")

    shift = Shift(org_id=admin.org_id, **body.model_dump(), user_name=target_user["name"])
    await db.shifts.insert_one(shift.model_dump())
    return shift


@router.delete("/{shift_id}")
async def remove_shift(shift_id: str, admin: UserPublic = Depends(require_admin)):
    db = get_db()
    result = await db.shifts.delete_one({"shift_id": shift_id, "org_id": admin.org_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Shift not found")
    return {"status": "deleted"}
