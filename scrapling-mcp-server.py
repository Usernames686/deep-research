"""
Scrapling MCP Server for Codex
Exposes: scrapling_bulk_get, scrapling_bulk_stealthy_fetch, scrapling_bulk_fetch

This stdio MCP server is scoped by the Codex project config that starts it.
It validates URL schemes and private-address access, clamps batch size/timeouts,
and truncates oversized responses so research tasks cannot accidentally turn one
tool call into an unbounded crawler.
"""
import asyncio
import ipaddress
import json
import os
import socket
import sys
import time
import traceback
from typing import Any
from urllib.parse import urlparse

import scrapling
from markdownify import markdownify as to_markdown
from mcp.server import Server
from mcp.types import Tool, TextContent

server = Server("scrapling-mcp")


def _parse_networks(raw: str) -> tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...]:
    networks = []
    for value in raw.split(","):
        value = value.strip()
        if not value:
            continue
        try:
            networks.append(ipaddress.ip_network(value, strict=False))
        except ValueError:
            print(f"Ignoring invalid allowed DNS network: {value}", file=sys.stderr)
    return tuple(networks)


MAX_URLS = int(os.environ.get("SCRAPLING_MCP_MAX_URLS", "12"))
MAX_BROWSER_URLS = int(os.environ.get("SCRAPLING_MCP_MAX_BROWSER_URLS", "2"))
MAX_TIMEOUT = int(os.environ.get("SCRAPLING_MCP_MAX_TIMEOUT", "20"))
MAX_CONTENT_CHARS = int(os.environ.get("SCRAPLING_MCP_MAX_CONTENT_CHARS", "30000"))
MAX_TOTAL_CONTENT_CHARS = int(
    os.environ.get("SCRAPLING_MCP_MAX_TOTAL_CONTENT_CHARS", "180000")
)
MAX_CONCURRENCY = int(os.environ.get("SCRAPLING_MCP_MAX_CONCURRENCY", "6"))
BROWSER_CONCURRENCY = int(
    os.environ.get("SCRAPLING_MCP_BROWSER_CONCURRENCY", "2")
)
BATCH_TIMEOUT = int(os.environ.get("SCRAPLING_MCP_BATCH_TIMEOUT", "55"))
ALLOW_PRIVATE = os.environ.get("SCRAPLING_MCP_ALLOW_PRIVATE", "0") == "1"
STRICT_DNS = os.environ.get("SCRAPLING_MCP_STRICT_DNS", "1") == "1"
ALLOWED_HOSTS = [
    host.strip().lower()
    for host in os.environ.get("SCRAPLING_MCP_ALLOWED_HOSTS", "").split(",")
    if host.strip()
]
ALLOWED_DNS_NETWORKS = _parse_networks(
    os.environ.get("SCRAPLING_MCP_ALLOWED_RESOLVED_CIDRS", "")
)

_DNS_CACHE_TTL = 300
_DNS_CACHE: dict[str, tuple[float, tuple[bool, str]]] = {}


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
                    "extraction_type": {
                        "type": "string",
                        "description": "提取方式：markdown / html / text，默认 markdown",
                        "default": "markdown",
                    },
                },
                "required": ["urls"],
            },
        ),
    ]


def _clamp_timeout(value: Any) -> int:
    try:
        timeout = int(value)
    except (TypeError, ValueError):
        timeout = 12
    return max(1, min(timeout, MAX_TIMEOUT))


def _host_allowed(hostname: str) -> bool:
    if not ALLOWED_HOSTS:
        return True
    host = hostname.lower()
    return any(host == allowed or host.endswith(f".{allowed}") for allowed in ALLOWED_HOSTS)


