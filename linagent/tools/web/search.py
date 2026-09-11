"""Lightweight web search tool using DuckDuckGo (no API keys required)."""

import json
import re
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

from linagent.core.tools import ToolResult, default_registry

USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

def _ddg_lite_search(query: str, max_results: int = 5) -> List[Dict[str, str]]:
    """Query DuckDuckGo Lite and parse clean search results without JavaScript."""
    url = "https://lite.duckduckgo.com/lite/"
    data = urllib.parse.urlencode({"q": query}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "User-Agent": USER_AGENT,
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )

    results = []
    try:
        with urllib.request.urlopen(req, timeout=12) as response:
            html = response.read().decode("utf-8", errors="ignore")

        # Extract results matching DuckDuckGo Lite table format
        link_pattern = re.compile(
            r"<a[^>]+href=['\"]([^'\"]+)['\"][^>]*class=['\"]result-link['\"][^>]*>(.*?)</a>",
            re.IGNORECASE,
        )
        snippet_pattern = re.compile(
            r"<td[^>]*class=['\"]result-snippet['\"][^>]*>\s*(.*?)\s*</td>",
            re.DOTALL | re.IGNORECASE,
        )

        titles = link_pattern.findall(html)
        snippets = snippet_pattern.findall(html)

        for i in range(min(len(titles), max_results)):
            href, raw_title = titles[i]
            # Unescape html entities
            import html as html_lib
            clean_title = html_lib.unescape(re.sub(r"<[^>]+>", "", raw_title).strip())
            
            clean_snippet = ""
            if i < len(snippets):
                clean_snippet = html_lib.unescape(re.sub(r"<[^>]+>", "", snippets[i]).strip())

            results.append({
                "title": clean_title,
                "url": href,
                "snippet": clean_snippet,
            })
    except Exception as e:
        # Fallback to duckduckgo instant answer API
        api_url = f"https://api.duckduckgo.com/?q={urllib.parse.quote(query)}&format=json&no_html=1"
        try:
            api_req = urllib.request.Request(api_url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(api_req, timeout=8) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if data.get("AbstractText"):
                    results.append({
                        "title": data.get("Heading", query),
                        "url": data.get("AbstractURL", ""),
                        "snippet": data.get("AbstractText", ""),
                    })
                for topic in data.get("RelatedTopics", [])[:max_results]:
                    if isinstance(topic, dict) and "Text" in topic:
                        results.append({
                            "title": topic.get("FirstURL", "").split("/")[-1].replace("_", " "),
                            "url": topic.get("FirstURL", ""),
                            "snippet": topic.get("Text", ""),
                        })
        except Exception:
            pass

    return results

@default_registry.register(
    name="search_web",
    description="Search the internet for real-time information, documentation, news, or solutions using DuckDuckGo. No API key needed.",
)
def search_web(query: str, max_results: int = 5) -> ToolResult:
    """Perform a web search."""
    results = _ddg_lite_search(query, max_results=max_results)
    if not results:
        return ToolResult(
            success=False,
            output=f"No web search results found for: '{query}'",
            error="No results returned",
        )

    formatted = []
    for i, r in enumerate(results, 1):
        formatted.append(
            f"[{i}] {r['title']}\n    URL: {r['url']}\n    Summary: {r['snippet']}"
        )

    return ToolResult(
        success=True,
        output="\n\n".join(formatted),
        data={"results": results},
    )
