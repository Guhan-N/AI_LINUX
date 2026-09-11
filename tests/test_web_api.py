from fastapi.testclient import TestClient
from linagent.web.server import app

def test_web_endpoints():
    client = TestClient(app)

    # Health / static UI
    res = client.get("/")
    assert res.status_code == 200

    # System telemetry
    sys_res = client.get("/api/system")
    assert sys_res.status_code == 200
    assert "os" in sys_res.json() or "raw" in sys_res.json()

    # Tools endpoint
    tools_res = client.get("/api/tools")
    assert tools_res.status_code == 200
    tools_data = tools_res.json()
    assert "tools" in tools_data
    assert len(tools_data["tools"]) > 0

    # Memories endpoint
    mems_res = client.get("/api/memories")
    assert mems_res.status_code == 200
    assert "memories" in mems_res.json()

    # Direct action execution
    action_res = client.post("/api/action", json={
        "tool_name": "get_system_overview",
        "arguments": {}
    })
    assert action_res.status_code == 200
    assert action_res.json()["success"] is True
