"""Replay what Home Assistant received from the add-on, and show which of those
would actually have triggered the automation in ha_automation.yaml.

    python ha_agent/replay.py /tmp/receipts.jsonl

The filter matters: FiremeX raises every hazard class it can detect, but the
example automation deliberately acts only on fire/smoke/flame. This makes that
gap visible rather than leaving it as a line of YAML nobody reads.
"""
import json, sys, datetime

receipts = [json.loads(l) for l in open(sys.argv[1]) if l.strip()]
t0 = receipts[0]["t"] if receipts else 0

# The condition from ha_automation.yaml in the repo.
AUTOMATION_FIRES_ON = {"fire", "smoke", "flame"}

print("\n\033[1m  TIME   WHAT HOME ASSISTANT RECEIVED\033[0m")
print("  " + "─" * 76)

seen_hazards = 0
for r in receipts:
    dt = r["t"] - t0
    path, body = r["path"], r["body"]
    stamp = f"+{dt:05.1f}s"

    if path.startswith("/api/events/"):
        event = path.rsplit("/", 1)[1]
        h = body["hazard_type"]
        fires = h in AUTOMATION_FIRES_ON
        seen_hazards += 1
        print(f"  {stamp}  \033[1mevent\033[0m   {event}")
        print(f"           hazard_type={h}  camera={body['camera_name']}  "
              f"confidence={body['confidence']:.0%}")
        print(f"           → automation condition (fire/smoke/flame): "
              + ("\033[1mFIRES\033[0m — siren, lights, notify" if fires
                 else "does not fire (filtered out)"))
    elif path.startswith("/api/states/"):
        entity = path.rsplit("/", 1)[1]
        state = body["state"]
        colour = "\033[1m" if state != "clear" else ""
        print(f"  {stamp}  state   {entity} = {colour}{state}\033[0m")
    elif path.startswith("/api/webhook/"):
        wh = path.rsplit("/", 1)[1]
        print(f"  {stamp}  webhook {wh}")

print("  " + "─" * 76)
final = [r for r in receipts if r["path"].startswith("/api/states/")]
if final:
    print(f"  final sensor.firemex_hazard = {final[-1]['body']['state']}")
print(f"  {seen_hazards} hazard event(s) delivered to Home Assistant\n")
