"""Thin HTTP client for the FiremeX agent gateway.

Every call is outbound (agent → cloud) and carries the site token, so no
inbound ports need to be opened on the customer's firewall.
"""
import logging
import httpx

logger = logging.getLogger("edge.cloud")


class CloudClient:
    def __init__(self, base_url: str, token: str):
        self.base_url = base_url
        self.headers = {"X-Agent-Token": token}

    def get_config(self) -> dict:
        r = httpx.get(f"{self.base_url}/agent/config", headers=self.headers, timeout=10.0)
        r.raise_for_status()
        return r.json()

    def post_heartbeat(self, agent_version: str, pipelines: list[dict]) -> bool:
        try:
            r = httpx.post(
                f"{self.base_url}/agent/heartbeat",
                headers=self.headers,
                json={"agent_version": agent_version, "pipelines": pipelines},
                timeout=10.0,
            )
            r.raise_for_status()
            return True
        except Exception as exc:
            logger.warning(f"heartbeat failed: {exc}")
            return False

    def post_events(self, events: list[dict]) -> int:
        """Returns how many events the cloud accepted; 0 on failure (caller
        keeps them buffered to retry)."""
        if not events:
            return 0
        try:
            r = httpx.post(f"{self.base_url}/agent/events", headers=self.headers, json=events, timeout=15.0)
            r.raise_for_status()
            return r.json().get("created", 0)
        except Exception as exc:
            logger.warning(f"event post failed ({len(events)} queued): {exc}")
            return 0
