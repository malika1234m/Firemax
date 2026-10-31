"""Record training clips straight from a CCTV camera into ml/datasets/own_camera/.

Why straight from the camera: a phone filming the screen adds glare, moiré and
a tilted, shrunken picture — none of which the add-on ever sees. Recording the
camera's own stream gives frames that look exactly like what the model will
be asked to judge.

Each run is one recording SESSION with one label describing the scene, so the
clips can later be split by session (train vs held-out test) rather than by
frame — neighbouring frames of one clip are near-identical, and splitting them
across train and test would make the test score meaningless.

    export CAMERA_URL='rtsp://admin:<password>@192.168.1.120:554/Streaming/Channels/101'

    # 5 clips of 30 s of cigarette smoke at about 2 m, daylight, 10 s to reposition between clips
    python ml/record_camera.py --label smoke_2m_day --clips 5 --seconds 30 --gap 10

    # the "nothing is wrong" footage the model also needs
    python ml/record_camera.py --label no_smoke_walk_past --clips 3 --seconds 30

    # dry run against a video file instead of the camera
    python ml/record_camera.py --url clip.mp4 --label test --clips 1 --seconds 5

Every clip is listed in ml/datasets/own_camera/clips.csv with its label, start
time and frame count.
"""
import argparse
import csv
import os
import re
import sys
import time
from datetime import datetime
from urllib.parse import urlsplit, urlunsplit

# RTSP over TCP. OpenCV's default (UDP) drops packets on Wi-Fi cameras, which
# shows up as grey smeared frames — useless as training data.
os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp")

import cv2  # noqa: E402  (must come after the environment variable above)

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "datasets", "own_camera")
INDEX = os.path.join(OUT, "clips.csv")
RECONNECT_SECONDS = 3


def masked(url: str) -> str:
    """The URL with any password replaced, so it is safe to print."""
    parts = urlsplit(url)
    if parts.password:
        host = parts.hostname + (f":{parts.port}" if parts.port else "")
        parts = parts._replace(netloc=f"{parts.username}:***@{host}")
    return urlunsplit(parts)


def basic_auth_relay(url: str) -> str:
    """Relay the camera through 127.0.0.1 with Digest sign-in hidden.

    Some EZVIZ firmware offers Digest and Basic sign-in but rejects a correct
    Digest answer. FFmpeg (inside OpenCV) always prefers Digest, so it gets
    401 with the right password. The relay removes the Digest offer from the
    camera's replies, so FFmpeg falls back to Basic. RTSP over TCP carries the
    video on the same connection, so everything else passes through untouched.
    Listens on loopback only — nothing new is reachable from the network.
    """
    import socket
    import threading

    parts = urlsplit(url)
    camera = (parts.hostname, parts.port or 554)
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    listener.listen(4)
    port = listener.getsockname()[1]
    digest = re.compile(rb"WWW-Authenticate: Digest[^\r\n]*\r\n")

    def pipe(src, dst, rewrite):
        try:
            while data := src.recv(65536):
                dst.sendall(digest.sub(b"", data) if rewrite else data)
        except OSError:
            pass
        finally:
            for s in (src, dst):
                try:
                    s.close()
                except OSError:
                    pass

    def serve():
        while True:
            client, _ = listener.accept()
            upstream = socket.create_connection(camera, timeout=10)
            upstream.settimeout(None)
            threading.Thread(target=pipe, args=(client, upstream, False), daemon=True).start()
            threading.Thread(target=pipe, args=(upstream, client, True), daemon=True).start()

    threading.Thread(target=serve, daemon=True).start()
    auth = f"{parts.username}:{parts.password}@" if parts.username else ""
    return urlunsplit(parts._replace(netloc=f"{auth}127.0.0.1:{port}"))


def open_camera(url: str):
    """Open the stream, retrying until it answers or the user gives up."""
    source = int(url) if url.isdigit() else url
    while True:
        cap = cv2.VideoCapture(source)
        if cap.isOpened():
            ok, frame = cap.read()
            if ok:
                return cap, frame
            cap.release()
        print(f"  cannot read {masked(url)} — retrying in {RECONNECT_SECONDS}s (Ctrl-C to stop)")
        time.sleep(RECONNECT_SECONDS)


def stream_fps(cap, url: str) -> float:
    """Frames per second the stream really delivers.

    Cameras often report the wrong rate — the EZVIZ TY1 Pro says 15 and sends
    about 18 — and a clip written at the reported rate plays back too slowly,
    so a 30 s take becomes 37 s and every timestamp in it is wrong. A live
    stream is therefore timed for two seconds; a file reports its own rate.
    """
    reported = cap.get(cv2.CAP_PROP_FPS)
    if os.path.isfile(url):
        return reported if 1 <= reported <= 60 else 25.0
    start, frames = time.time(), 0
    while time.time() - start < 2.0:
        if cap.read()[0]:
            frames += 1
    measured = frames / (time.time() - start)
    return measured if 1 <= measured <= 60 else 25.0


