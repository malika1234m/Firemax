"""A new model release must replace the old file, not stop the add-on.

/data/fire_model.pt survives add-on updates. When a release pins a new
model_sha256, the cached old model no longer matches — that means "download
the new one", not "refuse to start".
"""
import hashlib
import threading
from functools import partial
from http.server import HTTPServer, SimpleHTTPRequestHandler

import pytest

from model import ensure_model


@pytest.fixture
def served(tmp_path):
    root = tmp_path / "www"
    root.mkdir()
    (root / "new.pt").write_bytes(b"new weights")
    handler = partial(SimpleHTTPRequestHandler, directory=str(root))
    server = HTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}/new.pt"
    server.shutdown()


def test_outdated_cached_model_is_replaced_by_the_pinned_release(tmp_path, served):
    path = tmp_path / "fire_model.pt"
    path.write_bytes(b"old weights")
    new_sha = hashlib.sha256(b"new weights").hexdigest()

    ensure_model(str(path), served, new_sha)

    assert path.read_bytes() == b"new weights"


def test_mismatched_model_with_no_download_address_still_refuses(tmp_path):
    path = tmp_path / "fire_model.pt"
    path.write_bytes(b"old weights")

    with pytest.raises(SystemExit):
        ensure_model(str(path), "", hashlib.sha256(b"new weights").hexdigest())
