#!/usr/bin/env bash
# Demonstrate the fully-local Home Assistant add-on on this Mac.
#
# Add-ons only run under the Home Assistant Supervisor, which HA Container does
# not have — so this stands up a stub Home Assistant (ha_agent/fake_ha.py),
# runs the REAL add-on against it, and replays what Home Assistant received.
# Every part except Home Assistant itself is the actual shipping code.
#
#   ./ha_agent/demo.sh            # ~60s
#   ./ha_agent/demo.sh 30         # shorter
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_SECONDS="${1:-60}"
WORK="$(mktemp -d)"
RECEIPTS="$WORK/receipts.jsonl"
PY="$ROOT/backend/.venv/bin/python"

cleanup() { kill "${HA_PID:-}" "${AGENT_PID:-}" 2>/dev/null || true; }
trap cleanup EXIT

rule() { printf '\n%s\n  %s\n%s\n' "$(printf '═%.0s' {1..72})" "$1" "$(printf '═%.0s' {1..72})"; }

rule "STEP 1 — Home Assistant, with cameras from its own integrations"
RECEIPTS="$RECEIPTS" "$PY" "$ROOT/ha_agent/fake_ha.py" >"$WORK/ha.log" 2>&1 &
HA_PID=$!
sleep 3
curl -s http://127.0.0.1:8899/api/states | "$PY" -c "
import json,sys
for s in json.load(sys.stdin):
    if s['entity_id'].startswith('camera.'):
        print(f\"    {s['entity_id']:26} {s['attributes'].get('friendly_name','—'):16} state={s['state']}\")
"

rule "STEP 2 — Install the add-on and press Start (no token, no account)"
cat > "$WORK/options.json" <<'J'
{"cameras": [], "confidence_threshold": 0.5, "alert_cooldown_seconds": 10,
 "detector_mode": "yolo", "model_url": "", "model_sha256": "",
 "process_fps": 2, "clear_after_seconds": 12}
J
PYTHONPATH="$ROOT/edge:$ROOT/backend" \
HA_API_URL="http://127.0.0.1:8899/api" \
SUPERVISOR_TOKEN="demo" \
OPTIONS_PATH="$WORK/options.json" \
MODEL_PATH="$ROOT/backend/models/fire_model.pt" \
"$PY" -m ha_agent.main >"$WORK/agent.log" 2>&1 &
AGENT_PID=$!

sleep 12
grep -E "add-on v|Detector:|skipping|camera added|watching" "$WORK/agent.log" | sed 's/^/    /' || true

echo
echo "    running detection for ${RUN_SECONDS}s …"
sleep "$RUN_SECONDS"
kill "$AGENT_PID" 2>/dev/null || true
sleep 2

rule "STEP 3 — Detected on this machine (no cloud involved)"
grep "HAZARD" "$WORK/agent.log" | grep "ha.main" | sed 's/.*WARNING/    /' || echo "    (none)"

rule "STEP 4 — What Home Assistant received back"
"$PY" "$ROOT/ha_agent/replay.py" "$RECEIPTS"