def record_clip(cap, first_frame, path: str, seconds: float, fps: float, url: str, preview: bool):
    """Write `seconds` of video to `path`. Returns (cap, frames written).

    A dropped stream reconnects and carries on into the same clip, so a Wi-Fi
    hiccup costs a moment of footage, not the whole take.
    """
    h, w = first_frame.shape[:2]
    writer = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    frames, frame = 0, first_frame
    # A camera delivers frames in real time; a video file (dry run) would be
    # read as fast as the disk allows, so pace it to the same rate.
    pace = os.path.isfile(url)
    start = time.time()
    end = start + seconds
    try:
        while time.time() < end:
            if pace:
                time.sleep(max(0.0, start + frames / fps - time.time()))
            if frame is None:
                ok, frame = cap.read()
                if not ok:
                    print("  stream dropped — reconnecting")
                    cap.release()
                    cap, frame = open_camera(url)
            if frame.shape[:2] != (h, w):
                frame = cv2.resize(frame, (w, h))
            writer.write(frame)
            frames += 1
            if preview:
                cv2.imshow("recording (q = stop this clip)", frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
            frame = None
    finally:
        writer.release()
    return cap, frames


def countdown(seconds: int, message: str):
    for left in range(seconds, 0, -1):
        print(f"\r  {message} in {left:2d}s ", end="", flush=True)
        time.sleep(1)
    print("\r" + " " * 60 + "\r", end="")


def append_index(row: dict):
    new = not os.path.exists(INDEX)
    with open(INDEX, "a", newline="") as fh:
        out = csv.DictWriter(fh, fieldnames=list(row))
        if new:
            out.writeheader()
        out.writerow(row)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--url", default=os.environ.get("CAMERA_URL", ""),
                    help="RTSP URL, video file or webcam index (default: $CAMERA_URL)")
    ap.add_argument("--label", required=True,
                    help="what this session shows, e.g. smoke_2m_day or no_smoke_walk_past")
    ap.add_argument("--clips", type=int, default=5, help="how many clips (default 5)")
    ap.add_argument("--seconds", type=float, default=30, help="length of each clip (default 30)")
    ap.add_argument("--gap", type=int, default=10,
                    help="seconds between clips to reposition / relight the smoke (default 10)")
    ap.add_argument("--preview", action="store_true", help="show the picture while recording")
    ap.add_argument("--basic-auth", action="store_true",
                    help="for cameras that answer 401 to a correct password (EZVIZ TY1 Pro)")
    args = ap.parse_args()

    if not args.url:
        sys.exit("No camera. Set CAMERA_URL or pass --url (see the top of this file).")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", args.label):
        sys.exit("--label may only contain letters, digits, _ and - (it becomes the file name).")

    session = datetime.now().strftime("%Y%m%d_%H%M%S")
    folder = os.path.join(OUT, f"{session}_{args.label}")
    os.makedirs(folder, exist_ok=True)

    print(f"camera : {masked(args.url)}")
    if args.basic_auth:
        args.url = basic_auth_relay(args.url)
    cap, frame = open_camera(args.url)
    fps = stream_fps(cap, args.url)
    h, w = frame.shape[:2]
    print(f"stream : {w}x{h} @ {fps:.1f} fps")
    print(f"saving : {folder}\n")

    try:
        for n in range(1, args.clips + 1):
            countdown(args.gap, f"clip {n}/{args.clips} starts")
            path = os.path.join(folder, f"{args.label}_{n:02d}.mp4")
            started = datetime.now().isoformat(timespec="seconds")
            print(f"  ● recording clip {n}/{args.clips} ({args.seconds:.0f}s) …")
            ok, frame = cap.read()
            if not ok:
                cap.release()
                cap, frame = open_camera(args.url)
            cap, frames = record_clip(cap, frame, path, args.seconds, fps, args.url, args.preview)
            print(f"  ✓ {os.path.basename(path)}  {frames} frames")
            append_index({"session": session, "label": args.label, "clip": n,
                          "file": os.path.relpath(path, OUT), "started": started,
                          "seconds": args.seconds, "frames": frames, "fps": round(fps, 1),
                          "width": w, "height": h})
    except KeyboardInterrupt:
        print("\nstopped — finished clips are kept.")
    finally:
        cap.release()
        if args.preview:
            cv2.destroyAllWindows()

    print(f"\nDone. Clips are in {folder}")
    print(f"Index: {INDEX}")


if __name__ == "__main__":
    main()
