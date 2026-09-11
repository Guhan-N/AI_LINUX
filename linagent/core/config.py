"""Configuration management for LinAgent."""

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field

# Determine platform-specific base configuration directories
def get_default_config_dir() -> Path:
    if os.name == "nt":
        base = os.getenv("APPDATA") or Path.home() / "AppData" / "Roaming"
        return Path(base) / "linagent"
    xdg_config = os.getenv("XDG_CONFIG_HOME")
    if xdg_config:
        return Path(xdg_config) / "linagent"
    return Path.home() / ".config" / "linagent"

def get_default_data_dir() -> Path:
    if os.name == "nt":
        base = os.getenv("LOCALAPPDATA") or Path.home() / "AppData" / "Local"
        return Path(base) / "linagent"
    xdg_data = os.getenv("XDG_DATA_HOME")
    if xdg_data:
        return Path(xdg_data) / "linagent"
    return Path.home() / ".local" / "share" / "linagent"

DEFAULT_CONFIG_DIR = get_default_config_dir()
DEFAULT_DATA_DIR = get_default_data_dir()

class LinAgentConfig(BaseModel):
    # LLM Settings
    provider: str = Field(default="ollama", description="LLM provider: 'ollama', 'groq', 'gemini', 'openai', 'custom'")
    model: str = Field(default="llama3.2:3b", description="Model name (e.g. llama3.2:3b, llama-3.3-70b-versatile, gemini-2.0-flash, gpt-4o-mini)")
    api_key: Optional[str] = Field(default=None, description="API key (if using cloud providers)")
    base_url: Optional[str] = Field(default=None, description="Custom endpoint base URL (e.g. http://localhost:11434/v1 for Ollama)")
    temperature: float = Field(default=0.2, description="Sampling temperature")
    max_tokens: int = Field(default=4096, description="Max output tokens")
    
    # Safety & Execution
    safe_mode: bool = Field(default=True, description="Prompt user before executing potentially destructive shell commands")
    auto_approve_safe: bool = Field(default=True, description="Automatically approve read-only commands (ls, cat, grep, ps, etc.)")
    shell_timeout_seconds: int = Field(default=60, description="Max seconds to wait for a shell command")
    default_shell: str = Field(default="bash", description="Default shell binary to use ('bash', 'sh', 'zsh', 'pwsh')")

    # Paths & Storage
    config_dir: str = Field(default_factory=lambda: str(DEFAULT_CONFIG_DIR))
    data_dir: str = Field(default_factory=lambda: str(DEFAULT_DATA_DIR))
    memory_db_path: str = Field(default_factory=lambda: str(DEFAULT_DATA_DIR / "memory.db"))
    skills_dir: str = Field(default_factory=lambda: str(DEFAULT_CONFIG_DIR / "skills"))

    # Web Dashboard Settings
    web_host: str = Field(default="127.0.0.1", description="Host address for Web UI")
    web_port: int = Field(default=8808, description="Port for Web UI")

    # Web Scraping & Search
    search_max_results: int = Field(default=5, description="Number of search results to return")
    browser_timeout_seconds: int = Field(default=15, description="Timeout for web page fetching")

def get_config_file_path() -> Path:
    env_path = os.getenv("LINAGENT_CONFIG")
    if env_path:
        return Path(env_path)
    return DEFAULT_CONFIG_DIR / "config.json"

def load_config() -> LinAgentConfig:
    """Load configuration from disk, falling back to environment variables and defaults."""
    config_file = get_config_file_path()
    data: Dict[str, Any] = {}

    if config_file.exists():
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            sys.stderr.write(f"[LinAgent] Warning: Failed to parse {config_file}: {e}\n")

    # Override with environment variables if not set in config file
    if os.getenv("LINAGENT_PROVIDER"):
        data["provider"] = os.getenv("LINAGENT_PROVIDER")
    if os.getenv("LINAGENT_MODEL"):
        data["model"] = os.getenv("LINAGENT_MODEL")

    if not data.get("api_key"):
        if os.getenv("LINAGENT_API_KEY"):
            data["api_key"] = os.getenv("LINAGENT_API_KEY")
        elif os.getenv("GROQ_API_KEY") and data.get("provider") == "groq":
            data["api_key"] = os.getenv("GROQ_API_KEY")
        elif os.getenv("GEMINI_API_KEY") and data.get("provider") == "gemini":
            data["api_key"] = os.getenv("GEMINI_API_KEY")
        elif os.getenv("OPENAI_API_KEY") and data.get("provider") == "openai":
            data["api_key"] = os.getenv("OPENAI_API_KEY")

    if os.getenv("LINAGENT_BASE_URL"):
        data["base_url"] = os.getenv("LINAGENT_BASE_URL")

    cfg = LinAgentConfig(**data)
    
    # Ensure directories exist
    Path(cfg.config_dir).mkdir(parents=True, exist_ok=True)
    Path(cfg.data_dir).mkdir(parents=True, exist_ok=True)
    Path(cfg.skills_dir).mkdir(parents=True, exist_ok=True)

    return cfg

def save_config(config: LinAgentConfig) -> Path:
    """Save configuration to disk."""
    config_file = get_config_file_path()
    config_file.parent.mkdir(parents=True, exist_ok=True)
    with open(config_file, "w", encoding="utf-8") as f:
        f.write(config.model_dump_json(indent=2))
    return config_file
