"""Command-line interface for LinAgent."""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Optional

# Ensure UTF-8 output on all platforms
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from linagent import __version__
from linagent.core.agent import LinAgent
from linagent.core.config import LinAgentConfig, load_config, save_config
from linagent.core.tools import default_registry

def _print_banner(cfg: LinAgentConfig) -> None:
    print(r"""
  _      _             _                    _   
 | |    (_)           / \   __ _  ___ _ __ | |_ 
 | |    | | _  _     / _ \ / _` |/ _ \ '_ \| __|
 | |___ | |(_)| |_  / ___ \ (_| |  __/ | | | |_ 
 |_____||_|    (_) /_/   \_\__, |\___|_| |_|\__|
                           |___/                
    """[1:])
    print(f"  LinAgent v{__version__} | Lightweight Linux AI Assistant")
    failover_badge = f"ON ({len(cfg.failover_providers)} providers)" if cfg.failover_enabled and cfg.failover_providers else "OFF"
    print(f"  Backend: {cfg.provider.upper()} ({cfg.model}) | Smart Failover: {failover_badge} | Safe Mode: {'ON' if cfg.safe_mode else 'OFF'}")
    print(f"  Type '/help' for commands, '/exit' to quit.\n")

def interactive_chat(agent: LinAgent) -> None:
    """Run interactive TUI / CLI chat session."""
    _print_banner(agent.config)

    while True:
        try:
            user_input = input("linagent> ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting LinAgent. Goodbye!")
            break

        if not user_input:
            continue

        # Handle slash commands
        if user_input.lower() in ("/exit", "/quit", "exit", "quit"):
            print("Goodbye!")
            break
        elif user_input.lower() in ("/clear", "clear"):
            agent.reset()
            print("[LinAgent] Conversation history cleared.\n")
            continue
        elif user_input.lower() in ("/tools", "tools"):
            print("\nAvailable Registered Tools:")
            for t in agent.registry.list_tools():
                badge = "[SAFE]" if not t.is_dangerous else "[REQUIRES CONFIRMATION]"
                print(f"  * {t.name:<25} {badge:<24} : {t.description}")
            print()
            continue
        elif user_input.lower() in ("/memory", "memory"):
            from linagent.tools.memory.store import default_memory
            mems = default_memory.list_all(limit=20)
            print(f"\nStored Memories ({len(mems)} total):")
            for m in mems:
                print(f"  * [{m['category'].upper()}] {m['key']}: {m['content']}")
            print()
            continue
        elif user_input.lower() in ("/help", "help"):
            print("\nLinAgent Commands:")
            print("  /tools   - List all available system, browsing, and learning tools")
            print("  /memory  - Show stored long-term memories")
            print("  /clear   - Clear current conversation context")
            print("  /exit    - Exit LinAgent")
            print("  Any text - Ask the agent to execute tasks, browse, monitor, or answer\n")
            continue

        # Execute agent step
        def on_step(event: dict) -> None:
            etype = event.get("type")
            if etype == "tool_start":
                args_summary = json.dumps(event.get("arguments", {}))
                if len(args_summary) > 70:
                    args_summary = args_summary[:67] + "..."
                print(f"  ⚡ Running tool [{event.get('tool')}] with {args_summary}")
            elif etype == "tool_end":
                status = "✓ Done" if event.get("success") else "✗ Failed"
                print(f"    └─ {status}")

        def confirm_action(tool_name: str, args_str: str) -> bool:
            print(f"\n⚠️  SAFETY WARNING: The tool '{tool_name}' performs system modifications.")
            print(f"Arguments:\n{args_str}")
            resp = input("Proceed? [y/N]: ").strip().lower()
            return resp in ("y", "yes")

        print()
        response = agent.step(
            user_input=user_input,
            on_step_callback=on_step,
            confirm_callback=confirm_action,
        )
        print(f"\n{response}\n")

def run_oneshot(agent: LinAgent, task: str) -> None:
    """Execute a single command headless and output result."""
    def on_step(event: dict) -> None:
        if event.get("type") == "tool_start":
            sys.stderr.write(f"[LinAgent] -> Tool: {event.get('tool')}\n")

    response = agent.step(user_input=task, on_step_callback=on_step)
    print(response)

