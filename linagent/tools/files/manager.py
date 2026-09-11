"""File system exploration, inspection, and manipulation tools."""

import os
import shutil
from pathlib import Path
from typing import List, Optional

from linagent.core.tools import ToolResult, default_registry

@default_registry.register(
    name="read_file",
    description="Read the text content of a file on the Linux filesystem.",
)
def read_file(path: str, max_lines: int = 500, start_line: int = 1) -> ToolResult:
    """Read lines from a file."""
    p = Path(os.path.expanduser(path))
    if not p.exists():
        return ToolResult(success=False, error=f"File not found: {path}")
    if not p.is_file():
        return ToolResult(success=False, error=f"Path is not a regular file: {path}")

    try:
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        total_lines = len(lines)
        start_idx = max(0, start_line - 1)
        end_idx = min(total_lines, start_idx + max_lines)
        selected_lines = lines[start_idx:end_idx]

        numbered = [f"{i + 1:4d} | {line}" for i, line in enumerate(selected_lines, start=start_idx)]
        header = f"--- {p.resolve()} (lines {start_idx + 1}-{end_idx} of {total_lines}) ---\n"
        return ToolResult(success=True, output=header + "".join(numbered))
    except Exception as e:
        return ToolResult(success=False, error=str(e))

@default_registry.register(
    name="write_file",
    description="Write text content to a file. Creates parent directories automatically if needed.",
)
def write_file(path: str, content: str, overwrite: bool = True) -> ToolResult:
    """Write text content to a destination file."""
    p = Path(os.path.expanduser(path))
    if p.exists() and not overwrite:
        return ToolResult(
            success=False,
            error=f"File already exists at {path} and overwrite is False.",
        )

    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(content)
        return ToolResult(
            success=True,
            output=f"Successfully wrote {len(content)} characters to {p.resolve()}",
        )
    except Exception as e:
        return ToolResult(success=False, error=str(e))

@default_registry.register(
    name="append_file",
    description="Append text content to the end of a file.",
)
def append_file(path: str, content: str) -> ToolResult:
    """Append content to a file."""
    p = Path(os.path.expanduser(path))
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "a", encoding="utf-8") as f:
            f.write(content)
        return ToolResult(
            success=True,
            output=f"Successfully appended to {p.resolve()}",
        )
    except Exception as e:
        return ToolResult(success=False, error=str(e))

@default_registry.register(
    name="search_files_by_name",
    description="Find files matching a filename wildcard pattern (e.g. '*.py', '*nginx*') in a directory.",
)
def search_files_by_name(directory: str, pattern: str = "*", max_results: int = 50) -> ToolResult:
    """Find files by glob pattern."""
    root = Path(os.path.expanduser(directory))
    if not root.exists():
        return ToolResult(success=False, error=f"Directory not found: {directory}")

    results = []
    try:
        for p in root.rglob(pattern):
            if len(results) >= max_results:
                break
            # Skip hidden git or cache dirs
            parts = p.parts
            if any(part.startswith(".") and part not in (".", "..") for part in parts):
                continue
            is_dir = "[DIR] " if p.is_dir() else "      "
            results.append(f"{is_dir}{p.resolve()}")

        if not results:
            return ToolResult(success=True, output=f"No matching files found for '{pattern}' in {directory}")
        return ToolResult(success=True, output="\n".join(results))
    except Exception as e:
        return ToolResult(success=False, error=str(e))

@default_registry.register(
    name="search_text_in_files",
    description="Search for a text pattern or regex across files in a directory.",
)
def search_text_in_files(
    directory: str,
    query: str,
    file_extension: Optional[str] = None,
    max_results: int = 30,
) -> ToolResult:
    """Search for string within file contents."""
    root = Path(os.path.expanduser(directory))
    if not root.exists():
        return ToolResult(success=False, error=f"Directory not found: {directory}")

    matches = []
    try:
        for p in root.rglob(f"*{file_extension}" if file_extension else "*"):
            if len(matches) >= max_results:
                break
            if not p.is_file():
                continue
            # Skip binary / large files
            if p.stat().st_size > 1_000_000:
                continue
            # Skip hidden dirs
            if any(part.startswith(".") for part in p.parts):
                continue

            try:
                with open(p, "r", encoding="utf-8", errors="ignore") as f:
                    for line_num, line in enumerate(f, 1):
                        if query in line:
                            matches.append(f"{p}:{line_num}: {line.strip()}")
                            if len(matches) >= max_results:
                                break
            except Exception:
                continue

        if not matches:
            return ToolResult(success=True, output=f"No occurrences of '{query}' found in {directory}")
        return ToolResult(success=True, output="\n".join(matches))
    except Exception as e:
        return ToolResult(success=False, error=str(e))
