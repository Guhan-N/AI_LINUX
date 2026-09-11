"""Desktop GUI and Graphical Browser automation tools for Linux (X11 & Wayland)."""

import os
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

from linagent.core.tools import ToolResult, default_registry

def _get_display_env() -> Dict[str, str]:
    """Ensure DISPLAY and XAUTHORITY or WAYLAND_DISPLAY are propagated to GUI commands."""
    env = dict(os.environ)
    if "DISPLAY" not in env and os.name != "nt":
        env["DISPLAY"] = ":0"
    return env

@default_registry.register(
    name="open_in_browser",
    description="Open a website or URL in the user's real graphical desktop web browser (Firefox, Chrome, Chromium, Brave, etc.) on Linux.",
)
def open_in_browser(url: str) -> ToolResult:
    """Open URL in user's default desktop browser."""
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "https://" + url

    env = _get_display_env()

    # Try xdg-open first (standard desktop opener across GNOME, XFCE, KDE, Kali)
    if shutil.which("xdg-open"):
        cmd = ["nohup", "xdg-open", url]
    elif shutil.which("firefox"):
        cmd = ["nohup", "firefox", url]
    elif shutil.which("chromium") or shutil.which("chromium-browser"):
        browser_bin = shutil.which("chromium") or shutil.which("chromium-browser")
        cmd = ["nohup", browser_bin, url]
    elif shutil.which("google-chrome"):
        cmd = ["nohup", "google-chrome", url]
    elif os.name == "nt":
        import webbrowser
        webbrowser.open(url)
        return ToolResult(success=True, output=f"Opened {url} in default browser.")
    else:
        return ToolResult(success=False, error="No graphical browser or xdg-open found on this system.")

    try:
        subprocess.Popen(
            cmd,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            preexec_fn=os.setpgrp if os.name != "nt" else None,
        )
        return ToolResult(
            success=True,
            output=f"Successfully launched desktop browser to: {url}",
            data={"url": url},
        )
    except Exception as e:
        return ToolResult(success=False, error=f"Failed to open browser: {e}")

@default_registry.register(
    name="launch_gui_app",
    description="Launch any graphical desktop application on Linux (e.g. 'firefox', 'vlc', 'gedit', 'mousepad', 'wireshark', 'code', 'calculator', 'thunar'). Spawns in background without blocking.",
)
def launch_gui_app(app_command: str) -> ToolResult:
    """Spawn a GUI application on Linux desktop."""
    env = _get_display_env()

    parts = app_command.strip().split()
    if not parts:
        return ToolResult(success=False, error="Empty application command.")

    bin_name = parts[0]
    if not shutil.which(bin_name):
        return ToolResult(
            success=False,
            error=f"Application '{bin_name}' is not installed. Install it first using package manager.",
        )

    try:
        subprocess.Popen(
            ["nohup"] + parts,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            preexec_fn=os.setpgrp if os.name != "nt" else None,
        )
        return ToolResult(
            success=True,
            output=f"Successfully launched GUI application: '{app_command}'",
        )
    except Exception as e:
        return ToolResult(success=False, error=f"Failed to launch GUI application: {e}")

@default_registry.register(
    name="type_text_into_active_window",
    description="Type text into the currently focused desktop application window using xdotool.",
)
def type_text_into_active_window(text: str, press_enter: bool = True) -> ToolResult:
    """Type keys into active desktop window."""
    if not shutil.which("xdotool"):
        return ToolResult(
            success=False,
            error="xdotool is not installed. Run 'sudo apt install xdotool' to enable GUI typing and mouse control.",
        )

    env = _get_display_env()
    try:
        subprocess.run(["xdotool", "type", "--delay", "50", text], env=env, check=True)
        if press_enter:
            subprocess.run(["xdotool", "key", "Return"], env=env, check=True)
        return ToolResult(success=True, output=f"Typed text: '{text}' into active window.")
    except Exception as e:
        return ToolResult(success=False, error=f"Failed to type text: {e}")

@default_registry.register(
    name="take_screenshot",
    description="Capture a screenshot of the Linux desktop display.",
)
def take_screenshot(output_path: Optional[str] = None) -> ToolResult:
    """Take desktop screenshot using import, scrot, maim, or grim."""
    dest = Path(output_path or os.path.expanduser("~/screenshot.png"))
    dest.parent.mkdir(parents=True, exist_ok=True)
    env = _get_display_env()

    if shutil.which("scrot"):
        cmd = ["scrot", str(dest)]
    elif shutil.which("maim"):
        cmd = ["maim", str(dest)]
    elif shutil.which("import"):
        cmd = ["import", "-window", "root", str(dest)]
    elif shutil.which("grim"):
        cmd = ["grim", str(dest)]
    else:
        return ToolResult(
            success=False,
            error="No screenshot utility found. Install scrot: 'sudo apt install scrot'",
        )

    try:
        subprocess.run(cmd, env=env, check=True, timeout=10)
        return ToolResult(
            success=True,
            output=f"Screenshot captured and saved to: {dest.resolve()}",
            data={"path": str(dest.resolve())},
        )
    except Exception as e:
        return ToolResult(success=False, error=f"Screenshot failed: {e}")
