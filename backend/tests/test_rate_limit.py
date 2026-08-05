import pytest
from starlette.requests import Request
from app import rate_limit
from app.config import settings


def _req(xff=None, peer="203.0.113.9"):
    headers = []
    if xff is not None:
        headers.append((b"x-forwarded-for", xff.encode()))
    scope = {"type": "http", "headers": headers, "client": (peer, 12345)}
    return Request(scope)


@pytest.fixture
def restore_proxy_count():
    original = settings.TRUSTED_PROXY_COUNT
    yield
    settings.TRUSTED_PROXY_COUNT = original


# ── Client IP derivation (the load-balancer bug) ────────────────────────────

def test_no_trusted_proxy_uses_socket_peer(restore_proxy_count):
    settings.TRUSTED_PROXY_COUNT = 0
    # Even with a forged XFF, we ignore it when no proxy is trusted.
    assert rate_limit.client_ip(_req(xff="1.2.3.4", peer="203.0.113.9")) == "203.0.113.9"


def test_one_trusted_proxy_takes_rightmost(restore_proxy_count):
    settings.TRUSTED_PROXY_COUNT = 1
    # LB appended the real client as the last entry.
    assert rate_limit.client_ip(_req(xff="198.51.100.7")) == "198.51.100.7"


def test_spoofed_left_entries_are_ignored(restore_proxy_count):
    settings.TRUSTED_PROXY_COUNT = 1
    # Attacker prepends a fake IP; LB appends the true peer on the right.
    # We must return the true peer, not the spoofed value.
    assert rate_limit.client_ip(_req(xff="9.9.9.9, 198.51.100.7")) == "198.51.100.7"


def test_two_trusted_proxies(restore_proxy_count):
    settings.TRUSTED_PROXY_COUNT = 2
    # client -> proxyA -> proxyB -> app  =>  XFF: "client, proxyA_peer"
    assert rate_limit.client_ip(_req(xff="203.0.113.5, 70.0.0.1")) == "203.0.113.5"


def test_short_header_falls_back_to_peer(restore_proxy_count):
    settings.TRUSTED_PROXY_COUNT = 2
    # Only one entry but two proxies expected → distrust, use socket peer.
    assert rate_limit.client_ip(_req(xff="198.51.100.7", peer="10.0.0.1")) == "10.0.0.1"


# ── In-memory sliding window ────────────────────────────────────────────────

def test_memory_window_blocks_after_max():
    rate_limit._attempts.clear()
    key = "ratelimit:/x:1.1.1.1"
    for _ in range(3):
        allowed, _ = rate_limit._memory_hit(key, max_attempts=3, window_seconds=60)
        assert allowed
    allowed, retry_after = rate_limit._memory_hit(key, max_attempts=3, window_seconds=60)
    assert not allowed and retry_after > 0
    rate_limit._attempts.clear()
