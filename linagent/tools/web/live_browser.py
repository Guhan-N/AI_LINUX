"""Live Autonomous Browser Automation Engine for LinAgent (Playwright-based).

Provides live headful/headless web automation: navigation, visual/DOM inspection,
clicking, form filling, keystroke input, screenshots, and multi-step web workflows.
"""

import os
import shutil
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from linagent.core.tools import ToolResult, default_registry

class LiveBrowserManager:
    """Persistent singleton manager for live browser automation sessions."""

    _instance: Optional["LiveBrowserManager"] = None

    def __init__(self) -> None:
        self._playwright: Any = None
        self._browser: Any = None
        self._context: Any = None
        self._page: Any = None
        self._is_headless: bool = False

    @classmethod
    def get_instance(cls) -> "LiveBrowserManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _ensure_display_env(self) -> None:
        """Ensure DISPLAY or WAYLAND_DISPLAY is set for headful rendering on Linux."""
        if os.name != "nt" and "DISPLAY" not in os.environ and "WAYLAND_DISPLAY" not in os.environ:
            os.environ["DISPLAY"] = ":0"

    def is_active(self) -> bool:
        """Check if an active page is currently open and responsive."""
        return self._page is not None and not self._page.is_closed()

    def get_active_page(self) -> Any:
        return self._page

    def open_url(self, url: str, headless: bool = False) -> ToolResult:
        """Launch browser session (headful by default on desktop) and navigate to URL."""
        if not url.startswith("http://") and not url.startswith("https://"):
            url = "https://" + url

        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return ToolResult(
                success=False,
                error=(
                    "Playwright library is not installed.\n"
                    "Install it in 1 command: `linagent setup-browser`\n"
                    "Or: `pip install playwright && playwright install chromium`"
                ),
            )

        self._ensure_display_env()

        try:
            # Initialize playwright runtime if not running
            if self._playwright is None:
                self._playwright = sync_playwright().start()

            # If browser closed or mode switched, recreate
            if self._browser is None or self._is_headless != headless:
                if self._browser:
                    try:
                        self._browser.close()
                    except Exception:
                        pass

                self._is_headless = headless
                launch_args = {
                    "headless": headless,
                    "args": ["--start-maximized", "--no-sandbox", "--disable-dev-shm-usage"],
                }

                # Attempt launch; fallback to system Chromium/Chrome if playwright driver missing
                try:
                    self._browser = self._playwright.chromium.launch(**launch_args)
                except Exception as launch_err:
                    system_browser = (
                        shutil.which("chromium")
                        or shutil.which("chromium-browser")
                        or shutil.which("google-chrome")
                        or shutil.which("firefox")
                    )
                    if system_browser:
                        launch_args["executable_path"] = system_browser
                        self._browser = self._playwright.chromium.launch(**launch_args)
                    else:
                        return ToolResult(
                            success=False,
                            error=(
                                f"Failed to launch browser: {launch_err}\n"
                                "Run `linagent setup-browser` to download the browser drivers."
                            ),
                        )

                self._context = self._browser.new_context(
                    viewport=None if not headless else {"width": 1280, "height": 800},
                    user_agent=(
                        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                    ),
                )
                self._page = self._context.new_page()

            if self._page is None or self._page.is_closed():
                self._page = self._context.new_page()

            # Navigate to the requested URL
            self._page.goto(url, wait_until="domcontentloaded", timeout=30000)
            try:
                self._page.wait_for_load_state("networkidle", timeout=3000)
            except Exception:
                pass  # Dynamic sites stream continuously

            title = self._page.title()
            current_url = self._page.url
            inspection = self.inspect_elements()

            mode_str = "headless" if headless else "visible desktop window"
            output = (
                f"✓ Browser navigated to: {current_url} ({mode_str})\n"
                f"Page Title: {title}\n\n"
                f"{inspection}"
            )
            return ToolResult(
                success=True,
                output=output,
                data={"url": current_url, "title": title},
            )
        except Exception as e:
            return ToolResult(success=False, error=f"Browser navigation failed: {e}")

    def inspect_elements(self, max_items: int = 25) -> str:
        """Inspect and return a compact tree of interactive elements (inputs, buttons, links)."""
        if not self.is_active():
            return "No active browser page open."

        try:
            # Run fast JavaScript extraction of interactive DOM elements
            js_script = """
            () => {
                const elements = [];
                // 1. Search & text inputs
                document.querySelectorAll('input:not([type="hidden"]), textarea, select').forEach(el => {
                    if (el.offsetParent !== null) { // visible
                        elements.push({
                            type: 'input',
                            tag: el.tagName.toLowerCase(),
                            name: el.name || '',
                            id: el.id || '',
                            placeholder: el.placeholder || '',
                            ariaLabel: el.getAttribute('aria-label') || '',
                            value: el.value || '',
                            selector: el.id ? '#' + el.id : (el.name ? `${el.tagName.toLowerCase()}[name="${el.name}"]` : '')
                        });
                    }
                });

                // 2. Clickable buttons
                document.querySelectorAll('button, [role="button"], input[type="submit"], input[type="button"]').forEach(el => {
                    if (el.offsetParent !== null) {
                        const text = (el.innerText || el.value || el.getAttribute('aria-label') || '').trim();
                        if (text && text.length < 50) {
                            elements.push({
                                type: 'button',
                                text: text,
                                id: el.id || '',
                                ariaLabel: el.getAttribute('aria-label') || '',
                                selector: el.id ? '#' + el.id : ''
                            });
                        }
                    }
                });

                // 3. Significant links or titles
                document.querySelectorAll('a[href]').forEach(el => {
                    if (el.offsetParent !== null) {
                        const text = (el.innerText || el.getAttribute('aria-label') || '').trim();
                        if (text && text.length > 2 && text.length < 80) {
                            elements.push({
                                type: 'link',
                                text: text,
                                href: el.href,
                                id: el.id || ''
                            });
                        }
                    }
                });

                return elements.slice(0, 50);
            }
            """
            items: List[Dict[str, Any]] = self._page.evaluate(js_script)
            if not items:
                return "No interactive elements detected on page."

            lines = ["Interactive Elements on Page:"]
            inputs = [i for i in items if i.get("type") == "input"][:8]
            buttons = [i for i in items if i.get("type") == "button"][:10]
            links = [i for i in items if i.get("type") == "link"][:10]

            if inputs:
                lines.append("  [Input Fields]:")
                for inp in inputs:
                    desc = f"selector: '{inp.get('selector') or inp.get('name') or inp.get('id')}'"
                    if inp.get("placeholder"):
                        desc += f", placeholder: '{inp['placeholder']}'"
                    if inp.get("ariaLabel"):
                        desc += f", label: '{inp['ariaLabel']}'"
                    lines.append(f"    - {desc}")

            if buttons:
                lines.append("  [Buttons]:")
                for btn in buttons:
                    desc = f"'{btn.get('text')}'"
                    if btn.get("selector"):
                        desc += f" (selector: '{btn['selector']}')"
                    lines.append(f"    - {desc}")

            if links:
                lines.append("  [Links & Titles]:")
                for lnk in links:
                    lines.append(f"    - '{lnk.get('text')}'")

            return "\n".join(lines)
        except Exception as e:
            return f"Element inspection warning: {e}"

    def click(self, target: str) -> ToolResult:
        """Click an element by CSS selector, button text, or aria-label."""
        if not self.is_active():
            return ToolResult(success=False, error="No active browser session. Call 'browser_open' first.")

        try:
            # 1. Try direct selector
            try:
                self._page.click(target, timeout=2500)
                time.sleep(0.5)
                return ToolResult(
                    success=True,
                    output=f"✓ Clicked element with selector: '{target}'. Current page title: '{self._page.title()}'",
                )
            except Exception:
                pass

            # 2. Try text matching button / role
            try:
                self._page.get_by_role("button", name=target).click(timeout=2500)
                time.sleep(0.5)
                return ToolResult(success=True, output=f"✓ Clicked button with label: '{target}'")
            except Exception:
                pass

            # 3. Try generic text content match
            try:
                self._page.get_by_text(target, exact=False).first.click(timeout=2500)
                time.sleep(0.5)
                return ToolResult(success=True, output=f"✓ Clicked element containing text: '{target}'")
            except Exception:
                pass

            # 4. Try CSS text= selector
            self._page.click(f"text={target}", timeout=3000)
            time.sleep(0.5)
            return ToolResult(success=True, output=f"✓ Clicked text: '{target}'")
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Could not click '{target}'. Error: {e}\nTip: Check available elements with 'browser_extract_content' or inspect output.",
            )

    def type_text(self, target: str, text: str, press_enter: bool = True) -> ToolResult:
        """Type text into an input or search field."""
        if not self.is_active():
            return ToolResult(success=False, error="No active browser session. Call 'browser_open' first.")

        try:
            # 1. Try direct selector fill
            filled = False
            try:
                self._page.fill(target, text, timeout=2500)
                filled = True
            except Exception:
                pass

            # 2. Try placeholder match
            if not filled:
                try:
                    self._page.get_by_placeholder(target).fill(text, timeout=2500)
                    filled = True
                except Exception:
                    pass

            # 3. Try name attribute
            if not filled:
                try:
                    self._page.locator(f"input[name='{target}'], textarea[name='{target}']").fill(text, timeout=2500)
                    filled = True
                except Exception:
                    pass

            # 4. Fallback: focus and keyboard type
            if not filled:
                self._page.click(target, timeout=2500)
                self._page.keyboard.type(text)
                filled = True

            if press_enter:
                self._page.keyboard.press("Enter")
                time.sleep(1.0)
                try:
                    self._page.wait_for_load_state("domcontentloaded", timeout=5000)
                except Exception:
                    pass

            status_enter = " and submitted [Enter]" if press_enter else ""
            return ToolResult(
                success=True,
                output=f"✓ Typed '{text}' into '{target}'{status_enter}. Current URL: {self._page.url}",
                data={"url": self._page.url, "title": self._page.title()},
            )
        except Exception as e:
            return ToolResult(success=False, error=f"Failed typing into '{target}': {e}")

    def press_key(self, key: str) -> ToolResult:
        """Press keyboard key (e.g. 'Enter', 'Escape', 'ArrowDown', 'Space', 'Tab')."""
        if not self.is_active():
            return ToolResult(success=False, error="No active browser session. Call 'browser_open' first.")

        try:
            self._page.keyboard.press(key)
            return ToolResult(success=True, output=f"✓ Pressed key: '{key}'")
        except Exception as e:
            return ToolResult(success=False, error=f"Failed pressing key '{key}': {e}")

    def scroll(self, direction: str = "down", amount: int = 500) -> ToolResult:
        """Scroll page up or down."""
        if not self.is_active():
            return ToolResult(success=False, error="No active browser session. Call 'browser_open' first.")

        try:
            delta = amount if direction.lower() == "down" else -amount
            self._page.mouse.wheel(0, delta)
            time.sleep(0.5)
            return ToolResult(success=True, output=f"✓ Scrolled page {direction} by {amount}px.")
        except Exception as e:
            return ToolResult(success=False, error=f"Failed scrolling page: {e}")

    def extract_content(self, selector: Optional[str] = None, max_chars: int = 4000) -> ToolResult:
        """Extract clean rendered text from the active page."""
        if not self.is_active():
            return ToolResult(success=False, error="No active browser session. Call 'browser_open' first.")

        try:
            if selector:
                text = self._page.locator(selector).inner_text(timeout=5000)
            else:
                text = self._page.inner_text("body", timeout=5000)

            # Compact whitespace
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            clean_text = "\n".join(lines)
            truncated = clean_text[:max_chars]
            if len(clean_text) > max_chars:
                truncated += f"\n\n... [Truncated {len(clean_text) - max_chars} characters remaining] ..."

            return ToolResult(
                success=True,
                output=f"Page Content ({self._page.title()} - {self._page.url}):\n\n{truncated}",
                data={"url": self._page.url, "title": self._page.title()},
            )
        except Exception as e:
            return ToolResult(success=False, error=f"Failed to extract page content: {e}")

    def take_screenshot(self, output_path: Optional[str] = None) -> ToolResult:
        """Capture screenshot of the live browser view."""
        if not self.is_active():
            return ToolResult(success=False, error="No active browser session. Call 'browser_open' first.")

        dest = Path(output_path or os.path.expanduser("~/browser_screenshot.png"))
        dest.parent.mkdir(parents=True, exist_ok=True)

        try:
            self._page.screenshot(path=str(dest.resolve()), full_page=False)
            return ToolResult(
                success=True,
                output=f"✓ Live browser screenshot saved to: {dest.resolve()}",
                data={"path": str(dest.resolve())},
            )
        except Exception as e:
            return ToolResult(success=False, error=f"Failed taking browser screenshot: {e}")

    def close(self) -> ToolResult:
        """Close browser session and cleanup resources."""
        try:
            if self._page:
                try:
                    self._page.close()
                except Exception:
                    pass
                self._page = None

            if self._context:
                try:
                    self._context.close()
                except Exception:
                    pass
                self._context = None

            if self._browser:
                try:
                    self._browser.close()
                except Exception:
                    pass
                self._browser = None

            if self._playwright:
                try:
                    self._playwright.stop()
                except Exception:
                    pass
                self._playwright = None

            return ToolResult(success=True, output="✓ Live browser session successfully closed.")
        except Exception as e:
            return ToolResult(success=False, error=f"Error closing browser: {e}")