def _is_public_ip(address: str) -> bool:
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return True
    return not (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def _is_allowed_dns_proxy_ip(address: str) -> bool:
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return False
    return any(ip in network for network in ALLOWED_DNS_NETWORKS)


def _validate_url(url: str) -> tuple[bool, str]:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return False, "only http and https URLs are allowed"
    if not parsed.hostname:
        return False, "URL host is required"
    hostname = parsed.hostname.lower()
    if hostname in {"localhost", "localhost.localdomain"} or hostname.endswith(".localhost") or hostname.endswith(".local"):
        return False, "localhost and local network names are blocked"
    if not _host_allowed(parsed.hostname):
        return False, "host is outside SCRAPLING_MCP_ALLOWED_HOSTS"
    if ALLOW_PRIVATE:
        return True, ""

    try:
        ipaddress.ip_address(hostname)
    except ValueError:
        return True, ""
    if not _is_public_ip(hostname):
        return False, (
            "private, loopback, link-local, multicast, reserved, and unspecified "
            "IP addresses are blocked"
        )
    return True, ""


async def _resolve_public_host(hostname: str) -> tuple[bool, str]:
    now = time.monotonic()
    cached = _DNS_CACHE.get(hostname)
    if cached and now - cached[0] < _DNS_CACHE_TTL:
        return cached[1]

    try:
        infos = await asyncio.to_thread(socket.getaddrinfo, hostname, None)
    except socket.gaierror as exc:
        result = (False, f"host resolution failed: {exc}")
        _DNS_CACHE[hostname] = (now, result)
        return result

    addresses = {info[4][0] for info in infos}
    if not addresses or any(
        not _is_public_ip(address) and not _is_allowed_dns_proxy_ip(address)
        for address in addresses
    ):
        result = (
            False,
            "private, loopback, link-local, multicast, reserved, and unspecified "
            "addresses are blocked by strict DNS mode",
        )
    else:
        result = (True, "")
    _DNS_CACHE[hostname] = (now, result)
    return result


async def _validate_url_async(url: str) -> tuple[bool, str]:
    valid, error = _validate_url(url)
    if not valid or ALLOW_PRIVATE or not STRICT_DNS:
        return valid, error
    hostname = urlparse(url).hostname
    return await _resolve_public_host(hostname) if hostname else (False, "URL host is required")


async def _secure_browser_route(route, request) -> None:
    parsed = urlparse(request.url)
    if parsed.scheme in {"data", "blob", "about"} and not request.is_navigation_request():
        await route.continue_()
        return
    valid, _ = await _validate_url_async(request.url)
    if valid:
        await route.continue_()
    else:
        await route.abort("blockedbyclient")


async def _secure_page_setup(page) -> None:
    await page.route("**/*", _secure_browser_route)


def _extract_content(html: str, extraction_type: str) -> tuple[str, int, bool]:
    if extraction_type == "html":
        content = html
    elif extraction_type == "text":
        content = to_markdown(html, strip=["a", "img"]).strip()
    else:
        content = to_markdown(html).strip()
    original_length = len(content)
    truncated = original_length > MAX_CONTENT_CHARS
    if truncated:
        content = content[:MAX_CONTENT_CHARS]
    return content, original_length, truncated


async def _fetch_single(url: str, timeout: int, method: str, extraction_type: str) -> dict:
    """Fetch a single URL and return result dict."""
    result = {
        "url": url,
        "success": False,
        "content": "",
        "error": "",
        "content_length": 0,
        "original_content_length": 0,
        "truncated": False,
    }
    valid, error = await _validate_url_async(url)
    if not valid:
        result["error"] = error
        return result

    try:
        if method == "get":
            response = await scrapling.AsyncFetcher.get(
                url, timeout=timeout, follow_redirects="safe"
            )
            content, original_length, truncated = _extract_content(
                response.html_content, extraction_type
            )
            result.update(
                content=content,
                content_length=len(content),
                original_content_length=original_length,
                truncated=truncated,
            )
            result["success"] = True
        elif method == "stealthy":
            try:
                resp = await scrapling.StealthyFetcher.async_fetch(
                    url, headless=True, timeout=timeout * 1000,
                    page_setup=_secure_page_setup,
                )
                content, original_length, truncated = _extract_content(
                    resp.html_content, extraction_type
                )
                result.update(
                    content=content,
                    content_length=len(content),
                    original_content_length=original_length,
                    truncated=truncated,
                )
                result["success"] = True
            except Exception as e:
                result["error"] = f"{type(e).__name__}: {e}"
        elif method == "dynamic":
            try:
                resp = await scrapling.DynamicFetcher.async_fetch(
                    url, headless=True, timeout=timeout * 1000,
                    page_setup=_secure_page_setup,
                )
                content, original_length, truncated = _extract_content(
                    resp.html_content, extraction_type
                )
                result.update(
                    content=content,
                    content_length=len(content),
                    original_content_length=original_length,
                    truncated=truncated,
                )
                result["success"] = True
            except Exception as e:
                result["error"] = f"{type(e).__name__}: {e}"
    except Exception as e:
        result["error"] = f"{type(e).__name__}: {e}"
    return result


async def _bulk_fetch(
    urls: list[str], timeout: int, method: str, extraction_type: str
) -> list[dict]:
    concurrency = BROWSER_CONCURRENCY if method in {"stealthy", "dynamic"} else MAX_CONCURRENCY
    semaphore = asyncio.Semaphore(max(1, concurrency))
    results: list[dict | None] = [None] * len(urls)

    async def run_one(index: int, url: str) -> None:
        async with semaphore:
            results[index] = await _fetch_single(url, timeout, method, extraction_type)

    tasks = {
        asyncio.create_task(run_one(index, str(url))): index
        for index, url in enumerate(urls)
    }
    done, pending = await asyncio.wait(tasks, timeout=max(1, BATCH_TIMEOUT))
    for task in pending:
        task.cancel()
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)
    for task in done:
        if task.cancelled():
            continue
        exc = task.exception()
        if exc is not None:
            index = tasks[task]
            results[index] = {
                "url": str(urls[index]),
                "success": False,
                "content": "",
                "error": f"{type(exc).__name__}: {exc}",
                "content_length": 0,
                "original_content_length": 0,
                "truncated": False,
            }
    for task in pending:
        index = tasks[task]
        results[index] = {
            "url": str(urls[index]),
            "success": False,
            "content": "",
            "error": f"batch deadline exceeded after {BATCH_TIMEOUT}s",
            "content_length": 0,
            "original_content_length": 0,
            "truncated": False,
            "batch_timeout": True,
        }
    return [result for result in results if result is not None]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    urls = arguments.get("urls", [])
    timeout = _clamp_timeout(arguments.get("timeout", 12))
    extraction_type = arguments.get("extraction_type", "markdown")
    if extraction_type not in {"markdown", "html", "text"}:
        extraction_type = "markdown"

    if not urls:
        return [TextContent(type="text", text=json.dumps({"error": "urls is required"}))]
    if len(urls) > MAX_URLS:
        return [TextContent(type="text", text=json.dumps({
            "error": f"too many URLs: max {MAX_URLS}",
            "total_urls": len(urls),
        }))]
    if name in {"scrapling_bulk_stealthy_fetch", "scrapling_bulk_fetch"} and len(urls) > MAX_BROWSER_URLS:
        return [TextContent(type="text", text=json.dumps({
            "error": f"too many browser URLs: max {MAX_BROWSER_URLS}",
            "total_urls": len(urls),
        }))]

    try:
        if name == "scrapling_bulk_get":
            raw_results = await _bulk_fetch(urls, timeout, "get", extraction_type)
        elif name == "scrapling_bulk_stealthy_fetch":
            raw_results = await _bulk_fetch(urls, timeout, "stealthy", extraction_type)
        elif name == "scrapling_bulk_fetch":
            raw_results = await _bulk_fetch(urls, timeout, "dynamic", extraction_type)
        else:
            return [TextContent(type="text", text=json.dumps({"error": f"unknown tool: {name}"}))]

        output = []
        remaining_chars = max(0, MAX_TOTAL_CONTENT_CHARS)
        for r in raw_results:
            entry = {
                "url": r["url"],
                "success": r["success"],
            }
            if r["success"]:
                content = r["content"]
                batch_truncated = len(content) > remaining_chars
                if batch_truncated:
                    content = content[:remaining_chars]
                remaining_chars -= len(content)
                entry["content_length"] = len(content)
                entry["original_content_length"] = r.get(
                    "original_content_length", len(r["content"])
                )
                entry["truncated"] = bool(r.get("truncated") or batch_truncated)
                entry["content_preview"] = content[:500]
                entry["content"] = content
            else:
                entry["error"] = r["error"]
                if r.get("batch_timeout"):
                    entry["batch_timeout"] = True
            output.append(entry)

        return [TextContent(
            type="text",
            text=json.dumps({
                "tool": name,
                "total_urls": len(urls),
                "success_count": sum(1 for r in raw_results if r["success"]),
                "fail_count": sum(1 for r in raw_results if not r["success"]),
                "content_chars": sum(
                    entry.get("content_length", 0) for entry in output
                ),
                "truncated_count": sum(
                    1 for entry in output if entry.get("truncated")
                ),
                "results": output,
            }, ensure_ascii=False, indent=2)
        )]
    except Exception as e:
        traceback.print_exc(file=sys.stderr)
        return [TextContent(type="text", text=json.dumps({
            "error": str(e),
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
