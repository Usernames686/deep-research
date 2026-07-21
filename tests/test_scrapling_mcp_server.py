import importlib.util
import ipaddress
import json
import asyncio
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import ANY, AsyncMock, patch


MODULE_PATH = Path(__file__).resolve().parents[1] / "scrapling-mcp-server.py"
SPEC = importlib.util.spec_from_file_location("scrapling_mcp_server", MODULE_PATH)
scrapling_mcp_server = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(scrapling_mcp_server)


class ScraplingMcpServerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        scrapling_mcp_server._DNS_CACHE.clear()

    async def test_standard_fetch_uses_native_async_api(self):
        response = SimpleNamespace(html_content="<html><body>standard</body></html>")
        async_get = AsyncMock(return_value=response)

        with patch.object(
            scrapling_mcp_server.scrapling.AsyncFetcher, "get", new=async_get
        ), patch.object(
            scrapling_mcp_server,
            "_validate_url_async",
            new=AsyncMock(return_value=(True, "")),
        ):
            result = await scrapling_mcp_server._fetch_single(
                "https://example.com", 5, "get", "text"
            )

        self.assertTrue(result["success"])
        self.assertIn("standard", result["content"])
        async_get.assert_awaited_once_with(
            "https://example.com", timeout=5, follow_redirects="safe"
        )

    async def test_dynamic_fetch_uses_native_async_api(self):
        response = SimpleNamespace(html_content="<html><body>dynamic</body></html>")
        async_fetch = AsyncMock(return_value=response)

        with patch.object(
            scrapling_mcp_server.scrapling.DynamicFetcher,
            "async_fetch",
            new=async_fetch,
        ), patch.object(
            scrapling_mcp_server,
            "_validate_url_async",
            new=AsyncMock(return_value=(True, "")),
        ):
            result = await scrapling_mcp_server._fetch_single(
                "https://example.com", 5, "dynamic", "text"
            )

        self.assertTrue(result["success"])
        self.assertIn("dynamic", result["content"])
        async_fetch.assert_awaited_once_with(
            "https://example.com", headless=True, timeout=5000, page_setup=ANY
        )

    async def test_stealthy_fetch_uses_native_async_api(self):
        response = SimpleNamespace(html_content="<html><body>stealthy</body></html>")
        async_fetch = AsyncMock(return_value=response)

        with patch.object(
            scrapling_mcp_server.scrapling.StealthyFetcher,
            "async_fetch",
            new=async_fetch,
        ), patch.object(
            scrapling_mcp_server,
            "_validate_url_async",
            new=AsyncMock(return_value=(True, "")),
        ):
            result = await scrapling_mcp_server._fetch_single(
                "https://example.com", 5, "stealthy", "text"
            )

        self.assertTrue(result["success"])
        self.assertIn("stealthy", result["content"])
        async_fetch.assert_awaited_once_with(
            "https://example.com", headless=True, timeout=5000, page_setup=ANY
        )

    async def test_browser_route_blocks_private_redirects_and_subresources(self):
        blocked_route = SimpleNamespace(
            continue_=AsyncMock(), abort=AsyncMock()
        )
        blocked_request = SimpleNamespace(
            url="http://127.0.0.1/admin",
            is_navigation_request=lambda: True,
        )
        with patch.object(
            scrapling_mcp_server,
            "_validate_url_async",
            new=AsyncMock(return_value=(False, "blocked")),
        ):
            await scrapling_mcp_server._secure_browser_route(
                blocked_route, blocked_request
            )
        blocked_route.abort.assert_awaited_once_with("blockedbyclient")
        blocked_route.continue_.assert_not_awaited()

        data_route = SimpleNamespace(continue_=AsyncMock(), abort=AsyncMock())
        data_request = SimpleNamespace(
            url="data:image/png;base64,AA==",
            is_navigation_request=lambda: False,
        )
        await scrapling_mcp_server._secure_browser_route(data_route, data_request)
        data_route.continue_.assert_awaited_once_with()
        data_route.abort.assert_not_awaited()

    async def test_call_tool_preserves_response_contract(self):
        raw_results = [
            {
                "url": "https://example.com",
                "success": True,
                "content": "example content",
                "error": "",
                "content_length": 15,
                "original_content_length": 15,
                "truncated": False,
            }
        ]
        bulk_fetch = AsyncMock(return_value=raw_results)

        with patch.object(scrapling_mcp_server, "_bulk_fetch", new=bulk_fetch):
            response = await scrapling_mcp_server.call_tool(
                "scrapling_bulk_fetch",
                {"urls": ["https://example.com"], "timeout": 5},
            )

        payload = json.loads(response[0].text)
        self.assertEqual(payload["tool"], "scrapling_bulk_fetch")
        self.assertEqual(payload["success_count"], 1)
        self.assertEqual(payload["fail_count"], 0)
        self.assertEqual(payload["results"][0]["content"], "example content")
        self.assertFalse(payload["results"][0]["truncated"])
        bulk_fetch.assert_awaited_once_with(
            ["https://example.com"], 5, "dynamic", "markdown"
        )

    async def test_bulk_fetch_runs_concurrently_and_preserves_order(self):
        async def fake_fetch(url, timeout, method, extraction_type):
            await asyncio.sleep(0.08 if url.endswith("1") else 0.04)
            return {
                "url": url,
                "success": True,
                "content": url,
                "error": "",
                "content_length": len(url),
                "original_content_length": len(url),
                "truncated": False,
            }

        started = time.perf_counter()
        with patch.object(scrapling_mcp_server, "_fetch_single", new=fake_fetch):
            results = await scrapling_mcp_server._bulk_fetch(
                ["url1", "url2", "url3", "url4"], 5, "get", "text"
            )
        elapsed = time.perf_counter() - started

        self.assertLess(elapsed, 0.2)
        self.assertEqual([result["url"] for result in results], [
            "url1", "url2", "url3", "url4"
        ])

    async def test_bulk_fetch_marks_items_exceeding_batch_deadline(self):
        async def slow_fetch(url, timeout, method, extraction_type):
            await asyncio.sleep(1)
            return {"url": url, "success": True, "content": url, "error": ""}

        with patch.object(scrapling_mcp_server, "_fetch_single", new=slow_fetch), patch.object(
            scrapling_mcp_server, "BATCH_TIMEOUT", 0.01
        ):
            results = await scrapling_mcp_server._bulk_fetch(
                ["url1", "url2"], 5, "get", "text"
            )

        self.assertEqual(len(results), 2)
        self.assertTrue(all(result.get("batch_timeout") for result in results))

    async def test_browser_tools_enforce_smaller_batch_limit(self):
        with patch.object(scrapling_mcp_server, "MAX_BROWSER_URLS", 2):
            response = await scrapling_mcp_server.call_tool(
                "scrapling_bulk_fetch",
                {"urls": ["https://a.example", "https://b.example", "https://c.example"]},
            )

        payload = json.loads(response[0].text)
        self.assertIn("too many browser URLs", payload["error"])

    async def test_total_content_budget_is_enforced(self):
        raw_results = [
            {
                "url": f"https://example.com/{index}",
                "success": True,
                "content": "x" * 10,
                "error": "",
                "content_length": 10,
                "original_content_length": 10,
                "truncated": False,
            }
            for index in range(2)
        ]
        with patch.object(
            scrapling_mcp_server, "_bulk_fetch", new=AsyncMock(return_value=raw_results)
        ), patch.object(scrapling_mcp_server, "MAX_TOTAL_CONTENT_CHARS", 12):
            response = await scrapling_mcp_server.call_tool(
                "scrapling_bulk_get",
                {"urls": [item["url"] for item in raw_results]},
            )

        payload = json.loads(response[0].text)
        self.assertEqual(payload["content_chars"], 12)
        self.assertEqual(payload["truncated_count"], 1)
        self.assertEqual(len(payload["results"][1]["content"]), 2)

    async def test_strict_dns_rejects_private_resolution(self):
        private_result = [(socket_family, None, None, None, ("127.0.0.1", 0))
                          for socket_family in (2,)]
        with patch.object(scrapling_mcp_server.socket, "getaddrinfo", return_value=private_result):
            allowed, error = await scrapling_mcp_server._resolve_public_host("private.example")

        self.assertFalse(allowed)
        self.assertIn("private", error)

    async def test_strict_dns_allows_configured_proxy_fake_ip_only_after_resolution(self):
        fake_result = [(2, None, None, None, ("198.18.0.136", 0))]
        with patch.object(
            scrapling_mcp_server.socket, "getaddrinfo", return_value=fake_result
        ), patch.object(
            scrapling_mcp_server,
            "ALLOWED_DNS_NETWORKS",
            (ipaddress.ip_network("198.18.0.0/15"),),
        ):
            allowed, error = await scrapling_mcp_server._resolve_public_host(
                "example.com"
            )

        self.assertTrue(allowed, error)
        direct_allowed, _ = scrapling_mcp_server._validate_url(
            "http://198.18.0.136/"
        )
        self.assertFalse(direct_allowed)

    def test_url_validation_blocks_non_http_and_private_ip(self):
        self.assertFalse(scrapling_mcp_server._validate_url("file:///tmp/a")[0])
        self.assertFalse(scrapling_mcp_server._validate_url("http://127.0.0.1")[0])

    def test_extract_content_reports_truncation(self):
        with patch.object(scrapling_mcp_server, "MAX_CONTENT_CHARS", 5):
            content, original_length, truncated = scrapling_mcp_server._extract_content(
                "abcdefgh", "html"
            )
        self.assertEqual(content, "abcde")
        self.assertEqual(original_length, 8)
        self.assertTrue(truncated)


if __name__ == "__main__":
    unittest.main()
