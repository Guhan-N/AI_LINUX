"""Systemd service management and log inspection tools."""

import shutil
import subprocess
from typing import Optional

from linagent.core.tools import ToolResult, default_registry

@default_registry.register(
    name="check_service_status",
    description="Check the systemd status of a service (e.g. 'nginx', 'ssh', 'docker', 'cron').",
)
def check_service_status(service_name: str) -> ToolResult:
    """Check service status using systemctl."""
    if not shutil.which("systemctl"):
        return ToolResult(success=False, error="systemctl is not available on this system.")

    try:
        res = subprocess.run(
            ["systemctl", "status", service_name, "--no-pager"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        return ToolResult(
            success=True,
            output=res.stdout.strip() or res.stderr.strip(),
            data={"active": res.returncode == 0},
        )
    except Exception as e:
        return ToolResult(success=False, error=str(e))

@default_registry.register(
    name="manage_service",
    description="Start, stop, restart, enable, or disable a system service.",
    is_dangerous=True,
    requires_confirmation=True,
)
def manage_service(service_name: str, action: str) -> ToolResult:
    """Manage service state: start | stop | restart | reload | enable | disable."""
    valid_actions = ["start", "stop", "restart", "reload", "enable", "disable"]
    if action not in valid_actions:
        return ToolResult(
            success=False,
            error=f"Invalid action '{action}'. Must be one of: {', '.join(valid_actions)}",
        )

    if not shutil.which("systemctl"):
        return ToolResult(success=False, error="systemctl is not available on this system.")

    try:
        res = subprocess.run(
            ["sudo", "systemctl", action, service_name],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if res.returncode == 0:
            return ToolResult(
                success=True,
                output=f"Successfully executed 'systemctl {action} {service_name}'.",
            )
        else:
            return ToolResult(
                success=False,
                error=res.stderr.strip() or res.stdout.strip(),
            )
    except Exception as e:
        return ToolResult(success=False, error=str(e))

@default_registry.register(
    name="get_service_logs",
    description="Fetch recent journalctl system logs for a specific service or unit.",
)
def get_service_logs(service_name: str, lines: int = 50) -> ToolResult:
    """Fetch logs using journalctl."""
    if not shutil.which("journalctl"):
        return ToolResult(success=False, error="journalctl is not available on this system.")

    try:
        res = subprocess.run(
            ["journalctl", "-u", service_name, "-n", str(lines), "--no-pager"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        output = res.stdout.strip()
        return ToolResult(success=True, output=output or "No logs found.")
    except Exception as e:
        return ToolResult(success=False, error=str(e))
