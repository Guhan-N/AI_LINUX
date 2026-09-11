#!/usr/bin/env bash
# ==============================================================================
# LinAgent - Lightweight Linux AI Assistant Installer
# ==============================================================================
set -e

COLOR_BLUE='\033[0;34m'
COLOR_GREEN='\033[0;32m'
COLOR_YELLOW='\033[1;33m'
COLOR_RED='\033[0;31m'
COLOR_CYAN='\033[0;36m'
COLOR_RESET='\033[0m'

echo -e "${COLOR_BLUE}"
cat << "EOF"
  _      _             _                    _   
 | |    (_)           / \   __ _  ___ _ __ | |_ 
 | |    | | _  _     / _ \ / _` |/ _ \ '_ \| __|
 | |___ | |(_)| |_  / ___ \ (_| |  __/ | | | |_ 
 |_____||_|    (_) /_/   \_\__, |\___|_| |_|\__|
                           |___/                
EOF
echo -e "${COLOR_CYAN}Installing LinAgent - Lightweight Autonomous Linux AI Assistant${COLOR_RESET}\n"

# 1. Check Python 3
if ! command -v python3 &>/dev/null; then
    echo -e "${COLOR_RED}Error: Python 3 is not installed.${COLOR_RESET}"
    echo "Please install Python 3 (e.g. 'sudo apt install python3 python3-venv python3-pip' or 'sudo pacman -S python')"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo -e "${COLOR_GREEN}✓ Found Python ${PYTHON_VERSION}${COLOR_RESET}"

# 2. Determine installation paths
INSTALL_DIR="$HOME/.local/share/linagent"
BIN_DIR="$HOME/.local/bin"
CONFIG_DIR="$HOME/.config/linagent"

mkdir -p "$INSTALL_DIR"
mkdir -p "$BIN_DIR"
mkdir -p "$CONFIG_DIR"
mkdir -p "$CONFIG_DIR/skills"

# 3. Create virtual environment
VENV_DIR="$INSTALL_DIR/venv"
if [ ! -d "$VENV_DIR" ]; then
    echo -e "${COLOR_CYAN}Creating virtual environment at ${VENV_DIR}...${COLOR_RESET}"
    python3 -m venv "$VENV_DIR"
fi

# 4. Fetch or copy LinAgent files
echo -e "${COLOR_CYAN}Setting up LinAgent files...${COLOR_RESET}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd)"

if [ -d "$SCRIPT_DIR/linagent" ]; then
    cp -r "$SCRIPT_DIR/linagent" "$INSTALL_DIR/"
    cp "$SCRIPT_DIR/pyproject.toml" "$INSTALL_DIR/" 2>/dev/null || true
    cp "$SCRIPT_DIR/setup.py" "$INSTALL_DIR/" 2>/dev/null || true
else
    echo -e "${COLOR_CYAN}Fetching latest LinAgent from https://github.com/Guhan-N/AI_LINUX.git...${COLOR_RESET}"
    TMP_CLONE=$(mktemp -d)
    git clone https://github.com/Guhan-N/AI_LINUX.git "$TMP_CLONE"
    cp -r "$TMP_CLONE/linagent" "$INSTALL_DIR/"
    cp "$TMP_CLONE/pyproject.toml" "$INSTALL_DIR/" 2>/dev/null || true
    cp "$TMP_CLONE/setup.py" "$INSTALL_DIR/" 2>/dev/null || true
    rm -rf "$TMP_CLONE"
fi

# 5. Install Python dependencies
echo -e "${COLOR_CYAN}Installing dependencies into virtual environment...${COLOR_RESET}"
"$VENV_DIR/bin/pip" install --upgrade pip --quiet
"$VENV_DIR/bin/pip" install -e "$INSTALL_DIR" --quiet || "$VENV_DIR/bin/pip" install openai pydantic fastapi uvicorn requests --quiet

# 6. Create binary wrapper in ~/.local/bin
WRAPPER="$BIN_DIR/linagent"
cat << EOF > "$WRAPPER"
#!/usr/bin/env bash
exec "$VENV_DIR/bin/python3" -m linagent.cli.main "\$@"
EOF
chmod +x "$WRAPPER"

# Also try symlinking to /usr/local/bin if running as root or sudo available
if [ "$EUID" -eq 0 ]; then
    ln -sf "$WRAPPER" /usr/local/bin/linagent
    echo -e "${COLOR_GREEN}✓ Symlinked to /usr/local/bin/linagent${COLOR_RESET}"
elif sudo -n true 2>/dev/null; then
    sudo ln -sf "$WRAPPER" /usr/local/bin/linagent 2>/dev/null || true
fi

# 7. Check if ~/.local/bin is in PATH
if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
    echo -e "${COLOR_YELLOW}Notice: $BIN_DIR is not in your current PATH.${COLOR_RESET}"
    echo "Add it to your shell configuration by running:"
    echo "  echo 'export PATH=\"\$HOME/.local/bin:\$PATH\"' >> ~/.bashrc  # or ~/.zshrc"
    echo "  source ~/.bashrc"
fi

echo -e "\n${COLOR_GREEN}======================================================${COLOR_RESET}"
echo -e "${COLOR_GREEN}✓ LinAgent successfully installed!${COLOR_RESET}"
echo -e "${COLOR_GREEN}======================================================${COLOR_RESET}\n"

echo -e "Quick Start Guide:"
echo -e "  1. Configure your LLM backend:"
echo -e "     ${COLOR_CYAN}linagent config${COLOR_RESET}   (Choose Ollama local or Groq/Gemini/OpenAI)"
echo -e "  2. Start interactive assistant:"
echo -e "     ${COLOR_CYAN}linagent chat${COLOR_RESET}     (Or simply run 'linagent')"
echo -e "  3. Run one-shot automation:"
echo -e "     ${COLOR_CYAN}linagent run \"find files over 500MB and list them\"${COLOR_RESET}"
echo -e "  4. Launch Web UI Dashboard:"
echo -e "     ${COLOR_CYAN}linagent web${COLOR_RESET}      (Open http://127.0.0.1:8808)"
echo -e "  5. Set up as systemd background service:"
echo -e "     ${COLOR_CYAN}linagent service${COLOR_RESET}\n"
