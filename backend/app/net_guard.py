"""SSRF guard for user-supplied camera targets.

Camera stream URLs and the "test connection" probe both take host/URL input
from an (authenticated) admin. Without validation these become a server-side
request forgery vector: an admin could point them at loopback (localhost
services) or link-local (cloud metadata at 169.254.169.254) and use the
server as a port scanner / metadata thief. We restrict to the schemes a real
camera uses and refuse targets that resolve to loopback/link-local/reserved
addresses. Private LAN ranges (192.168.x, 10.x, ...) are intentionally
allowed because on-prem IP cameras live there.
"""
import ipaddress
import socket
from urllib.parse import urlparse

ALLOWED_SCHEMES = {"rtsp", "rtsps", "http", "https"}


class UnsafeTargetError(ValueError):
    """Raised when a host/URL resolves to a non-public address or uses a
    disallowed scheme."""


def _is_allowed_camera_ip(ip_str: str, allow_loopback: bool = False) -> bool:
    """Real IP cameras almost always sit on a private LAN (192.168.x / 10.x /
    172.16-31.x), so we deliberately ALLOW RFC1918 private ranges — blocking
    them would break the product's core use case. What we refuse are the
    ranges that are never a legitimate camera and are the actual SSRF prizes:
    loopback (localhost services), link-local (169.254.169.254 cloud
    metadata), plus reserved / multicast / unspecified.

    allow_loopback=True permits loopback (for Home Assistant, which an admin
    legitimately runs on the same host in on-prem setups) while still blocking
    the link-local metadata range and other reserved/multicast targets."""
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return False
    if ip.is_loopback:
        return allow_loopback
    return not (
        ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def parse_target(raw: str) -> tuple[str, int, str]:
    """Parse a camera target into (host, port, scheme). Adds a default rtsp://
    scheme when the caller passes a bare host[:port]. Raises UnsafeTargetError
    for disallowed schemes."""
    raw = (raw or "").strip()
    if not raw:
        raise UnsafeTargetError("A target host or URL is required")

    parsed = urlparse(raw if "://" in raw else f"rtsp://{raw}")
    scheme = parsed.scheme.lower()
    if scheme not in ALLOWED_SCHEMES:
        raise UnsafeTargetError(f"Unsupported scheme '{scheme}' — allowed: {sorted(ALLOWED_SCHEMES)}")

    host = parsed.hostname
    if not host:
        raise UnsafeTargetError("Could not determine a host from the target")

    default_port = 554 if scheme in ("rtsp", "rtsps") else (443 if scheme == "https" else 80)
    port = parsed.port or default_port
    return host, port, scheme


def _looks_like_ip(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        return False


def assert_safe_target(raw: str, allow_loopback: bool = False) -> tuple[str, int, str]:
    """Parse and validate a host/URL, rejecting loopback/link-local targets
    (the SSRF prizes). Returns (host, port, scheme).

    A literal IP is checked directly. A hostname is resolved and every returned
    address must pass — but if the hostname currently *doesn't* resolve we
    allow it, because a real camera host can be legitimately offline at the
    moment it's registered; the pipeline connection simply fails later.
    (Fully closing DNS-rebinding belongs at the network egress layer, not here.)

    allow_loopback=True is used for Home Assistant, which an admin may run on
    the same host (localhost) in an on-prem deployment — the link-local
    cloud-metadata range stays blocked regardless.
    """
    host, port, scheme = parse_target(raw)

    if _looks_like_ip(host):
        if not _is_allowed_camera_ip(host, allow_loopback):
            raise UnsafeTargetError(
                "Target is a link-local or reserved address, which is not allowed"
            )
        return host, port, scheme

    try:
        infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        return host, port, scheme   # unresolvable now — allow; connection fails later

    for info in infos:
        if not _is_allowed_camera_ip(info[4][0], allow_loopback):
            raise UnsafeTargetError(
                "Target resolves to a link-local or reserved address, which is not allowed"
            )

    return host, port, scheme
