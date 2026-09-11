"""Task scheduling and cron management for Linux."""

import os
import shutil
import subprocess
from typing import Optional

from linagent.core.tools import ToolResult, default_registry

@default_registry.register(
    name="list_cron_jobs",
    description="List all scheduled cron jobs for the current user.",
)
def list_cron_jobs() -> ToolResult:
    """Read crontab list."""
    if not shutil.which("crontab"):
        return ToolResult(success=False, error="crontab is not available on this system.")

    try:
        res = subprocess.run(["crontab", "-l"], capture_output=True, text=True, timeout=10)
        if res.returncode == 0:
            return ToolResult(success=True, output=res.stdout.strip() or "No cron jobs scheduled.")
        elif "no crontab for" in res.stderr.lower():
            return ToolResult(success=True, output="No crontab currently configured for this user.")
        else:
            return ToolResult(success=False, error=res.stderr.strip())
    except Exception as e:
        return ToolResult(success=False, error=str(e))

@default_registry.register(
    name="add_cron_job",
    description="Add a new recurring cron job (e.g. cron_expression='0 2 * * *', command='/home/user/backup.sh').",
    is_dangerous=True,
    requires_confirmation=True,
)
def add_cron_job(cron_expression: str, command: str) -> ToolResult:
    """Append a new cron job to the user's crontab."""
    if not shutil.which("crontab"):
        return ToolResult(success=False, error="crontab is not available on this system.")

    # Validate cron expression has 5 fields
    fields = cron_expression.strip().split()
    if len(fields) != 5:
        return ToolResult(
            success=False,
            error=f"Invalid cron expression '{cron_expression}'. Expected 5 time fields (minute hour day-of-month month day-of-week).",
        )

    new_line = f"{cron_expression.strip()} {command.strip()}\n"

    try:
        # Read current crontab
        current = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
        existing_lines = current.stdout if current.returncode == 0 else ""
        
        # Check if identical job already exists
        if new_line.strip() in existing_lines:
            return ToolResult(success=True, output="Job already exists in crontab.")

        updated_crontab = existing_lines.rstrip("\n") + "\n" + new_line

        write_proc = subprocess.run(
            ["crontab", "-"],
            input=updated_crontab,
            text=True,
            capture_output=True,
        )
        if write_proc.returncode == 0:
            return ToolResult(
                success=True,
                output=f"Successfully added cron job: {new_line.strip()}",
            )
        else:
            return ToolResult(success=False, error=write_proc.stderr.strip())
    except Exception as e:
        return ToolResult(success=False, error=str(e))
