"""The add-on must actually reach the model a release ships, even for users
whose saved options still name an older model."""
import json
import os

import yaml

from ha_agent import options

CONFIG = os.path.join(os.path.dirname(__file__), "..", "..", "addon", "firemex-local", "config.yaml")


def _load(tmp_path, **saved):
    path = tmp_path / "options.json"
    path.write_text(json.dumps(saved))
    return options.load(str(path))


def test_config_yaml_ships_the_model_the_code_expects():
    config = yaml.safe_load(open(CONFIG))
    assert (config["options"]["model_url"], config["options"]["model_sha256"]) == options.CURRENT_MODEL
    assert config["version"] == options.ADDON_VERSION


def test_a_saved_old_release_is_moved_to_the_current_model(tmp_path):
    old = "https://github.com/malika1234m/Firemax/releases/download/model-v2/fire_model.pt"
    opts = _load(tmp_path, model_url=old, model_sha256="11d7278e" + "0" * 56)
    assert (opts.model_url, opts.model_sha256) == options.CURRENT_MODEL


def test_a_users_own_model_is_kept(tmp_path):
    opts = _load(tmp_path, model_url="https://example.com/my_model.pt", model_sha256="ab" * 32)
    assert opts.model_url == "https://example.com/my_model.pt"
    assert opts.model_sha256 == "ab" * 32
