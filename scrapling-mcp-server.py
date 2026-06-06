"""
Scrapling MCP Server for OpenCode
Exposes: scrapling_bulk_get, scrapling_bulk_stealthy_fetch, scrapling_bulk_fetch

此脚本是一个标准 MCP Server 实现，供 AI 在安装 Scrapling 时参考。
AI 可以原样使用此脚本，或根据系统环境自行修改后注册到 opencode.json。
不包含任何硬编码路径，完全由 AI 在注册时动态配置。
"""
import asyncio
import json
import sys
import traceback
from typing import Any

import scrapling
from mcp.server import Server
from mcp.types import Tool, TextContent

server = Server("scrapling-mcp")


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="scrapling_bulk_get",
            description="批量抓取网页全文（标准模式，适合大多数网站）",
            inputSchema={
                "type": "object",
                "properties": {
                    "urls": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "要抓取的 URL 列表",
                    },
                    "timeout": {
                        "type": "number",
                        "description": "超时秒数，默认 12",
                        "default": 12,
                    },
                    "extraction_type": {
                        "type": "string",
                        "description": "提取方式：markdown / html / text，默认 markdown",
                        "default": "markdown",
                    },
                },
                "required": ["urls"],
            },
        ),
        Tool(
            name="scrapling_bulk_stealthy_fetch",
            description="批量抓取网页全文（反检测模式，适合有 Cloudflare/WAF 防护的网站）",
            inputSchema={
                "type": "object",
                "properties": {
                    "urls": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "要抓取的 URL 列表",
                    },
                    "timeout": {
                        "type": "number",
                        "description": "超时秒数，默认 15",
                        "default": 15,
                    },
                },
                "required": ["urls"],
            },
        ),
        Tool(
            name="scrapling_bulk_fetch",
            description="批量抓取网页全文（JS 渲染模式，适合需要 JavaScript 执行才能显示内容的页面）",
            inputSchema={
                "type": "object",
                "properties": {
                    "urls": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "要抓取的 URL 列表",
                    },
                    "timeout": {
                        "type": "number",
                        "description": "超时秒数，默认 15",
                        "default": 15,
                    },
                },
                "required": ["urls"],
            },
        ),
    ]


def _fetch_single(url: str, timeout: int, method: str) -> dict:
    """Fetch a single URL and return result dict."""
    result = {"url": url, "success": False, "content": "", "error": ""}
    try:
        if method == "get":
            fetcher = scrapling.Fetcher()
            response = fetcher.get(url)
            result["content"] = response.html_content
            result["success"] = True
        elif method == "stealthy":
            import threading
            sf_result = {}
            def _stealthy_fetch():
                try:
                    fetcher = scrapling.StealthyFetcher()
                    resp = fetcher.fetch(url)
                    sf_result["content"] = resp.html_content
                    sf_result["success"] = True
                except Exception as e:
                    sf_result["error"] = f"{type(e).__name__}: {e}"
                    sf_result["success"] = False
            t = threading.Thread(target=_stealthy_fetch)
            t.start()
            t.join(timeout=timeout)
            if sf_result.get("success"):
                result["content"] = sf_result["content"]
                result["success"] = True
            else:
                result["error"] = sf_result.get("error", "stealthy fetch timeout or failed")
        elif method == "dynamic":
            import threading
            df_result = {}
            def _dynamic_fetch():
                try:
                    fetcher = scrapling.DynamicFetcher()
                    resp = fetcher.fetch(url)
                    df_result["content"] = resp.html_content
                    df_result["success"] = True
                except Exception as e:
                    df_result["error"] = f"{type(e).__name__}: {e}"
                    df_result["success"] = False
            t = threading.Thread(target=_dynamic_fetch)
            t.start()
            t.join(timeout=timeout)
            if df_result.get("success"):
                result["content"] = df_result["content"]
                result["success"] = True
            else:
                result["error"] = df_result.get("error", "dynamic fetch timeout or failed")
    except Exception as e:
        result["error"] = f"{type(e).__name__}: {e}"
    return result


def _bulk_fetch(urls: list[str], timeout: int, method: str) -> list[dict]:
    results = []
    for url in urls:
        r = _fetch_single(url, timeout, method)
        results.append(r)
    return results


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    urls = arguments.get("urls", [])
    timeout = arguments.get("timeout", 12)
    extraction_type = arguments.get("extraction_type", "markdown")

    if not urls:
        return [TextContent(type="text", text=json.dumps({"error": "urls is required"}))]

    try:
        if name == "scrapling_bulk_get":
            raw_results = _bulk_fetch(urls, timeout, "get")
        elif name == "scrapling_bulk_stealthy_fetch":
            raw_results = _bulk_fetch(urls, timeout, "stealthy")
        elif name == "scrapling_bulk_fetch":
            raw_results = _bulk_fetch(urls, timeout, "dynamic")
        else:
            return [TextContent(type="text", text=json.dumps({"error": f"unknown tool: {name}"}))]

        output = []
        for r in raw_results:
            entry = {
                "url": r["url"],
                "success": r["success"],
            }
            if r["success"]:
                entry["content_length"] = len(r["content"])
                entry["content_preview"] = r["content"][:500]
                entry["content"] = r["content"]
            else:
                entry["error"] = r["error"]
            output.append(entry)

        return [TextContent(
            type="text",
            text=json.dumps({
                "tool": name,
                "total_urls": len(urls),
                "success_count": sum(1 for r in raw_results if r["success"]),
                "fail_count": sum(1 for r in raw_results if not r["success"]),
                "results": output,
            }, ensure_ascii=False, indent=2)
        )]
    except Exception as e:
        tb = traceback.format_exc()
        return [TextContent(type="text", text=json.dumps({
            "error": str(e),
            "traceback": tb,
        }))]


async def main():
    from mcp.server.stdio import stdio_server
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())
