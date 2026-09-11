"""Autonomous ReAct agent loop for LinAgent."""

import json
import os
import platform
from typing import Any, Callable, Dict, Generator, List, Optional

from linagent.core.config import LinAgentConfig, load_config
from linagent.core.llm import BaseLLMClient, Message, create_llm_client
from linagent.core.tools import ToolRegistry, ToolResult
import linagent.tools  # registers all tools
from linagent.core.tools import default_registry

SYSTEM_PROMPT = """You are LinAgent, an autonomous, ultra-lightweight AI assistant running natively on Linux.
Your mission is to help the user manage, monitor, automate, browse, search, and troubleshoot their Linux system seamlessly.

### CORE CAPABILITIES
1. **Linux Automation & Shell**: You can execute bash commands, check running services with systemctl, monitor top processes, inspect system logs with journalctl, and schedule cron jobs.
2. **File & System Management**: You can read, write, edit, and search for files, inspect directory trees, and view disk and memory usage.
3. **Web Search & Browsing**: You can search the internet for real-time information, documentation, and error fixes using DuckDuckGo, and fetch web pages to extract readable articles and docs.
4. **Learning & Memory**: You have persistent memory (SQLite). You can remember user preferences (`remember_fact`), recall past facts (`recall_memories`), and learn troubleshooting solutions (`learn_solution`, `find_solution`).
5. **Desktop & GUI Interaction**: You CAN interact directly with the Linux graphical desktop! You can open websites in the user's real desktop browser (`open_in_browser`), launch graphical apps like Firefox, VLC, or text editors (`launch_gui_app`), type into active windows (`type_text_into_active_window`), and take screenshots (`take_screenshot`). When the user asks to "open browser", "open youtube", or launch any GUI software, use your desktop tools! NEVER say you cannot open a browser or interact with the GUI.
6. **Extensibility**: You can dynamically write and load new Python tools (`create_new_skill`) when the user asks for new custom capabilities.

### OPERATIONAL GUIDELINES
- Always be concise, accurate, and direct.
- When the user asks to open a browser or website, use `open_in_browser`.
- When the user asks to search the web for information, use `search_web`.
- Before executing a potentially risky or destructive command (e.g. wiping directories, modifying system configs, stopping critical services), inspect the system state first and explain what you are doing.
- Store important learned user preferences or recurring server fixes into memory so you remember them next time.
"""

class AgentStep(dict):
    """Represents a single step in the agent reasoning and action loop."""
    pass

class LinAgent:
    def __init__(
        self,
        config: Optional[LinAgentConfig] = None,
        registry: Optional[ToolRegistry] = None,
        llm_client: Optional[BaseLLMClient] = None,
    ):
        self.config = config or load_config()
        self.registry = registry or default_registry
        self.llm = llm_client or create_llm_client(self.config)
        self.messages: List[Message] = []
        self._init_system_prompt()

    def _init_system_prompt(self) -> None:
        """Inject system prompt with environment context."""
        distro = "Linux"
        try:
            from linagent.tools.automation.system import _read_os_release
            distro = _read_os_release()
        except Exception:
            pass

        sys_context = (
            f"\n\n### CURRENT HOST ENVIRONMENT\n"
            f"- OS: {distro}\n"
            f"- Architecture: {platform.machine()}\n"
            f"- Current Working Directory: {os.getcwd()}\n"
        )
        self.messages = [Message(role="system", content=SYSTEM_PROMPT + sys_context)]

    def reset(self) -> None:
        """Reset conversational history."""
        self._init_system_prompt()

    def step(
        self,
        user_input: str,
        max_iterations: int = 10,
        on_step_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
        confirm_callback: Optional[Callable[[str, str], bool]] = None,
    ) -> str:
        """Run the ReAct autonomous loop to fulfill the user's request."""
        self.messages.append(Message(role="user", content=user_input))

        tools_schema = self.registry.get_schemas()
        iterations = 0

        while iterations < max_iterations:
            iterations += 1

            # Query LLM
            response = self.llm.chat(self.messages, tools=tools_schema)

            # If no tool calls, this is the final answer
            if not response.tool_calls:
                final_content = response.content
                self.messages.append(Message(role="assistant", content=final_content))
                if on_step_callback:
                    on_step_callback({
                        "type": "final_answer",
                        "content": final_content,
                    })
                return final_content

            # Otherwise, append assistant response containing tool calls
            self.messages.append(Message(
                role="assistant",
                content=response.content or "",
                tool_calls=response.tool_calls,
            ))

            # Process each tool call
            for tc in response.tool_calls:
                tool_call_id = tc.get("id", f"call_{iterations}")
                func_info = tc.get("function", {})
                tool_name = func_info.get("name", "")
                raw_args = func_info.get("arguments", "{}")

                try:
                    args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                except Exception:
                    args = {}

                if on_step_callback:
                    on_step_callback({
                        "type": "tool_start",
                        "tool": tool_name,
                        "arguments": args,
                    })

                # Check confirmation if required
                tool_obj = self.registry.get_tool(tool_name)
                approved = True
                if tool_obj and tool_obj.requires_confirmation and self.config.safe_mode:
                    if confirm_callback:
                        approved = confirm_callback(tool_name, json.dumps(args, indent=2))
                    else:
                        # Auto-approve if safe mode callback not hooked or in headless
                        approved = True

                if not approved:
                    tool_result = ToolResult(
                        success=False,
                        error="Action cancelled by user safety confirmation.",
                    )
                else:
                    tool_result = self.registry.execute(tool_name, args)

                if on_step_callback:
                    on_step_callback({
                        "type": "tool_end",
                        "tool": tool_name,
                        "success": tool_result.success,
                        "output": tool_result.output,
                        "error": tool_result.error,
                    })

                # Append tool result to conversation history
                self.messages.append(Message(
                    role="tool",
                    name=tool_name,
                    tool_call_id=tool_call_id,
                    content=tool_result.to_llm_string(),
                ))

        # Max iterations reached fallback
        fallback = "Completed operations, reached maximum step limit."
        self.messages.append(Message(role="assistant", content=fallback))
        return fallback
