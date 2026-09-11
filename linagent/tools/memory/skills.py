"""Dynamic runtime skill creation and plugin loader."""

import importlib.util
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

from linagent.core.config import load_config
from linagent.core.tools import ToolResult, default_registry

def load_user_skills() -> int:
    """Scan and import all custom Python skill modules from skills_dir."""
    cfg = load_config()
    skills_path = Path(cfg.skills_dir)
    if not skills_path.exists():
        skills_path.mkdir(parents=True, exist_ok=True)
        return 0

    loaded_count = 0
    for py_file in skills_path.glob("*.py"):
        if py_file.name.startswith("__"):
            continue
        try:
            module_name = f"linagent_custom_skill_{py_file.stem}"
            spec = importlib.util.spec_from_file_location(module_name, py_file)
            if spec and spec.loader:
                mod = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = mod
                spec.loader.exec_module(mod)
                loaded_count += 1
        except Exception as e:
            sys.stderr.write(f"[LinAgent] Failed loading skill {py_file}: {e}\n")

    return loaded_count

@default_registry.register(
    name="create_new_skill",
    description="Dynamically create and register a brand new Python tool/skill that LinAgent can use immediately. Python code must define a function with docstring and @default_registry.register decorator.",
    is_dangerous=True,
    requires_confirmation=True,
)
def create_new_skill(skill_name: str, python_code: str) -> ToolResult:
    """Save and dynamically load a new Python skill into LinAgent."""
    cfg = load_config()
    skills_path = Path(cfg.skills_dir)
    skills_path.mkdir(parents=True, exist_ok=True)

    clean_name = skill_name.lower().replace(" ", "_").replace("-", "_")
    target_file = skills_path / f"{clean_name}.py"

    # Prepend default imports if missing
    header = (
        "from linagent.core.tools import default_registry, ToolResult\n"
        "import os\nimport subprocess\n\n"
    )
    if "from linagent" not in python_code and "import default_registry" not in python_code:
        full_code = header + python_code
    else:
        full_code = python_code

    try:
        # Validate syntax before writing
        compile(full_code, str(target_file), "exec")

        with open(target_file, "w", encoding="utf-8") as f:
            f.write(full_code)

        # Load it dynamically
        module_name = f"linagent_custom_skill_{clean_name}"
        spec = importlib.util.spec_from_file_location(module_name, target_file)
        if spec and spec.loader:
            mod = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = mod
            spec.loader.exec_module(mod)

        return ToolResult(
            success=True,
            output=f"Skill '{clean_name}' created, validated, and loaded successfully at {target_file.resolve()}!",
            data={"path": str(target_file.resolve())},
        )
    except SyntaxError as se:
        return ToolResult(
            success=False,
            error=f"Python Syntax Error in skill code: {se}",
        )
    except Exception as e:
        return ToolResult(
            success=False,
            error=f"Failed to load new skill: {str(e)}",
        )

@default_registry.register(
    name="list_custom_skills",
    description="List all custom dynamically installed user skills.",
)
def list_custom_skills() -> ToolResult:
    """List installed skills in skills directory."""
    cfg = load_config()
    skills_path = Path(cfg.skills_dir)
    if not skills_path.exists():
        return ToolResult(success=True, output="No custom skills installed.")

    skills = [p.name for p in skills_path.glob("*.py") if not p.name.startswith("__")]
    if not skills:
        return ToolResult(success=True, output="No custom skills installed yet in " + str(skills_path))

    return ToolResult(
        success=True,
        output="Installed custom skills:\n" + "\n".join(f"- {s}" for s in skills),
        data={"skills": skills},
    )