def configure_wizard() -> None:
    """Interactive CLI configuration setup wizard."""
    cfg = load_config()
    print("\n--- LinAgent Configuration Wizard ---\n")
    print("Select LLM Provider:")
    print("  1) Ollama (100% Free, Local, Offline - e.g. llama3.2, qwen2.5-coder)")
    print("  2) Groq (Free fast cloud API - e.g. llama-3.3-70b-versatile)")
    print("  3) Google Gemini (Free tier, fast - e.g. gemini-2.0-flash)")
    print("  4) OpenAI (e.g. gpt-4o-mini, gpt-4o)")
    print("  5) Custom OpenAI-compatible endpoint (vLLM, LocalAI, LM Studio)")

    choice = input(f"Choice [current: {cfg.provider}]: ").strip()
    provider_map = {"1": "ollama", "2": "groq", "3": "gemini", "4": "openai", "5": "custom"}
    if choice in provider_map:
        cfg.provider = provider_map[choice]

    if cfg.provider == "ollama":
        model = input(f"Ollama Model [current: {cfg.model or 'llama3.2:3b'}]: ").strip()
        if model:
            cfg.model = model
        base_url = input("Ollama URL [default: http://localhost:11434/v1]: ").strip()
        if base_url:
            cfg.base_url = base_url
    elif cfg.provider in ("groq", "gemini", "openai"):
        key_input = input(f"Enter API Key(s) for {cfg.provider.upper()} (comma-separated for rotation): ").strip()
        if key_input:
            keys = [k.strip() for k in key_input.split(",") if k.strip()]
            cfg.api_keys = keys
            cfg.api_key = keys[0] if keys else None
        model = input(f"Model name [current: {cfg.model}]: ").strip()
        if model:
            cfg.model = model
    elif cfg.provider == "custom":
        url = input("Endpoint Base URL (e.g. http://localhost:8000/v1): ").strip()
        if url:
            cfg.base_url = url
        model = input("Model name: ").strip()
        if model:
            cfg.model = model

    failover_choice = input(f"Enable Multi-Provider Failover Waterfall? (Gemini ➔ Groq ➔ OpenRouter ➔ Local Ollama) [Y/n]: ").strip().lower()
    if failover_choice in ("n", "no"):
        cfg.failover_enabled = False
    else:
        cfg.failover_enabled = True

    safe = input(f"Enable Safe Mode? (asks confirmation for dangerous commands) [Y/n]: ").strip().lower()
    if safe in ("n", "no"):
        cfg.safe_mode = False
    else:
        cfg.safe_mode = True

    saved_path = save_config(cfg)
    print(f"\n✓ Configuration successfully saved to: {saved_path}\n")

def generate_systemd_service() -> None:
    """Generate systemd service file."""
    import sys
    py_path = sys.executable
    service_content = f"""[Unit]
Description=LinAgent AI Assistant Service
After=network.target

[Service]
Type=simple
User={os.getenv('USER', 'root')}
WorkingDirectory={os.path.expanduser('~')}
ExecStart={py_path} -m linagent.cli.main web
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
"""
    dest = Path("linagent.service")
    with open(dest, "w", encoding="utf-8") as f:
        f.write(service_content)
    print(f"Generated {dest.resolve()}")
    print("To install as systemd service:")
    print(f"  sudo cp {dest.resolve()} /etc/systemd/system/")
    print("  sudo systemctl daemon-reload")
    print("  sudo systemctl enable --now linagent")

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="linagent",
        description="LinAgent - Lightweight Autonomous AI Assistant for Linux",
    )
    parser.add_argument("-v", "--version", action="version", version=f"LinAgent {__version__}")
    
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # chat command (default)
    subparsers.add_parser("chat", help="Start interactive conversational assistant session")

    # run command
    run_parser = subparsers.add_parser("run", help="Execute a one-shot task or automation instruction")
    run_parser.add_argument("task", type=str, help="The instruction or task for the agent to execute")

    # config command
    subparsers.add_parser("config", help="Run interactive configuration setup wizard")

    # tools command
    subparsers.add_parser("tools", help="List all registered tools")

    # memory command
    mem_parser = subparsers.add_parser("memory", help="Inspect and manage long-term memories")
    mem_parser.add_argument("action", choices=["list", "search", "clear"], default="list", nargs="?")
    mem_parser.add_argument("query", type=str, nargs="?", default="")

    # web command
    web_parser = subparsers.add_parser("web", help="Start lightweight Web Dashboard and REST API server")
    web_parser.add_argument("--port", type=int, default=8808, help="Port to listen on (default: 8808)")
    web_parser.add_argument("--host", type=str, default="127.0.0.1", help="Host address (default: 127.0.0.1)")

    # service command
    subparsers.add_parser("service", help="Generate systemd service file for running LinAgent in background")

    args = parser.parse_args()

    cfg = load_config()
    agent = LinAgent(config=cfg)

    if args.command == "run":
        run_oneshot(agent, args.task)
    elif args.command == "config":
        configure_wizard()
    elif args.command == "tools":
        print("\nRegistered Tools in LinAgent:")
        for t in agent.registry.list_tools():
            print(f"  * {t.name:<25} : {t.description}")
        print()
    elif args.command == "memory":
        from linagent.tools.memory.store import default_memory
        if args.action == "list":
            items = default_memory.list_all()
            print(f"\nStored Memories ({len(items)} items):")
            for m in items:
                print(f"  * [{m['category'].upper()}] {m['key']}: {m['content']}")
        elif args.action == "search":
            items = default_memory.search(args.query or "")
            print(f"\nSearch results for '{args.query}':")
            for m in items:
                print(f"  • [{m['category'].upper()}] {m['key']}: {m['content']}")
        elif args.action == "clear":
            import os
            if os.path.exists(cfg.memory_db_path):
                os.remove(cfg.memory_db_path)
            print("Memory database cleared.")
    elif args.command == "service":
        generate_systemd_service()
    elif args.command == "web":
        from linagent.web.server import start_server
        start_server(host=args.host, port=args.port)
    else:
        # Default to interactive chat
        interactive_chat(agent)

if __name__ == "__main__":
    main()
