"""Lightweight web scraper and browser tool for reading documentation and web pages."""

import os
import re
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Optional

from linagent.core.tools import ToolResult, default_registry

USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

def _clean_html_to_markdown(html: str) -> str:
    """Convert HTML string to clean readable text/markdown without massive dependencies."""
    # Strip script and style blocks
    text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<nav[^>]*>.*?</nav>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<footer[^>]*>.*?</footer>", "", text, flags=re.DOTALL | re.IGNORECASE)

    # Convert headings
    text = re.sub(r"<h1[^>]*>(.*?)</h1>", r"\n# \1\n", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<h2[^>]*>(.*?)</h2>", r"\n## \1\n", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<h3[^>]*>(.*?)</h3>", r"\n### \1\n", text, flags=re.DOTALL | re.IGNORECASE)

    # Convert links <a href="...">text</a> to [text](url)
    text = re.sub(r'<a\s+[^>]*href="([^"]+)"[^>]*>(.*?)</a>', r"[\2](\1)", text, flags=re.DOTALL | re.IGNORECASE)

    # Convert list items
    text = re.sub(r"<li[^>]*>(.*?)</li>", r"\n- \1", text, flags=re.DOTALL | re.IGNORECASE)

    # Convert line breaks and paragraphs
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<p[^>]*>(.*?)</p>", r"\n\n\1\n", text, flags=re.DOTALL | re.IGNORECASE)

    # Strip remaining HTML tags
    text = re.sub(r"<[^>]+>", "", text)

    # Decode common HTML entities
    text = text.replace("&nbsp;", " ")
    text = text.replace("&amp;", "&")
    text = text.replace("&lt;", "<")
    text = text.replace("&gt;", ">")
    text = text.replace("&quot;", '"')
    text = text.replace("&#39;", "'")

    # Collapse multiple blank lines
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
    return text.strip()

@default_registry.register(
    name="fetch_web_page",
    description="Fetch and extract the readable text/markdown content from a URL (e.g. documentation, tutorials, articles).",
)
def fetch_web_page(url: str, max_chars: int = 5000) -> ToolResult:
    """Fetch a web page and return clean readable content."""
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "https://" + url

    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=15) as response:
            content_type = response.headers.get("Content-Type", "")
            raw_data = response.read()
            charset = "utf-8"
            if "charset=" in content_type:
                charset = content_type.split("charset=")[-1].split(";")[0].strip()

            html = raw_data.decode(charset, errors="ignore")

        clean_text = _clean_html_to_markdown(html)
        truncated = clean_text[:max_chars]
        if len(clean_text) > max_chars:
            truncated += f"\n\n... [Content truncated, {len(clean_text) - max_chars} characters remaining] ..."

        return ToolResult(
            success=True,
            output=truncated,
            data={"url": url, "full_length": len(clean_text)},
        )
    except Exception as e:
        return ToolResult(success=False, error=f"Failed to fetch {url}: {str(e)}")

@default_registry.register(
    name="download_file_from_web",
    description="Download a file (binary, archive, script, document) from a URL directly to the Linux filesystem.",
)
def download_file_from_web(url: str, destination_path: str) -> ToolResult:
    """Download a file from web to local path."""
    dest = Path(os.path.expanduser(destination_path))
    dest.parent.mkdir(parents=True, exist_ok=True)

    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=30) as response, open(dest, "wb") as out_file:
            shutil.copyfileobj(response, out_file)

        size_kb = round(dest.stat().st_size / 1024, 2)
        return ToolResult(
            success=True,
            output=f"Successfully downloaded file to {dest.resolve()} ({size_kb} KB)",
            data={"path": str(dest.resolve()), "size_bytes": dest.stat().st_size},
        )
    except Exception as e:
        return ToolResult(success=False, error=f"Download failed: {str(e)}")
