"""Live-feed relay hub (cloud side).

Bridges two kinds of WebSocket:
  • browser viewers          →  /ws/{camera_id}      (operators watching a feed)
  • edge-agent connections   →  /agent/ws            (one per online site)

Since detection runs at the edge, the cloud has no frames of its own. When an
operator opens a feed, the hub asks the owning site's agent to start streaming
that camera; frames arrive over the agent's outbound connection and are fanned
out to the browser(s). When the last viewer leaves, the hub tells the agent to
stop — so an agent only ever uploads video while someone is actually watching.
"""
import logging
from collections import defaultdict

logger = logging.getLogger("relay")


class RelayHub:
    def __init__(self):
        self._viewers: dict[str, set] = defaultdict(set)   # camera_id -> {browser WebSocket}
        self._agents: dict[str, dict] = {}                 # site_id  -> {"ws":WebSocket, "org_id":str}

    # ── agents ──
    def add_agent(self, site_id: str, org_id: str, ws):
        self._agents[site_id] = {"ws": ws, "org_id": org_id}
        logger.info(f"agent connected: site={site_id}")

    def remove_agent(self, site_id: str):
        self._agents.pop(site_id, None)
        logger.info(f"agent disconnected: site={site_id}")

    def agent_online(self, org_id: str) -> bool:
        return any(a["org_id"] == org_id for a in self._agents.values())

    async def _signal(self, org_id: str, camera_id: str, kind: str):
        """Tell every online agent of this org to start/stop a camera stream."""
        for a in list(self._agents.values()):
            if a["org_id"] == org_id:
                try:
                    await a["ws"].send_json({"type": kind, "camera_id": camera_id})
                except Exception:
                    pass

    # ── browser viewers ──
    async def add_viewer(self, camera_id: str, org_id: str, ws):
        first = not self._viewers[camera_id]
        self._viewers[camera_id].add(ws)
        if first:
            await self._signal(org_id, camera_id, "stream_start")

    async def remove_viewer(self, camera_id: str, org_id: str, ws):
        self._viewers[camera_id].discard(ws)
        if not self._viewers[camera_id]:
            self._viewers.pop(camera_id, None)
            await self._signal(org_id, camera_id, "stream_stop")

    async def on_agent_frame(self, camera_id: str, payload: dict):
        """Fan a frame from an agent out to that camera's browser viewers."""
        dead = set()
        for ws in list(self._viewers.get(camera_id, ())):
            try:
                await ws.send_json(payload)
            except Exception:
                dead.add(ws)
        for ws in dead:
            self._viewers.get(camera_id, set()).discard(ws)

    def stats(self) -> dict:
        return {
            "total_connections": sum(len(s) for s in self._viewers.values()),
            "cameras_with_viewers": len([c for c, s in self._viewers.items() if s]),
            "agents_connected": len(self._agents),
        }


relay_hub = RelayHub()
