"""Seed realistic sample alerts for an existing organization, so every
dashboard page has something to show. Cameras/users/shifts/authority
contacts are best created through the normal signup + admin UI/API (they're
subject to plan limits); this script only backfills alert history, which
the API has no bulk-insert path for.

Usage:
    cd backend && source .venv/bin/activate
    python scripts/seed_demo_data.py <org_id> <camera_id> <camera_name> [<camera_id2> <camera_name2>]
"""
import asyncio
import base64
import sys
from datetime import datetime, timedelta

import cv2
import numpy as np
from motor.motor_asyncio import AsyncIOMotorClient

sys.path.insert(0, ".")
from app.config import settings          # noqa: E402
from app.models import Alert             # noqa: E402


def synth_frame(label: str, confidence: float) -> str:
    """A small synthetic annotated JPEG so the Dashboard preview has
    something to render, without needing a real camera or fire footage."""
    img = np.full((240, 320, 3), (25, 20, 18), dtype=np.uint8)
    cv2.rectangle(img, (90, 70), (230, 190), (0, 0, 220), 3)
    cv2.putText(img, label.upper(), (95, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
    cv2.putText(img, f"{confidence:.0%}", (95, 210), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    _, jpeg = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 70])
    return base64.b64encode(jpeg.tobytes()).decode()


async def main():
    if len(sys.argv) < 4:
        print(__doc__)
        sys.exit(1)

    org_id = sys.argv[1]
    cameras = [(sys.argv[2], sys.argv[3])]
    if len(sys.argv) >= 6:
        cameras.append((sys.argv[4], sys.argv[5]))
    cam_a = cameras[0]
    cam_b = cameras[1] if len(cameras) > 1 else cameras[0]

    now = datetime.utcnow()

    alerts = [
        Alert(org_id=org_id, camera_id=cam_a[0], camera_name=cam_a[1],
              hazard_type="fire", confidence=0.94, zone="Warehouse A",
              timestamp=now - timedelta(hours=2),
              frame_b64=synth_frame("fire", 0.94)),

        Alert(org_id=org_id, camera_id=cam_a[0], camera_name=cam_a[1],
              hazard_type="gas_fire", confidence=0.87, zone="Warehouse A",
              status="in_progress", promoted_to_incident=True,
              promoted_at=now - timedelta(hours=5), timestamp=now - timedelta(hours=5),
              frame_b64=synth_frame("gas_fire", 0.87)),

        Alert(org_id=org_id, camera_id=cam_b[0], camera_name=cam_b[1],
              hazard_type="smoke", confidence=0.71, zone="Main Entrance",
              status="resolved", promoted_to_incident=True,
              resolution_verdict="false_alarm", resolution_remark="Fog machine test during a fire-drill rehearsal, not real smoke.",
              timestamp=now - timedelta(days=1, hours=3)),

        Alert(org_id=org_id, camera_id=cam_b[0], camera_name=cam_b[1],
              hazard_type="camera_offline", confidence=1.0, zone="Main Entrance",
              status="resolved", resolution_verdict="false_alarm",
              resolution_remark="Network switch rebooted, camera reconnected on its own.",
              timestamp=now - timedelta(days=3)),

        Alert(org_id=org_id, camera_id=cam_a[0], camera_name=cam_a[1],
              hazard_type="fire", confidence=0.98, zone="Warehouse A",
              status="resolved", promoted_to_incident=True,
              resolution_verdict="true_fire",
              resolution_remark="Confirmed electrical fire near pallet rack C3 — extinguished by on-site staff with a dry-chemical extinguisher before the fire department arrived.",
              timestamp=now - timedelta(days=6)),

        Alert(org_id=org_id, camera_id=cam_b[0], camera_name=cam_b[1],
              hazard_type="flame", confidence=0.65, zone="Main Entrance",
              status="resolved", resolution_verdict="false_alarm",
              resolution_remark="Sunset reflection off the glass entrance door.",
              timestamp=now - timedelta(days=8)),

        Alert(org_id=org_id, camera_id=cam_a[0], camera_name=cam_a[1],
              hazard_type="fire", confidence=0.91, zone="Warehouse A",
              status="resolved", promoted_to_incident=True,
              resolution_verdict="true_fire",
              resolution_remark="Small trash-bin fire, extinguished immediately. No damage.",
              timestamp=now - timedelta(days=12)),
    ]

    client = AsyncIOMotorClient(settings.MONGODB_URL)
    db = client[settings.DB_NAME]
    await db.alerts.insert_many([a.model_dump() for a in alerts])
    print(f"Inserted {len(alerts)} sample alerts for org {org_id}")
    client.close()


if __name__ == "__main__":
    asyncio.run(main())
