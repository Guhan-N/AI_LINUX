"""Linux native system telemetry and monitoring tools."""

import os
import platform
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from linagent.core.tools import ToolResult, default_registry

def _read_proc_meminfo() -> Dict[str, int]:
    """Parse /proc/meminfo on Linux into kB values."""
    mem = {}
    proc_path = Path("/proc/meminfo")
    if proc_path.exists():
        try:
            with open(proc_path, "r", encoding="utf-8") as f:
                for line in f:
                    parts = line.split(":")
                    if len(parts) == 2:
                        key = parts[0].strip()
                        val_parts = parts[1].strip().split()
                        if val_parts:
                            try:
                                mem[key] = int(val_parts[0])
                            except ValueError:
                                pass
        except Exception:
            pass
    return mem

def _read_os_release() -> str:
    """Parse /etc/os-release or fallback to platform.platform()."""
    release_path = Path("/etc/os-release")
    if release_path.exists():
        try:
            with open(release_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("PRETTY_NAME="):
                        return line.split("=", 1)[1].strip().strip('"')
        except Exception:
            pass
    return f"{platform.system()} {platform.release()}"

@default_registry.register(
    name="get_system_overview",
    description="Retrieve a quick high-level summary of the Linux system: OS distribution, kernel, uptime, CPU cores, RAM usage, and root disk capacity.",
)
def get_system_overview() -> ToolResult:
    """Returns a consolidated system status overview."""
    info: Dict[str, Any] = {
        "os": _read_os_release(),
        "kernel": platform.release(),
        "arch": platform.machine(),
        "hostname": platform.node(),
    }

    # Uptime
    uptime_path = Path("/proc/uptime")
    if uptime_path.exists():
        try:
            with open(uptime_path, "r", encoding="utf-8") as f:
                total_seconds = float(f.read().split()[0])
                days = int(total_seconds // 86400)
                hours = int((total_seconds % 86400) // 3600)
                minutes = int((total_seconds % 3600) // 60)
                info["uptime"] = f"{days}d {hours}h {minutes}m"
        except Exception:
            info["uptime"] = "unknown"
    else:
        info["uptime"] = "N/A"

    # Memory from /proc/meminfo
    mem = _read_proc_meminfo()
    if mem:
        total_kb = mem.get("MemTotal", 0)
        avail_kb = mem.get("MemAvailable", mem.get("MemFree", 0))
        used_kb = total_kb - avail_kb
        info["memory"] = {
            "total_mb": round(total_kb / 1024, 1),
            "used_mb": round(used_kb / 1024, 1),
            "free_mb": round(avail_kb / 1024, 1),
            "percent_used": round((used_kb / total_kb * 100) if total_kb > 0 else 0, 1),
        }
    else:
        # Fallback
        info["memory"] = "Unavailable"

    # CPU load average
    load_path = Path("/proc/loadavg")
    if load_path.exists():
        try:
            with open(load_path, "r", encoding="utf-8") as f:
                loads = f.read().split()[:3]
                info["load_avg"] = {
                    "1min": loads[0],
                    "5min": loads[1],
                    "15min": loads[2],
                }
        except Exception:
            pass

    # Root Disk space
    try:
        if os.name != "nt":
            stat = os.statvfs("/")
            total_disk = (stat.f_blocks * stat.f_frsize) / (1024 ** 3)
            free_disk = (stat.f_bavail * stat.f_frsize) / (1024 ** 3)
            used_disk = total_disk - free_disk
            info["disk_root"] = {
                "total_gb": round(total_disk, 1),
                "used_gb": round(used_disk, 1),
                "free_gb": round(free_disk, 1),
                "percent_used": round((used_disk / total_disk * 100) if total_disk > 0 else 0, 1),
            }
        else:
            import shutil
            total, used, free = shutil.disk_usage("C:\\")
            info["disk_root"] = {
                "total_gb": round(total / (1024 ** 3), 1),
                "used_gb": round(used / (1024 ** 3), 1),
                "free_gb": round(free / (1024 ** 3), 1),
            }
    except Exception as e:
        info["disk_root"] = f"Error: {e}"

    lines = [
        f"OS: {info['os']} ({info['kernel']} {info['arch']})",
        f"Hostname: {info['hostname']}",
        f"Uptime: {info.get('uptime', 'N/A')}",
    ]
    if isinstance(info.get("memory"), dict):
        m = info["memory"]
        lines.append(f"Memory: {m['used_mb']} MB / {m['total_mb']} MB ({m['percent_used']}% used)")
    if "load_avg" in info:
        l = info["load_avg"]
        lines.append(f"Load Average: {l['1min']} (1m), {l['5min']} (5m), {l['15min']} (15m)")
    if isinstance(info.get("disk_root"), dict):
        d = info["disk_root"]
        lines.append(f"Disk (/): {d['used_gb']} GB / {d['total_gb']} GB used, {d['free_gb']} GB free")

    return ToolResult(
        success=True,
        output="\n".join(lines),
        data=info,
    )

@default_registry.register(
    name="get_top_processes",
    description="List the top resource-consuming processes on the system (sorted by 'cpu' or 'mem'). Returns PID, User, %CPU, %MEM, Command.",
)
def get_top_processes(limit: int = 10, sort_by: str = "cpu") -> ToolResult:
    """List top processes sorted by CPU or memory usage."""
    if os.name == "nt":
        # Windows fallback
        cmd = ["powershell", "-NoProfile", "-Command", 
               f"Get-Process | Sort-Object {'CPU' if sort_by == 'cpu' else 'WS'} -Descending | Select-Object -First {limit} Id,ProcessName,CPU,WorkingSet"]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            return ToolResult(success=True, output=res.stdout.strip())
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    # Linux native ps command
    sort_flag = "-%cpu" if sort_by.lower() == "cpu" else "-%mem"
    cmd = ["ps", "-eo", "pid,user,%cpu,%mem,stat,start,time,comm", f"--sort={sort_flag}"]
    
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if res.returncode != 0:
            return ToolResult(success=False, error=res.stderr.strip())
        
        lines = res.stdout.strip().split("\n")
        header = lines[0]
        processes = lines[1 : limit + 1]
        output = "\n".join([header] + processes)
        return ToolResult(success=True, output=output)
    except Exception as e:
        return ToolResult(success=False, error=str(e))
