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

    def __init__(self, entity_id: str, client):
        self.entity_id = entity_id
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


def reader_factory(client):
    """EdgePipeline calls reader_factory(stream_url); bind the client here."""
    return lambda entity_id: HACameraStream(entity_id, client)
