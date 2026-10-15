"""Frame source that reads a Home Assistant camera entity's MJPEG proxy.

Deliberately mirrors app/detection/stream.py's StreamReader — same four
methods, same latest-frame-wins behaviour — so EdgePipeline can use either
without knowing which it has.

Why not just open the camera with OpenCV, as the site agent does? Because in
this deployment Home Assistant owns the camera. Whatever integration provides
it (Hikvision, ONVIF, generic RTSP) has already authenticated and connected;
FiremeX reads that existing feed rather than opening a second connection to the
same camera with credentials the user would have to enter twice.

cv2.VideoCapture cannot attach an Authorization header, and the proxy requires
the bearer token, so the multipart stream is read with httpx and each part is
decoded with cv2.imdecode.
"""
import logging
import threading
import time

logger = logging.getLogger("ha.stream")

# JPEG start-of-image and end-of-image markers. Scanning for these is more
# forgiving than parsing the multipart boundary, which Home Assistant has
# formatted differently across versions.
SOI = b"\xff\xd8"
EOI = b"\xff\xd9"

# If we ever accumulate this much without completing a frame, something is
# wrong with the stream and the buffer is dropped rather than grown forever.
MAX_BUFFER = 8 * 1024 * 1024

RECONNECT_SECONDS = 5


class HACameraStream:
    """Latest-frame-wins reader for one Home Assistant camera entity."""

    def __init__(self, entity_id: str, client, poll_interval: float | None = None):
        self.entity_id = entity_id
        # Seconds between still-image requests; None reads the MJPEG stream.
        self._poll_interval = poll_interval
        self.stream_url = entity_id          # what EdgePipeline logs
        self._client = client
        self._frame = None
        self._lock = threading.Lock()
        self._running = False
        self._thread = None
        self._last_frame_time = 0.0

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=3)

    def get_frame(self):
        with self._lock:
            return self._frame.copy() if self._frame is not None else None

    def last_frame_age(self) -> float | None:
        """Seconds since the last decoded frame, or None if never connected."""
        with self._lock:
            return time.time() - self._last_frame_time if self._last_frame_time else None

    def _read_loop(self):
        import cv2
        import numpy as np

        # Poll still images. The MJPEG stream below is kept for a direct
        # connection to Core, but inside Home Assistant OS the Supervisor's
        # proxy buffers whole responses and an endless stream never arrives —
        # found on a real HA OS install, where every camera sat "offline".
        if self._poll_interval is not None:
            failures = 0
            while self._running:
                t0 = time.time()
                try:
                    jpeg = self._client.camera_snapshot(self.entity_id)
                    frame = cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR)
                    if frame is not None:
                        with self._lock:
                            self._frame = frame
                            self._last_frame_time = time.time()
                        if failures:
                            logger.info(f"{self.entity_id}: snapshots flowing again")
                        failures = 0
                except Exception as exc:
                    failures += 1
                    if failures in (1, 10) or failures % 60 == 0:
                        logger.warning(f"{self.entity_id}: snapshot failed ({exc})")
                    with self._lock:
                        self._frame = None
                time.sleep(max(0.0, self._poll_interval - (time.time() - t0)))
            return

        while self._running:
            try:
                with self._client.open_stream(self.entity_id) as response:
                    response.raise_for_status()
                    logger.info(f"stream opened: {self.entity_id}")
                    buffer = bytearray()

                    for chunk in response.iter_bytes():
                        if not self._running:
                            break
                        buffer.extend(chunk)

                        # Keep only the most recent complete image in the
                        # buffer: if detection is slower than the stream, we
                        # want the newest frame, not a backlog of stale ones.
                        while True:
                            start = buffer.find(SOI)
                            end = buffer.find(EOI, start + 2) if start != -1 else -1
                            if start == -1 or end == -1:
                                break
                            jpeg = bytes(buffer[start:end + 2])
                            del buffer[:end + 2]
                            frame = cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR)
                            if frame is not None:
                                with self._lock:
                                    self._frame = frame
                                    self._last_frame_time = time.time()

                        if len(buffer) > MAX_BUFFER:
                            logger.warning(f"{self.entity_id}: no complete frame in "
                                           f"{MAX_BUFFER // 1024}KB — resetting buffer")
                            buffer.clear()

            except Exception as exc:
                if not self._running:
                    break
                logger.warning(f"{self.entity_id}: stream failed ({exc}); "
                               f"retrying in {RECONNECT_SECONDS}s")

            # A dropped stream must not leave a stale frame looking current —
            # last_frame_age is what marks the camera offline.
            with self._lock:
                self._frame = None
            if self._running:
                time.sleep(RECONNECT_SECONDS)


def reader_factory(client, poll_interval: float | None = None):
    """EdgePipeline calls reader_factory(stream_url); bind the client here.

    Pass poll_interval (seconds) to read still images instead of the MJPEG
    stream — required behind the Supervisor proxy, see camera_snapshot()."""
    return lambda entity_id: HACameraStream(entity_id, client, poll_interval)
