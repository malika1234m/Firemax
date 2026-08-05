"""Live-feed relay client (edge side).

Maintains a persistent OUTBOUND WebSocket to the cloud (/agent/ws). Over it:
  • receives stream_start / stream_stop commands (which cameras an operator is
    watching) and calls a callback to toggle per-camera frame emission,
  • sends frames the pipeline hands it, but only for cameras currently being
    watched — so we never upload video unless someone's looking.

Runs in its own thread with its own asyncio loop, so it coexists with the
agent's synchronous detection threads. Auto-reconnects on drop.
"""
import asyncio
import logging
import threading
import queue

import websockets

logger = logging.getLogger("edge.relay")


class RelayClient:
    def __init__(self, cloud_url: str, token: str, on_command):
        # cloud_url is http(s); derive the ws(s) URL.
        self.ws_url = cloud_url.replace("https://", "wss://").replace("http://", "ws://") + "/agent/ws"
        self.token = token
        self.on_command = on_command          # fn(kind:str, camera_id:str)
        self._frames: queue.Queue = queue.Queue(maxsize=60)
        self._thread = None
        self._running = False

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False

    def send_frame(self, camera_id: str, frame_b64: str, fps: float):
        """Thread-safe; drops frames if the send queue is backed up (live feed
        favours freshness over completeness)."""
        try:
            self._frames.put_nowait({"type": "frame", "camera_id": camera_id, "frame_b64": frame_b64, "fps": fps})
        except queue.Full:
            pass

    def _run(self):
        asyncio.run(self._loop())

    async def _connect(self):
        headers = {"X-Agent-Token": self.token}
        # Header kwarg was renamed across websockets versions.
        try:
            return await websockets.connect(self.ws_url, additional_headers=headers)
        except TypeError:
            return await websockets.connect(self.ws_url, extra_headers=headers)

    async def _loop(self):
        while self._running:
            try:
                ws = await self._connect()
                logger.info("relay connected")
                try:
                    await asyncio.gather(self._recv(ws), self._send(ws))
                finally:
                    await ws.close()
            except Exception as exc:
                logger.warning(f"relay disconnected ({exc}); retrying in 3s")
                await asyncio.sleep(3)

    async def _recv(self, ws):
        async for raw in ws:
            import json
            try:
                msg = json.loads(raw)
            except Exception:
                continue
            kind, cam = msg.get("type"), msg.get("camera_id")
            if kind in ("stream_start", "stream_stop") and cam:
                self.on_command(kind, cam)

    async def _send(self, ws):
        loop = asyncio.get_event_loop()
        while self._running:
            frame = await loop.run_in_executor(None, self._blocking_get)
            if frame is not None:
                import json
                await ws.send(json.dumps(frame))

    def _blocking_get(self):
        try:
            return self._frames.get(timeout=1.0)
        except queue.Empty:
            return None
