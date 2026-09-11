"""Lightweight FastAPI server for LinAgent Web Dashboard and REST API."""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

from linagent.core.agent import LinAgent
from linagent.core.config import load_config
from linagent.core.tools import default_registry
from linagent.tools.automation.system import get_system_overview
from linagent.tools.memory.store import default_memory

app = FastAPI(title="LinAgent API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = Path(__file__).parent / "static"
INDEX_FILE = STATIC_DIR / "index.html"

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = "default"

class DirectActionRequest(BaseModel):
    tool_name: str
    arguments: Dict[str, Any] = {}

# Reusable agent instance
_agent_instance: Optional[LinAgent] = None

def get_agent() -> LinAgent:
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = LinAgent(config=load_config())
    return _agent_instance

@app.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    if INDEX_FILE.exists():
        return FileResponse(INDEX_FILE)
    return HTMLResponse("<h2>LinAgent is running. Web UI file not found.</h2>")

@app.get("/api/system")
async def api_system():
    res = get_system_overview()
    return res.data or {"raw": res.output}

@app.get("/api/tools")
async def api_tools():
    tools = []
    for t in default_registry.list_tools():
        tools.append({
            "name": t.name,
            "description": t.description,
            "is_dangerous": t.is_dangerous,
            "requires_confirmation": t.requires_confirmation,
            "parameters": t.schema.get("function", {}).get("parameters", {}),
        })
    return {"tools": tools}

@app.get("/api/memories")
async def api_memories(query: Optional[str] = None):
    if query:
        return {"memories": default_memory.search(query)}
    return {"memories": default_memory.list_all()}

@app.post("/api/chat")
async def api_chat(req: ChatRequest):
    agent = get_agent()
    events: List[Dict[str, Any]] = []

    def on_step(evt: Dict[str, Any]):
        events.append(evt)

    try:
        reply = agent.step(
            user_input=req.message,
            on_step_callback=on_step,
        )
        return {
            "reply": reply,
            "trace": events,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/action")
async def api_action(req: DirectActionRequest):
    res = default_registry.execute(req.tool_name, req.arguments)
    return {
        "success": res.success,
        "output": res.output,
        "error": res.error,
        "data": res.data,
    }

def start_server(host: str = "127.0.0.1", port: int = 8808):
    """Launch the uvicorn web server."""
    import uvicorn
    print(f"\n🚀 LinAgent Web Dashboard starting at http://{host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="info")
