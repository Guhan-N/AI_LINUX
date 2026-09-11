"""Safe bash and shell automation engine for Linux."""

import os
import re
import shlex
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from linagent.core.tools import ToolResult, default_registry

# Dangerous command patterns that should trigger safety warnings or blocking
DANGEROUS_PATTERNS = [
    r"\brm\s+-[a-zA-Z0-9]*[rR][a-zA-Z0-9]*\s+(?:/|/\*|~)(?:\s|$)",  # rm -rf / or rm -rf /* or rm -rf ~
    r"\brm\s+-[a-zA-Z0-9]*[rR][a-zA-Z0-9]*\s+--no-preserve-root",    # rm --no-preserve-root
    r"\bmkfs(\.\w+)?\s+",                                            # mkfs formatting
    r"\bdd\s+if=.*?of=/dev/[a-z]+",                                   # raw dd to disk
    r":\(\)\s*\{\s*:\|:&\s*\};:",                                     # fork bomb
    r">\s*/dev/sd[a-z]",                                              # redirecting to disk device
    r">\s*/dev/nvme[0-9]",                                            # redirecting to nvme
    r"\bchmod\s+(-R\s+)?777\s+/(?:\s|$)",                             # chmod 777 root
    r"\bchown\s+(-R\s+)?.*?\s+/(?:\s|$)",                             # chown root
    r"\bshutdown\b",                                                  # shutdown
    r"\breboot\b",                                                    # reboot
    r"\binit\s+0\b",                                                  # halt
]

# Read-only or safe command prefixes that never cause system damage
SAFE_PREFIXES = (
    "ls", "dir", "cat", "head", "tail", "grep", "rg", "find", "pwd",
    "echo", "uname", "whoami", "id", "uptime", "free", "df", "du",
    "ps", "top", "htop", "which", "whereis", "file", "wc", "stat",
    "date", "cal", "hostname", "netstat", "ss", "ip", "ifconfig",
    "systemctl status", "systemctl is-active", "journalctl", "dmesg",
    "env", "printenv", "diff", "curl -I", "curl -s", "ping -c",
)

class ShellSession:
    """Manages shell execution state and working directory."""

    def __init__(self, initial_cwd: Optional[str] = None):
        self.cwd = initial_cwd or os.getcwd()

    def is_safe(self, command: str) -> Tuple[bool, Optional[str]]:
        """Assess whether a command is dangerous or safe."""
        cmd_stripped = command.strip()

        # Check dangerous patterns
        for pattern in DANGEROUS_PATTERNS:
            if re.search(pattern, cmd_stripped, re.IGNORECASE):
                return False, f"Dangerous command pattern detected: matches '{pattern}'"

        return True, None

    def execute(
        self,
        command: str,
        timeout: int = 60,
        custom_cwd: Optional[str] = None,
    ) -> ToolResult:
        """Execute a shell command in a persistent bash subshell."""
        target_cwd = custom_cwd or self.cwd

        # Handle 'cd <dir>' command to update persistent state
        cd_match = re.match(r"^cd\s+(.+)$", command.strip())
        if cd_match:
            new_dir = os.path.expanduser(cd_match.group(1).strip().strip("'\""))
            resolved = Path(target_cwd) / new_dir
            try:
                resolved = resolved.resolve()
                if resolved.is_dir():
                    self.cwd = str(resolved)
                    return ToolResult(
                        success=True,
                        output=f"Changed directory to {self.cwd}",
                        data={"cwd": self.cwd},
                    )
                else:
                    return ToolResult(
                        success=False,
                        error=f"Directory does not exist: {new_dir}",
                    )
            except Exception as e:
                return ToolResult(success=False, error=str(e))

        # Check safety
        is_safe, danger_reason = self.is_safe(command)
        if not is_safe:
            return ToolResult(
                success=False,
                error=f"SAFETY VIOLATION BLOCKED: {danger_reason}. Re-run with confirmation if you explicitly want this action.",
            )

        # Select shell
        if os.name == "nt":
            shell_cmd = ["powershell", "-NoProfile", "-Command", command]
        else:
            # Linux / Unix bash with pipefail
            shell_cmd = ["/bin/bash", "-c", f"set -o pipefail; {command}"]

        try:
            proc = subprocess.run(
                shell_cmd,
                cwd=self.cwd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )

            stdout = proc.stdout.strip()
            stderr = proc.stderr.strip()
            exit_code = proc.returncode

            combined_output = []
            if stdout:
                combined_output.append(stdout)
            if stderr:
                combined_output.append(f"[stderr]\n{stderr}")

            output_str = "\n\n".join(combined_output) if combined_output else "(no output)"

            if exit_code == 0:
                return ToolResult(
                    success=True,
                    output=output_str,
                    data={"exit_code": exit_code, "cwd": self.cwd},
                )
            else:
                return ToolResult(
                    success=False,
                    output=output_str,
                    error=f"Command exited with non-zero exit code: {exit_code}",
                    data={"exit_code": exit_code, "cwd": self.cwd},
                )

        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False,
                error=f"Command timed out after {timeout} seconds",
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Execution error: {str(e)}",
            )

# Global shell session
default_shell_session = ShellSession()

@default_registry.register(
    name="execute_shell_command",
    description="Execute a bash/shell command on the Linux system. Returns stdout, stderr, and exit code. Tracks working directory.",
)
def execute_shell_command(
    command: str,
    timeout_seconds: int = 60,
) -> ToolResult:
    """Execute a shell command on the host Linux system."""
    return default_shell_session.execute(command=command, timeout=timeout_seconds)

@default_registry.register(
    name="check_command_installed",
    description="Check if a specific binary or command line tool is installed on the system (e.g. 'git', 'docker', 'curl', 'htop').",
)
def check_command_installed(command_name: str) -> ToolResult:
    """Check if a command exists in PATH."""
    import shutil
    path = shutil.which(command_name)
    if path:
        return ToolResult(
            success=True,
            output=f"Command '{command_name}' is installed at: {path}",
            data={"installed": True, "path": path},
        )
    return ToolResult(
        success=False,
        output=f"Command '{command_name}' was NOT found in PATH.",
        data={"installed": False, "path": None},
    )
