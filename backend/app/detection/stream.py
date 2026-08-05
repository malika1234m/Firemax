import cv2
import threading
import time
import logging

logger = logging.getLogger(__name__)


class StreamReader:
    """
    Reads frames from an RTSP stream or video file in a background thread.
    Always holds the latest frame — callers never block waiting for a frame.
    """

    def __init__(self, stream_url: str):
        self.stream_url = stream_url
        self._cap: cv2.VideoCapture = None
        self._frame = None
        self._lock = threading.Lock()
        self._running = False
        self._thread: threading.Thread = None
        self._last_frame_time = 0.0

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=3)
        if self._cap:
            self._cap.release()

    def get_frame(self):
        with self._lock:
            return self._frame.copy() if self._frame is not None else None

    def last_frame_age(self) -> float | None:
        """Seconds since the last successfully read frame, or None if never connected."""
        with self._lock:
            return time.time() - self._last_frame_time if self._last_frame_time else None

    def _read_loop(self):
        while self._running:
            self._cap = cv2.VideoCapture(self.stream_url)
            if not self._cap.isOpened():
                logger.warning(f"Cannot open stream: {self.stream_url} — retrying in 5s")
                with self._lock:
                    self._frame = None
                time.sleep(5)
                continue

            logger.info(f"Stream opened: {self.stream_url}")
            while self._running:
                ret, frame = self._cap.read()
                if not ret:
                    logger.warning(f"Stream lost: {self.stream_url} — reconnecting")
                    break
                with self._lock:
                    self._frame = frame
                    self._last_frame_time = time.time()

            self._cap.release()
            with self._lock:
                self._frame = None
            if self._running:
                time.sleep(2)  # brief pause before reconnect
