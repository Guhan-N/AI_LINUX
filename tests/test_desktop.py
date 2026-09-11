from linagent.core.tools import default_registry
from linagent.tools.automation.desktop import open_in_browser, launch_gui_app

def test_desktop_tools_registered():
    t1 = default_registry.get_tool("open_in_browser")
    t2 = default_registry.get_tool("launch_gui_app")
    t3 = default_registry.get_tool("type_text_into_active_window")
    t4 = default_registry.get_tool("take_screenshot")

    assert t1 is not None
    assert t2 is not None
    assert t3 is not None
    assert t4 is not None

def test_launch_gui_app_validation():
    res = launch_gui_app("non_existent_app_12345")
    assert res.success is False
    assert "not installed" in res.error
