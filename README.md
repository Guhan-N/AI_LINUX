# 🐧 LinAgent: Lightweight Autonomous Linux AI Assistant

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Linux Compatible](https://img.shields.io/badge/Linux-Debian%20%7C%20Ubuntu%20%7C%20Arch%20%7C%20Fedora%20%7C%20Alpine-green.svg)](#)

**LinAgent** is an ultra-lightweight, modular, and autonomous AI assistant engineered specifically for Linux systems. It acts as an intelligent co-pilot for Linux administration, system automation, live web browsing, online/local search, and persistent self-learning.

It is designed with **zero bloat**: starts up in milliseconds, runs on less than 40 MB RAM idle, and works with **100% free local offline models** (via Ollama) as well as ultra-fast cloud models (Groq, Gemini, OpenAI).

---

## 🌟 Key Capabilities

1. **System Automation & Administration**
   - Execute bash/zsh shell commands with persistent working directory tracking.
   - Built-in safety guardrails intercepting dangerous operations (e.g. `rm -rf /`, raw disk formatting, fork bombs).
   - Abstraction over package managers (`apt`, `pacman`, `dnf`, `zypper`, `apk`).
   - Service management with `systemctl` (start, stop, restart, status) and live log inspection with `journalctl`.
   - Automated cron job scheduling.

2. **Web Browsing & Real-Time Searching**
   - **Zero-API-key Web Search**: Native DuckDuckGo integration for real-time web search, technical solutions, and package queries.
   - **Ultra-Lightweight Web Reader**: Direct HTTP scraper that extracts clean Markdown text from tutorials, documentation, and GitHub repositories without running a heavy browser.
   - Web file downloader for binaries, scripts, and archives.

3. **Continuous Learning & Long-Term Memory**
   - Embedded SQLite database with **FTS5 (Full-Text Search)** indexing.
   - Remembers user preferences, project directory paths, hardware specs, and custom configurations.
   - Learns and remembers troubleshooting solutions: when an error is resolved, LinAgent stores the fix so it knows how to solve it immediately next time.
   - **Dynamic Skill Learning**: LinAgent can write and register brand-new Python tools into `~/.config/linagent/skills/` on the fly.

4. **Multiple Interfaces**
   - **Interactive CLI / TUI**: Live chat with syntax highlighting, streaming, and execution approval prompts.
   - **One-Shot CLI**: Direct command execution from bash (`linagent run "find files over 500MB and compress them"`).
   - **Modern Web Dashboard**: Embedded glassmorphic dark-mode web dashboard on `http://localhost:8808` with real-time CPU/RAM/Disk telemetry.
   - **Systemd Daemon**: Single-command background service setup (`linagent.service`).

---

## 🏗️ Architecture

```
                               ┌─────────────────────────────┐
                               │       User Interfaces       │
                               │  - Interactive CLI / TUI    │
                               │  - One-shot CLI ("run ...") │
                               │  - Embedded Web Dashboard   │
                               └──────────────┬──────────────┘
                                              │
                                              ▼
                               ┌─────────────────────────────┐
                               │     LinAgent Core Engine    │
                               │  - ReAct Autonomous Loop    │
                               │  - Safety & Policy Filter   │
                               │  - Pluggable LLM Providers  │
                               │    (Ollama/Groq/Gemini/OAI) │
                               └──────────────┬──────────────┘
                                              │
               ┌───────────────┬──────────────┼──────────────┬───────────────┐
               ▼               ▼              ▼              ▼               ▼
        ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
        │  Automation │ │   Browsing  │ │  Searching  │ │   Learning  │ │ Dynamic     │
        │  - Bash/zsh │ │ - Fast HTTP │ │ - DuckDuckGo│ │ - SQLite FTS│ │ Skills &    │
        │  - Systemctl│ │   scraper   │ │ - Ripgrep / │ │ - Solution  │ │ User        │
        │  - Package  │ │ - Page text │ │   fd search │   knowledge   │ │ Extensions  │
        │    managers │   extractor   │ - Local files │ - User prefs  │ └─────────────┘
        │  - Cron/jobs│ └─────────────┘ └─────────────┘ └─────────────┘
        └─────────────┘
```

---

## 🚀 Quick Start & Installation

### Option 1: One-Line Curl Installer (Fastest)
On any Linux machine (Ubuntu, Debian, Arch, Fedora, Alpine, etc.):

```bash
curl -sSL https://raw.githubusercontent.com/Guhan-N/AI_LINUX/main/install.sh | bash
```

### Option 2: Clone and Install

```bash
git clone https://github.com/Guhan-N/AI_LINUX.git
cd AI_LINUX
chmod +x install.sh
./install.sh
```

The script automatically sets up a clean virtual environment in `~/.local/share/linagent/venv`, installs dependencies, and creates a symlink in `~/.local/bin/linagent` (or `/usr/local/bin/linagent`).

### Option 2: Manual Installation via Pip

```bash
python3 -m venv ~/.local/share/linagent/venv
source ~/.local/share/linagent/venv/bin/activate
pip install -e .
```

---

## ⚙️ Configuration & LLM Providers

Run the interactive setup wizard:

```bash
linagent config
```

You can choose between:

| Provider | Type | Recommended Model | API Key Required? |
| :--- | :--- | :--- | :--- |
| **Ollama** | 100% Local & Offline | `llama3.2:3b`, `qwen2.5-coder:7b` | No (Completely Free) |
| **Groq** | Fast Cloud API | `llama-3.3-70b-versatile` | Yes (Free Tier Available) |
| **Google Gemini** | Cloud API | `gemini-2.0-flash` | Yes (Free Tier Available) |
| **OpenAI** | Cloud API | `gpt-4o-mini`, `gpt-4o` | Yes |
| **Custom** | Local / Self-Hosted | vLLM, LocalAI, LM Studio | Depends on host |

You can also configure via environment variables:

```bash
export LINAGENT_PROVIDER="ollama"          # or "groq", "gemini", "openai"
export LINAGENT_MODEL="llama3.2:3b"
export GROQ_API_KEY="gsk_..."              # if using Groq
export GEMINI_API_KEY="AIza..."            # if using Gemini
export OPENAI_API_KEY="sk-..."             # if using OpenAI
```

### 🔄 Smart Failover Waterfall & Key Rotation (100% Free AI)
LinAgent features an automated **Failover Waterfall** and **Key-Rotation Pool**:

```
[1. Google Gemini (1,500/day free)]
       │ (Hit Rate Limit HTTP 429)
       ▼
[2. Groq Cloud (14,400/day free)]
       │ (Hit Rate Limit or Network Error)
       ▼
[3. OpenRouter Free Tier (:free models)]
       │ (Exhausted or Offline)
       ▼
[4. Local Ollama (100% Offline on Linux CPU)]
       │
       ▼
  Never Fails!
```

- **Key Rotation**: You can provide multiple keys for the same provider (e.g. `GEMINI_API_KEYS="key1,key2,key3"`). When one key hits its quota limit (HTTP 429), LinAgent rotates to the next key automatically.
- **Provider Waterfall**: If all keys for Gemini are exhausted, LinAgent cascades to Groq, then OpenRouter, and finally drops down to your local **Ollama** running offline on your Linux CPU.
- **Enable/Disable**: Toggle via `linagent config` or set `export LINAGENT_AUTO_FAILOVER=true`.

Configuration is persisted to `~/.config/linagent/config.json`.

---

## 💻 CLI Usage

### 1. Interactive Terminal Assistant
Launch the interactive session:

```bash
linagent chat
# or simply:
linagent
```

Commands available inside interactive chat:
- `/tools` - List all active tools and permissions.
- `/memory` - View stored facts, preferences, and learned recipes.
- `/clear` - Reset conversational history.
- `/help` - Show command help.
- `/exit` - Exit LinAgent.

### 2. One-Shot Command Execution
Run any instruction directly from your terminal or shell scripts:

```bash
linagent run "check system memory and list the top 3 processes"
linagent run "search DuckDuckGo for the latest Arch Linux news"
linagent run "find all .log files in /var/log modified in the last 24 hours"
linagent run "remember that my web project root is at /var/www/my-app"
```

### 3. Memory & Knowledge Base Management

```bash
# List all stored memories
linagent memory list

# Search memory
linagent memory search "web project"

# Clear memory database
linagent memory clear
```

### 4. Web Dashboard & REST API
Launch the responsive dark-mode Web UI:

```bash
linagent web --port 8808
```
Open `http://localhost:8808` in your browser.

---

## 🛡️ Safety Guardrails

LinAgent includes a safety filter that intercepts destructive and high-risk commands before execution:
- Blocks catastrophic patterns: `rm -rf /`, `rm -rf /*`, `mkfs`, raw device writes (`dd of=/dev/sdX`), fork bombs, `chmod 777 /`.
- Interactive prompt asks for explicit user confirmation before executing tools marked with `requires_confirmation=True` (e.g. installing packages, modifying cron jobs, managing systemd services).
- Safe mode can be toggled in `linagent config` or via `--safe-mode`.

---

## 🔄 Running as a Background Daemon (Systemd)

Generate and install the systemd user service:

```bash
linagent service
sudo cp linagent.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now linagent
```

Now LinAgent's REST API and Web Dashboard will automatically start on system boot.

---

## 🧪 Running the Test Suite

LinAgent includes a comprehensive unit and integration test suite:

```bash
pytest tests/ -v
```

All 13 test suites validate configuration, safety filters, file operations, web search, memory storage, dynamic skill creation, and ReAct loop execution.

---

## 📄 License
Released under the [MIT License](LICENSE).
