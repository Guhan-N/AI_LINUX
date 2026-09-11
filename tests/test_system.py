from linagent.tools.automation.system import get_system_overview, get_top_processes

def test_system_overview():
    res = get_system_overview()
    assert res.success is True
    assert res.data is not None
    assert "os" in res.data
    assert "arch" in res.data
    assert "hostname" in res.data

def test_top_processes():
    res = get_top_processes(limit=5)
    assert res.success is True
    assert len(res.output) > 0
