"""Linux package manager abstraction (apt, pacman, dnf, zypper, apk, pip)."""

import shutil
import subprocess
from typing import Dict, List, Optional, Tuple

from linagent.core.tools import ToolResult, default_registry

def detect_package_manager() -> Optional[str]:
    """Detect available package manager on the Linux distribution."""
    managers = ["apt-get", "pacman", "dnf", "zypper", "apk", "yum"]
    for mgr in managers:
        if shutil.which(mgr):
            return mgr
    return None

@default_registry.register(
    name="search_linux_package",
    description="Search for available packages across the distribution's package repositories.",
)
def search_linux_package(package_name: str) -> ToolResult:
    """Search for a package in the distribution's repositories."""
    mgr = detect_package_manager()
    if not mgr:
        return ToolResult(
            success=False,
            error="No supported Linux package manager found (checked: apt-get, pacman, dnf, zypper, apk).",
        )

    if mgr == "apt-get":
        cmd = ["apt-cache", "search", package_name]
    elif mgr == "pacman":
        cmd = ["pacman", "-Ss", package_name]
    elif mgr == "dnf":
        cmd = ["dnf", "search", package_name]
    elif mgr == "zypper":
        cmd = ["zypper", "search", package_name]
    elif mgr == "apk":
        cmd = ["apk", "search", package_name]
    else:
        cmd = ["yum", "search", package_name]

    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        output = res.stdout.strip()
        lines = output.split("\n")[:25]  # Limit to 25 lines
        return ToolResult(success=True, output="\n".join(lines) or "No packages found.")
    except Exception as e:
        return ToolResult(success=False, error=str(e))

@default_registry.register(
    name="install_linux_package",
    description="Install a package via the system package manager (requires sudo permissions).",
    is_dangerous=True,
    requires_confirmation=True,
)
def install_linux_package(package_name: str, use_sudo: bool = True) -> ToolResult:
    """Install a package using the system package manager."""
    mgr = detect_package_manager()
    if not mgr:
        return ToolResult(success=False, error="No supported Linux package manager found.")

    prefix = ["sudo"] if use_sudo else []

    if mgr == "apt-get":
        cmd = prefix + ["apt-get", "install", "-y", package_name]
    elif mgr == "pacman":
        cmd = prefix + ["pacman", "-S", "--noconfirm", package_name]
    elif mgr == "dnf":
        cmd = prefix + ["dnf", "install", "-y", package_name]
    elif mgr == "zypper":
        cmd = prefix + ["zypper", "--non-interactive", "install", package_name]
    elif mgr == "apk":
        cmd = prefix + ["apk", "add", package_name]
    else:
        cmd = prefix + ["yum", "install", "-y", package_name]

    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if res.returncode == 0:
            return ToolResult(success=True, output=f"Successfully installed '{package_name}'.\n{res.stdout.strip()[:500]}")
        else:
            return ToolResult(success=False, error=res.stderr.strip() or res.stdout.strip())
    except Exception as e:
        return ToolResult(success=False, error=str(e))