# ==============================================================================
# LinAgent Tool Registry Registration
# ==============================================================================

@default_registry.register(
    name="browser_open",
    description="Launch a live browser window on desktop and navigate to a URL (e.g. YouTube, Google, GitHub, documentation). Displays real graphical browser window by default.",
)
def tool_browser_open(url: str, headless: bool = False) -> ToolResult:
    """Open a website in the live interactive browser."""
    mgr = LiveBrowserManager.get_instance()
    return mgr.open_url(url, headless=headless)

@default_registry.register(
    name="browser_click",
    description="Click an element on the live web page by CSS selector (e.g. '#search-button'), button text (e.g. 'Search', 'Play'), or link text.",
)
def tool_browser_click(selector_or_text: str) -> ToolResult:
    """Click an element on the active browser page."""
    mgr = LiveBrowserManager.get_instance()
    return mgr.click(selector_or_text)

@default_registry.register(
    name="browser_type",
    description="Type text into a search bar, input box, or form field on the live browser page (e.g. selector 'input[name=\"search_query\"]', text 'lo-fi music', press_enter=True).",
)
def tool_browser_type(selector_or_text: str, text: str, press_enter: bool = True) -> ToolResult:
    """Type text into an input field on the active browser page."""
    mgr = LiveBrowserManager.get_instance()
    return mgr.type_text(selector_or_text, text, press_enter=press_enter)

