import httpx
from .base import Tool


class WebSearchTool(Tool):
    name = "web_search"
    description = "使用 Brave Search 搜索网络，返回摘要和链接列表。"
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "搜索关键词"},
            "count": {"type": "integer", "description": "结果数量，默认 5", "default": 5},
        },
        "required": ["query"],
    }

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def execute(self, query: str, count: int = 5) -> str:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://api.search.brave.com/res/v1/web/search",
                params={"q": query, "count": count},
                headers={"X-Subscription-Token": self.api_key},
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
        results = data.get("web", {}).get("results", [])
        lines = []
        for r in results:
            lines.append(f"## {r['title']}\n{r['url']}\n{r.get('description', '')}")
        return "\n\n".join(lines) or "未找到结果"


class WebFetchTool(Tool):
    name = "web_fetch"
    description = "抓取网页内容并转为 Markdown 格式文本。"
    parameters = {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "要抓取的网页 URL"},
        },
        "required": ["url"],
    }

    async def execute(self, url: str) -> str:
        async with httpx.AsyncClient(follow_redirects=True, timeout=15) as client:
            resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
            resp.raise_for_status()
            html = resp.text
        try:
            import html2text
            h = html2text.HTML2Text()
            h.ignore_links = False
            return h.handle(html)[:8000]
        except ImportError:
            import re
            return re.sub(r"<[^>]+>", "", html)[:8000]
