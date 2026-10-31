"""The last detections, each with its own evidence photo, for the History tab.

The per-camera snapshot (main.write_snapshot) is overwritten by every alert,
so on its own it can only ever show the most recent one. An operator looking
back at the evening — or a fire officer asking "what did it see at 20:17?" —
needs every detection with the picture that triggered it.

Each detection's annotated frame is copied to www/firemex/history/ (served by
Home Assistant at /local/firemex/history/) and listed, newest first, in
/data/detections.json. /data survives restarts and add-on updates; Home
Assistant forgets states the add-on set when IT restarts, so the list is the
source of truth and the sensor is republished from it on every start.

Only the newest MAX_ENTRIES are kept, photos included, so a camera that alerts
all night cannot fill the Home Assistant disk.
"""
import base64
import json
import logging
import os

logger = logging.getLogger("ha.history")

HISTORY_PATH = os.environ.get("HISTORY_PATH", "/data/detections.json")
MAX_ENTRIES = 30


def load(path: str = HISTORY_PATH) -> list[dict]:
    try:
        with open(path) as fh:
            entries = json.load(fh)
        return entries if isinstance(entries, list) else []
    except (OSError, ValueError):
        return []


def _save(entries: list[dict], path: str) -> None:
    tmp = path + ".part"
    with open(tmp, "w") as fh:
        json.dump(entries, fh)
    os.replace(tmp, path)


def record(event: dict, timestamp: str, snapshot_dir: str,
           path: str = HISTORY_PATH, max_entries: int = MAX_ENTRIES) -> list[dict]:
    """Add one detection (with its photo, if it has one) and return the list.

    Never raises: losing a history entry must not cost the live alert.
    """
    entries = load(path)
    slug = event["camera_id"].split(".", 1)[-1]
    stamp = timestamp[:19].replace("-", "").replace(":", "").replace("T", "_")
    photo = None
    try:
        if event.get("frame_b64"):
            folder = os.path.join(snapshot_dir, "history")
            os.makedirs(folder, exist_ok=True)
            name = f"{slug}_{stamp}.jpg"
            with open(os.path.join(folder, name), "wb") as fh:
                fh.write(base64.b64decode(event["frame_b64"]))
            photo = f"/local/firemex/history/{name}"

        entries.insert(0, {
            "time": timestamp,
            "camera": event["camera_name"],
            "entity_id": event["camera_id"],
            "hazard": event["hazard_type"],
            "confidence": round(float(event["confidence"]), 2),
            "photo": photo,
        })
        for old in entries[max_entries:]:
            if old.get("photo"):
                try:
                    os.remove(os.path.join(snapshot_dir, "history", os.path.basename(old["photo"])))
                except OSError:
                    pass
        entries = entries[:max_entries]
        _save(entries, path)
    except Exception as exc:
        logger.warning(f"could not record detection history: {exc}")
    return entries
