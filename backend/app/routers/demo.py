from fastapi import APIRouter, Depends
from app.models import DemoRequest, DemoRequestCreate
from app.database import get_db
from app.rate_limit import rate_limiter
from app.services.notifications import send_demo_request_email

router = APIRouter(prefix="/demo-requests", tags=["demo-requests"])

DEMO_REQUEST_LIMIT = Depends(rate_limiter(max_attempts=5, window_seconds=3600))


@router.post("/", dependencies=[DEMO_REQUEST_LIMIT])
async def request_demo(body: DemoRequestCreate):
    db = get_db()
    request = DemoRequest(**body.model_dump())
    await db.demo_requests.insert_one(request.model_dump())
    await send_demo_request_email(request)
    return {"status": "received"}
