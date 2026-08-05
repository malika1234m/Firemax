import pytest
from app.net_guard import parse_target, assert_safe_target, UnsafeTargetError


# ── Scheme handling ─────────────────────────────────────────────────────────

def test_bare_host_defaults_to_rtsp():
    host, port, scheme = parse_target("192.168.1.10")
    assert (host, port, scheme) == ("192.168.1.10", 554, "rtsp")


def test_explicit_port_is_kept():
    host, port, _ = parse_target("192.168.1.10:8554")
    assert (host, port) == ("192.168.1.10", 8554)


@pytest.mark.parametrize("bad", ["file:///etc/passwd", "gopher://x", "ftp://host/f"])
def test_disallowed_schemes_rejected(bad):
    with pytest.raises(UnsafeTargetError):
        parse_target(bad)


def test_empty_target_rejected():
    with pytest.raises(UnsafeTargetError):
        parse_target("")


# ── SSRF address filtering ──────────────────────────────────────────────────

@pytest.mark.parametrize("target", [
    "127.0.0.1:8000",         # loopback / localhost services
    "169.254.169.254:80",     # cloud metadata (link-local)
    "0.0.0.0:80",             # unspecified
])
def test_dangerous_addresses_blocked(target):
    with pytest.raises(UnsafeTargetError):
        assert_safe_target(target)


@pytest.mark.parametrize("target", [
    "192.168.1.50:554",       # RFC1918 — legitimate on-prem camera
    "10.0.0.20:554",
    "172.16.5.5:554",
])
def test_private_lan_cameras_allowed(target):
    # Should not raise — private LAN is where real cameras live.
    host, port, scheme = assert_safe_target(target)
    assert scheme == "rtsp"
