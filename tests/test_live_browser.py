"""Unit tests for live autonomous browser engine and tools."""

import pytest
from unittest.mock import MagicMock
from linagent.core.tools import default_registry
from linagent.tools.web.live_browser import (
    LiveBrowserManager,
    tool_browser_open,
    tool_browser_click,
    tool_browser_type,
    tool_browser_press_key,
    tool_browser_scroll,
    tool_browser_extract_content,
    tool_browser_screenshot,
    tool_browser_close,
)

def test_live_browser_tools_registered():
    """Ensure all live browser tools are loaded into default registry."""
    tool_names = [t.name for t in default_registry.list_tools()]
    expected_tools = [
        "browser_open",
        "browser_click",
        "browser_type",
        "browser_press_key",
        "browser_scroll",
        "browser_extract_content",
        "browser_screenshot",
        "browser_close",
    ]
    for exp in expected_tools:
        assert exp in tool_names, f"Tool '{exp}' not found in registry"

def test_browser_not_installed_error(monkeypatch):
    """Ensure clean informative error when playwright is not available."""
    import builtins
    real_import = builtins.__import__

    def mock_import(name, *args, **kwargs):
        if "playwright" in name:
            raise ImportError("No module named 'playwright'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", mock_import)

    mgr = LiveBrowserManager()
    res = mgr.open_url("https://example.com")
    assert res.success is False
    assert "Playwright library is not installed" in res.error
    assert "linagent setup-browser" in res.error

def test_browser_actions_with_mocked_page(tmp_path):
    """Test browser live interaction steps with simulated Playwright page."""
    mgr = LiveBrowserManager()

    mock_page = MagicMock()
    mock_page.is_closed.return_value = False
    mock_page.title.return_value = "YouTube"
    mock_page.url = "https://www.youtube.com/"
    mock_page.inner_text.return_value = "Trending Videos\nMusic\nGaming"
    mock_page.evaluate.return_value = [
        {"type": "input", "selector": "input[name='search_query']", "placeholder": "Search"},
        {"type": "button", "text": "Search", "selector": "#search-button"},
    ]

    mgr._page = mock_page

    # 1. Type
    type_res = mgr.type_text("input[name='search_query']", "lo-fi beats", press_enter=True)
    assert type_res.success is True
    assert "Typed 'lo-fi beats'" in type_res.output
    mock_page.keyboard.press.assert_called_with("Enter")

    # 2. Click
    click_res = mgr.click("#search-button")
    assert click_res.success is True
    assert "Clicked element with selector" in click_res.output

    # 3. Press Key
    key_res = mgr.press_key("ArrowDown")
    assert key_res.success is True
    assert "Pressed key: 'ArrowDown'" in key_res.output

    # 4. Scroll
    scroll_res = mgr.scroll(direction="down", amount=300)
    assert scroll_res.success is True
    mock_page.mouse.wheel.assert_called_with(0, 300)

    # 5. Extract content
    extract_res = mgr.extract_content()
    assert extract_res.success is True
    assert "Trending Videos" in extract_res.output

    # 6. Screenshot
    shot_path = tmp_path / "shot.png"
    shot_res = mgr.take_screenshot(str(shot_path))
    assert shot_res.success is True
    mock_page.screenshot.assert_called_once()

    # 7. Close
    close_res = mgr.close()
    assert close_res.success is True
    assert mgr._page is None