@default_registry.register(
    name="browser_press_key",
    description="Press a keyboard key in the active live browser (e.g. 'Enter', 'Escape', 'ArrowDown', 'Space', 'Tab').",
)
def tool_browser_press_key(key: str) -> ToolResult:
    """Press keyboard key in live browser."""
    mgr = LiveBrowserManager.get_instance()
    return mgr.press_key(key)

@default_registry.register(
    name="browser_scroll",
    description="Scroll the live web page up or down (direction: 'down' or 'up', amount: pixels e.g. 500).",
)
def tool_browser_scroll(direction: str = "down", amount: int = 500) -> ToolResult:
    """Scroll the active browser page."""
    mgr = LiveBrowserManager.get_instance()
    return mgr.scroll(direction=direction, amount=amount)

@default_registry.register(
    name="browser_extract_content",
    description="Extract clean readable text/content from the active live browser page or specific CSS selector.",
)
def tool_browser_extract_content(selector: Optional[str] = None, max_chars: int = 4000) -> ToolResult:
    """Extract content from live browser page."""
    mgr = LiveBrowserManager.get_instance()
    return mgr.extract_content(selector=selector, max_chars=max_chars)

@default_registry.register(
    name="browser_screenshot",
    description="Capture a screenshot of the live browser window and save to disk (default: ~/browser_screenshot.png).",
)
def tool_browser_screenshot(output_path: Optional[str] = None) -> ToolResult:
    """Take a screenshot of the active browser window."""
    mgr = LiveBrowserManager.get_instance()
    return mgr.take_screenshot(output_path=output_path)

@default_registry.register(
    name="browser_close",
    description="Close the active live browser session and release desktop resources.",
)
def tool_browser_close() -> ToolResult:
    """Close active browser session."""
    mgr = LiveBrowserManager.get_instance()
    return mgr.close()
