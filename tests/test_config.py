import os
import tempfile
from pathlib import Path
from linagent.core.config import LinAgentConfig, load_config, save_config

def test_default_config():
    cfg = LinAgentConfig()
    assert cfg.provider == "ollama"
    assert cfg.safe_mode is True
    assert cfg.web_port == 8808

def test_save_and_load_config(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        fake_cfg_file = Path(tmpdir) / "config.json"
        monkeypatch.setenv("LINAGENT_CONFIG", str(fake_cfg_file))

        cfg = LinAgentConfig(provider="groq", model="llama-3.3-70b-versatile", api_key="gsk_test123")
        save_config(cfg)

        loaded = load_config()
        assert loaded.provider == "groq"
        assert loaded.model == "llama-3.3-70b-versatile"
        assert loaded.api_key == "gsk_test123"
