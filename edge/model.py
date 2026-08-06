"""Model acquisition for the edge agent.

The detection weights are too large to ship inside the agent image and are
distributed out-of-band (a GitHub Release asset, an S3 object, or whatever the
operator prefers). Rather than making every customer copy a .pt file onto the
box by hand, the agent fetches it on first run when MODEL_URL is set and
caches it at MODEL_PATH.

Set MODEL_SHA256 to pin the file. Weights are executable-ish input to
torch.load, so verifying what we downloaded matters — a wrong or tampered
model is a silent detection failure, which in this product means a fire that
nobody is told about.
"""
import hashlib
import logging
import os
import tempfile

import httpx

logger = logging.getLogger("edge.model")

_CHUNK = 1024 * 1024


def _sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(_CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ensure_model(model_path: str, model_url: str = "", expected_sha256: str = "") -> str:
    """Make sure model_path exists, downloading it from model_url if needed.

    Returns the usable path. Raises SystemExit with an actionable message when
    the model is missing and cannot be fetched — failing loudly at startup is
    far better than running a detector that can never fire.
    """
    if os.path.exists(model_path):
        if expected_sha256:
            actual = _sha256(model_path)
            if actual != expected_sha256.lower():
                raise SystemExit(
                    f"Model at {model_path} has checksum {actual}, expected {expected_sha256}. "
                    "Delete it to re-download, or correct MODEL_SHA256."
                )
            logger.info(f"model verified: {model_path}")
        else:
            logger.info(f"model present: {model_path}")
        return model_path

    if not model_url:
        raise SystemExit(
            f"Detection model not found at {model_path} and MODEL_URL is not set.\n"
            "Either mount the weights into the container, or set MODEL_URL to a "
            "download link. To run without detection while wiring up a site, "
            "set DETECTOR_MODE=mock."
        )

    os.makedirs(os.path.dirname(model_path) or ".", exist_ok=True)
    logger.info(f"downloading model from {model_url} …")

    # Download to a temp file in the same directory, then rename — an
    # interrupted download must never leave a half-written .pt in place that
    # looks valid on the next boot.
    fd, tmp_path = tempfile.mkstemp(dir=os.path.dirname(model_path) or ".", suffix=".part")
    os.close(fd)
    try:
        with httpx.stream("GET", model_url, follow_redirects=True, timeout=120.0) as r:
            r.raise_for_status()
            total = int(r.headers.get("content-length", 0))
            written = 0
            with open(tmp_path, "wb") as fh:
                for chunk in r.iter_bytes(_CHUNK):
                    fh.write(chunk)
                    written += len(chunk)
            if total and written != total:
                raise SystemExit(f"Model download truncated: got {written} of {total} bytes.")

        if expected_sha256:
            actual = _sha256(tmp_path)
            if actual != expected_sha256.lower():
                raise SystemExit(
                    f"Downloaded model checksum {actual} does not match MODEL_SHA256 "
                    f"{expected_sha256}. Refusing to use it."
                )

        os.replace(tmp_path, model_path)
        logger.info(f"model ready: {model_path} ({written / 1e6:.1f} MB)")
        return model_path
    except httpx.HTTPError as exc:
        raise SystemExit(f"Could not download the model from {model_url}: {exc}")
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
