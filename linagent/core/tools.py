"""Tool registry and execution infrastructure for LinAgent."""

import inspect
import json
import traceback
from typing import Any, Callable, Dict, List, Optional, get_type_hints
from pydantic import BaseModel, Field

class ToolResult(BaseModel):
    success: bool = True
    output: str = ""
    error: Optional[str] = None
    data: Optional[Dict[str, Any]] = None

    def to_llm_string(self) -> str:
        if not self.success:
            return f"ERROR: {self.error or 'Operation failed'}\nOutput: {self.output}"
        return self.output if self.output else "Success (no output)"

class ToolDefinition(BaseModel):
    name: str
    description: str
    parameters: Dict[str, Any]
    is_dangerous: bool = False
    requires_confirmation: bool = False

class RegisteredTool:
    def __init__(
        self,
        name: str,
        description: str,
        func: Callable[..., Any],
        is_dangerous: bool = False,
        requires_confirmation: bool = False,
    ):
        self.name = name
        self.description = description
        self.func = func
        self.is_dangerous = is_dangerous
        self.requires_confirmation = requires_confirmation
        self.schema = self._build_schema()

    def _build_schema(self) -> Dict[str, Any]:
        """Generate OpenAI-compatible tool calling JSON schema from function signature."""
        sig = inspect.signature(self.func)
        try:
            hints = get_type_hints(self.func)
        except Exception:
            hints = {}

        properties: Dict[str, Any] = {}
        required: List[str] = []

        type_map = {
            str: "string",
            int: "integer",
            float: "number",
            bool: "boolean",
            list: "array",
            dict: "object",
        }

        for param_name, param in sig.parameters.items():
            if param_name in ("self", "cls"):
                continue
            
            param_type = hints.get(param_name, str)
            # Basic type inference
            json_type = "string"
            if param_type in type_map:
                json_type = type_map[param_type]
            elif hasattr(param_type, "__origin__"):
                origin = param_type.__origin__
                if origin in type_map:
                    json_type = type_map[origin]

            properties[param_name] = {
                "type": json_type,
                "description": f"Parameter: {param_name}",
            }

            if param.default is inspect.Parameter.empty:
                required.append(param_name)

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }

    def execute(self, **kwargs: Any) -> ToolResult:
        """Execute the tool function with provided keyword arguments."""
        try:
            res = self.func(**kwargs)
            if isinstance(res, ToolResult):
                return res
            if isinstance(res, (dict, list)):
                return ToolResult(success=True, output=json.dumps(res, indent=2), data=res if isinstance(res, dict) else None)
            return ToolResult(success=True, output=str(res))
        except Exception as e:
            tb = traceback.format_exc()
            return ToolResult(success=False, error=str(e), output=tb)

class ToolRegistry:
    def __init__(self) -> None:
        self._tools: Dict[str, RegisteredTool] = {}

    def register(
        self,
        name: Optional[str] = None,
        description: Optional[str] = None,
        is_dangerous: bool = False,
        requires_confirmation: bool = False,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Decorator to register a function as an agent tool."""
        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            tool_name = name or func.__name__
            tool_desc = description or (func.__doc__ or "").strip() or f"Execute {tool_name}"
            
            registered = RegisteredTool(
                name=tool_name,
                description=tool_desc,
                func=func,
                is_dangerous=is_dangerous,
                requires_confirmation=requires_confirmation,
            )
            self._tools[tool_name] = registered
            return func
        return decorator

    def register_tool_instance(self, tool: RegisteredTool) -> None:
        self._tools[tool.name] = tool

    def get_tool(self, name: str) -> Optional[RegisteredTool]:
        return self._tools.get(name)

    def list_tools(self) -> List[RegisteredTool]:
        return list(self._tools.values())

    def get_schemas(self) -> List[Dict[str, Any]]:
        return [tool.schema for tool in self._tools.values()]

    def execute(self, tool_name: str, arguments: Dict[str, Any]) -> ToolResult:
        tool = self.get_tool(tool_name)
        if not tool:
            return ToolResult(
                success=False,
                error=f"Tool '{tool_name}' not found. Available tools: {', '.join(self._tools.keys())}",
            )
        return tool.execute(**arguments)

# Global default registry
default_registry = ToolRegistry()
tool = default_registry.register
