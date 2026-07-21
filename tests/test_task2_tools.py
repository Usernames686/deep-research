import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch


SKILL_DIR = Path(__file__).resolve().parents[1]
TOOLS_DIR = SKILL_DIR / "tools"
sys.path.insert(0, str(TOOLS_DIR))

from dr_local import extract_local  # noqa: E402
from dr_fetch import (  # noqa: E402
    fetch_pending,
    fetch_progress,
    ingest_fetch_batch,
    init_fetch_run,
    mark_fetch_processed,
)
from dr_manifest import build_task2_manifest, check_manifest  # noqa: E402
from dr_search import (  # noqa: E402
    _known_domains,
    _rank_result,
    build_fetch_queue,
    search_outline,
)


class Task2ToolTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)

    def tearDown(self):
        self.tempdir.cleanup()

    def write_json(self, name, value):
        path = self.root / name
        path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        return path

    def outline(self, questions=None):
        questions = questions or [{
            "question": "What changed?",
            "priority": "high",
            "search_keywords": ["change {target_year}"],
            "counter_keywords": ["change criticism"],
        }]
        return {
            "title": "Test",
            "language": "en",
            "depth_mode": "quick",
            "time_anchor": {"mode": "latest", "target_year": 2026},
            "source_suggestions": ["example.org"],
            "chapters": [{
                "title": "Finding",
                "sections": ["Evidence"],
                "sub_questions": questions,
            }],
        }

    def fact(self, url="https://example.org/a", year="2026"):
        return {
            "src": "Example",
            "yr": year,
            "met": "Metric",
            "val": 1,
            "u": "%",
            "ctx": "Published result",
            "url": url,
            "title": "Evidence",
            "conf": "high",
            "data_type": "actual",
        }

    def test_search_outline_ranks_deduplicates_and_records_trace(self):
        outline = self.write_json("outline.json", self.outline())
        sources = self.write_json("sources.json", {"sources": []})
        output = self.root / "search.json"
        trace = self.root / "trace.json"

        def fake_search(endpoint, query, lang, max_results, timeout):
            self.assertEqual(endpoint, "https://search.test/search")
            self.assertEqual(lang, "en")
            return [
                {"url": "https://news.test/item", "title": "News", "snippet": "", "engine": "mock", "published_date": "2026"},
                {"url": "https://example.org/report", "title": "Authority", "snippet": "", "engine": "mock", "published_date": "2026"},
                {"url": "https://example.org/report", "title": "Duplicate", "snippet": "", "engine": "mock", "published_date": "2026"},
            ]

        with patch("dr_search._search_query", side_effect=fake_search):
            result = search_outline(
                str(outline), str(sources), str(output), str(trace),
                endpoint="https://search.test/search", concurrency=3,
            )

        self.assertTrue(result["passed"], result)
        payload = json.loads(output.read_text(encoding="utf-8"))
        question = payload["questions"][0]
        self.assertEqual(len(question["queries"]), 3)
        self.assertEqual(question["results"][0]["url"], "https://example.org/report")
        self.assertEqual(len(question["results"]), 2)
        self.assertEqual(result["queries_total"], 3)

    def test_search_supplements_only_questions_with_inadequate_results(self):
        outline_data = self.outline([
            {"question": "Adequate", "priority": "medium",
             "search_keywords": ["adequate main", "adequate fallback"]},
            {"question": "Sparse", "priority": "medium",
             "search_keywords": ["sparse main", "sparse fallback"]},
        ])
        outline = self.write_json("outline.json", outline_data)
        sources = self.write_json("sources.json", {"sources": []})
        output = self.root / "search.json"
        trace = self.root / "trace.json"

        def fake_search(endpoint, query, lang, max_results, timeout):
            if query == "adequate main":
                suffixes = ["a", "b", "c"]
            elif query == "sparse main":
                suffixes = ["d"]
            elif query == "sparse fallback":
                suffixes = ["e", "f"]
            else:
                self.fail(f"Unexpected supplement query: {query}")
            return [{
                "url": f"https://example.org/{suffix}", "title": suffix,
                "snippet": "", "engine": "mock", "published_date": "2026",
            } for suffix in suffixes]

        with patch("dr_search._search_query", side_effect=fake_search):
            result = search_outline(
                str(outline), str(sources), str(output), str(trace),
                endpoint="https://search.test/search",
            )

        self.assertTrue(result["passed"], result)
        payload = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(
            [query["type"] for query in payload["questions"][0]["queries"]],
            ["main"],
        )
        self.assertEqual(
            [query["type"] for query in payload["questions"][1]["queries"]],
            ["main", "fallback"],
        )
        self.assertEqual(result["initial_queries"], 2)
        self.assertEqual(result["fallback_queries"], 1)
        self.assertEqual(result["questions_insufficient"], 0)

    def test_search_uses_one_language_matched_source_template_fallback(self):
        outline = self.write_json("source-outline.json", self.outline([{
            "question": "Sparse", "priority": "medium",
            "search_keywords": ["sparse main"],
        }]))
        sources = self.write_json("source-fallbacks.json", {"sources": [
            {
                "id": "wrong-language", "lang": ["zh"], "priority": 1,
                "url_template": "https://www.who.int/search?q={query}",
            },
            {
                "id": "nature", "lang": ["en"], "priority": 1,
                "url_template": "https://www.nature.com/search?q={query}",
            },
            {
                "id": "lower-priority", "lang": ["en"], "priority": 3,
                "url_template": "https://www.bbc.com/search?q={query}",
            },
        ]})
        output = self.root / "source-search.json"
        trace = self.root / "source-trace.json"

        def fake_search(endpoint, query, lang, max_results, timeout):
            if query == "sparse main":
                suffixes = ["a"]
            elif query == "site:nature.com sparse main":
                suffixes = ["b", "c"]
            else:
                self.fail(f"Unexpected source fallback query: {query}")
            return [{
                "url": f"https://example.org/{suffix}", "title": suffix,
                "snippet": "", "engine": "mock", "published_date": "2026",
            } for suffix in suffixes]

        with patch("dr_search._search_query", side_effect=fake_search):
            result = search_outline(
                str(outline), str(sources), str(output), str(trace),
                endpoint="https://search.test/search",
            )

        self.assertTrue(result["passed"], result)
        payload = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(
            payload["questions"][0]["queries"],
            [
                {"type": "main", "query": "sparse main", "result_count": 1},
                {"type": "source_fallback", "query": "site:nature.com sparse main",
                 "result_count": 2},
            ],
        )
        self.assertEqual(result["fallback_queries"], 1)
        self.assertEqual(result["source_fallback_queries"], 1)

    def test_source_ranking_matches_sibling_subdomains(self):
        sources = self.write_json("sources.json", {"sources": [{
            "health_url": "https://www.example.com/health",
            "url_template": "https://api.example.com/search?q={query}",
            "priority": 1,
        }]})
        known = _known_domains(str(sources))

        configured = _rank_result({
            "url": "https://reports.example.com/item", "published_date": "2026",
        }, [], known)
        generic_org = _rank_result({
            "url": "https://unknown.org/item", "published_date": "2026",
        }, [], known)

        self.assertEqual(known, {"example.com": 1})
        self.assertLess(configured, generic_org)

    def test_build_fetch_queue_is_bounded_and_merges_question_ownership(self):
        questions = []
        for q_index in range(2):
            questions.append({
                "q_index": q_index,
                "priority": "high" if q_index == 0 else "medium",
                "results": [
                    {"url": "https://example.org/shared", "title": "Shared"},
                    {"url": f"https://example.org/{q_index}-a", "title": "A"},
                    {"url": f"https://example.org/{q_index}-b", "title": "B"},
                    {"url": f"https://example.org/{q_index}-ignored", "title": "Ignored"},
                ],
            })
        search = self.write_json("search.json", {"questions": questions})
        output = self.root / "queue.json"

        result = build_fetch_queue(str(search), str(output), "quick")

        self.assertTrue(result["passed"], result)
        queue = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(len(queue["items"]), 5)
        self.assertEqual(queue["items"][0]["q_indices"], [0, 1])
        self.assertFalse(any("ignored" in item["url"] for item in queue["items"]))

    def test_fetch_status_resumes_and_retries_only_failed_urls(self):
        queue = self.write_json("queue.json", {"items": [
            {"url": "https://example.org/a", "title": "A", "q_indices": [0], "priorities": ["high"]},
            {"url": "https://example.org/b", "title": "B", "q_indices": [1], "priorities": ["medium"]},
        ]})
        status = self.root / "task2-progress.json"
        output_dir = self.root / "fetched"
        first = init_fetch_run(str(queue), str(output_dir), str(status))
        resumed = init_fetch_run(str(queue), str(output_dir), str(status))
        self.assertTrue(first["passed"], first)
        self.assertFalse(first["resumed"])
        self.assertTrue(resumed["resumed"])

        batch = self.write_json("batch.json", {"results": [
            {"url": "https://example.org/a", "success": True,
             "content": "# A\nEvidence", "original_content_length": 12,
             "truncated": False},
            {"url": "https://example.org/b", "success": False,
             "error": "timeout"},
        ]})
        ingested = ingest_fetch_batch(str(status), str(batch), "get")
        self.assertTrue(ingested["passed"], ingested)
        self.assertEqual(ingested["success"], 1)
        self.assertEqual(ingested["failed"], 1)
        duplicate = ingest_fetch_batch(str(status), str(batch), "get")
        self.assertTrue(duplicate["passed"], duplicate)
        self.assertEqual(duplicate["ingested"], 0)
        self.assertEqual(len(duplicate["warnings"]), 2)
        failed = fetch_progress(str(status), "failed")
        self.assertEqual([item["url"] for item in failed["selected"]],
                         ["https://example.org/b"])

        browser_result = [{
            "url": "https://example.org/b", "success": True,
            "content": "# B\nRecovered", "original_content_length": 13,
            "truncated": False, "error": "",
        }]
        with patch("dr_fetch._run_bulk_fetch", new=AsyncMock(return_value=browser_result)):
            retried = fetch_pending(
                str(status), method="dynamic", state="failed", limit=2
            )
        self.assertTrue(retried["passed"], retried)
        self.assertEqual(retried["success"], 2)
        self.assertEqual(retried["failed"], 0)
        final = json.loads(status.read_text(encoding="utf-8"))
        self.assertEqual(len(final["items"][1]["attempts"]), 2)
        self.assertEqual(final["items"][1]["method"], "dynamic")
        self.assertIn("Recovered", Path(final["items"][1]["output_path"]).read_text())

        unprocessed = fetch_progress(str(status), "unprocessed")
        self.assertEqual(len(unprocessed["selected"]), 2)
        datapool = self.write_json("incremental-pool.json", [
            {"q_index": 0, "facts": [self.fact("https://example.org/a")], "gaps": []},
            {"q_index": 1, "facts": [], "gaps": [{
                "url": "https://example.org/b",
                "reason": "No relevant fact in this source",
            }]},
        ])
        output_paths = [Path(item["output_path"]) for item in final["items"]]
        processed = mark_fetch_processed(
            str(status), str(datapool), [1, 2], release=True
        )
        self.assertTrue(processed["passed"], processed)
        self.assertEqual(processed["released"], 2)
        self.assertTrue(all(not path.exists() for path in output_paths))
        self.assertFalse(fetch_progress(str(status), "unprocessed")["selected"])

    def test_release_requires_matching_fact_or_explicit_gap(self):
        queue = self.write_json("queue.json", {"items": [{
            "url": "https://example.org/a", "q_indices": [0], "priorities": ["high"]
        }]})
        status = self.root / "task2-progress.json"
        init_fetch_run(str(queue), str(self.root / "fetched"), str(status))
        batch = self.write_json("batch.json", {"results": [{
            "url": "https://example.org/a", "success": True, "content": "Evidence"
        }]})
        ingest_fetch_batch(str(status), str(batch), "get")
        pool = self.write_json("pool.json", [{"q_index": 0, "facts": [], "gaps": []}])

        result = mark_fetch_processed(str(status), str(pool), [1], release=True)

        self.assertFalse(result["passed"])
        item = json.loads(status.read_text(encoding="utf-8"))["items"][0]
        self.assertTrue(Path(item["output_path"]).exists())

    def test_question_level_gap_cannot_release_unrelated_source(self):
        queue = self.write_json("generic-gap-queue.json", {"items": [{
            "url": "https://example.org/a", "q_indices": [0], "priorities": ["high"]
        }]})
        status = self.root / "generic-gap-status.json"
        init_fetch_run(str(queue), str(self.root / "generic-gap-fetched"), str(status))
        batch = self.write_json("generic-gap-batch.json", {"results": [{
            "url": "https://example.org/a", "success": True, "content": "Evidence"
        }]})
        ingest_fetch_batch(str(status), str(batch), "get")
        pool = self.write_json("generic-gap-pool.json", [{
            "q_index": 0, "facts": [], "gaps": ["No public data"]
        }])

        result = mark_fetch_processed(str(status), str(pool), [1], release=True)

        self.assertFalse(result["passed"])
        self.assertIn("source-specific gap", result["issues"][0])
        item = json.loads(status.read_text(encoding="utf-8"))["items"][0]
        self.assertTrue(Path(item["output_path"]).exists())

    def test_release_move_failure_rolls_back_all_content(self):
        urls = ["https://example.org/a", "https://example.org/b"]
        queue = self.write_json("rollback-queue.json", {"items": [{
            "url": url, "q_indices": [index], "priorities": ["medium"]
        } for index, url in enumerate(urls)]})
        status = self.root / "rollback-status.json"
        init_fetch_run(str(queue), str(self.root / "rollback-fetched"), str(status))
        batch = self.write_json("rollback-batch.json", {"results": [{
            "url": url, "success": True, "content": f"Evidence {index}"
        } for index, url in enumerate(urls)]})
        ingest_fetch_batch(str(status), str(batch), "get")
        pool = self.write_json("rollback-pool.json", [{
            "q_index": index, "facts": [self.fact(url)], "gaps": []
        } for index, url in enumerate(urls)])
        before = json.loads(status.read_text(encoding="utf-8"))
        original_paths = [Path(item["output_path"]) for item in before["items"]]
        real_replace = os.replace

        def fail_second_content_move(source, destination):
            if str(source).endswith("0002.md") and ".released" in str(destination):
                raise OSError("simulated move failure")
            return real_replace(source, destination)

        with patch("dr_fetch.os.replace", side_effect=fail_second_content_move):
            result = mark_fetch_processed(str(status), str(pool), [1, 2], release=True)

        self.assertFalse(result["passed"])
        self.assertTrue(all(path.exists() for path in original_paths))
        after = json.loads(status.read_text(encoding="utf-8"))
        self.assertTrue(all(not item["processed"] for item in after["items"]))

    def test_release_rejects_item_without_question_ownership(self):
        queue = self.write_json("unowned-queue.json", {"items": [{
            "url": "https://example.org/a", "q_indices": [], "priorities": []
        }]})
        status = self.root / "unowned-status.json"
        init_fetch_run(str(queue), str(self.root / "unowned-fetched"), str(status))
        batch = self.write_json("unowned-batch.json", {"results": [{
            "url": "https://example.org/a", "success": True, "content": "Evidence"
        }]})
        ingest_fetch_batch(str(status), str(batch), "get")
        pool = self.write_json("unowned-pool.json", [{
            "q_index": 0, "facts": [self.fact()], "gaps": []
        }])
        before = json.loads(status.read_text(encoding="utf-8"))["items"][0]

        result = mark_fetch_processed(str(status), str(pool), [1], release=True)

        self.assertFalse(result["passed"])
        self.assertTrue(any("no owning q_index" in issue for issue in result["issues"]))
        self.assertTrue(Path(before["output_path"]).exists())

    def test_release_prevalidates_all_paths_before_moving_content(self):
        urls = ["https://example.org/a", "https://example.org/b"]
        queue = self.write_json("path-queue.json", {"items": [{
            "url": url, "q_indices": [index], "priorities": ["medium"]
        } for index, url in enumerate(urls)]})
        status = self.root / "path-status.json"
        output_dir = self.root / "path-fetched"
        init_fetch_run(str(queue), str(output_dir), str(status))
        batch = self.write_json("path-batch.json", {"results": [{
            "url": url, "success": True, "content": f"Evidence {index}"
        } for index, url in enumerate(urls)]})
        ingest_fetch_batch(str(status), str(batch), "get")
        pool = self.write_json("path-pool.json", [{
            "q_index": index, "facts": [self.fact(url)], "gaps": []
        } for index, url in enumerate(urls)])
        state = json.loads(status.read_text(encoding="utf-8"))
        first_path = Path(state["items"][0]["output_path"])
        outside_path = self.root / "outside.md"
        outside_path.write_text("Outside", encoding="utf-8")
        state["items"][1]["output_path"] = str(outside_path)
        status.write_text(json.dumps(state), encoding="utf-8")

        result = mark_fetch_processed(str(status), str(pool), [1, 2], release=True)

        self.assertFalse(result["passed"])
        self.assertTrue(any("outside fetch output" in issue for issue in result["issues"]))
        self.assertTrue(first_path.exists())
        self.assertTrue(outside_path.exists())

    def test_status_write_failure_restores_content_and_run_can_resume(self):
        queue = self.write_json("write-queue.json", {"items": [{
            "url": "https://example.org/a", "q_indices": [0], "priorities": ["medium"]
        }]})
        status = self.root / "write-status.json"
        init_fetch_run(str(queue), str(self.root / "write-fetched"), str(status))
        batch = self.write_json("write-batch.json", {"results": [{
            "url": "https://example.org/a", "success": True, "content": "Evidence"
        }]})
        ingest_fetch_batch(str(status), str(batch), "get")
        pool = self.write_json("write-pool.json", [{
            "q_index": 0, "facts": [self.fact()], "gaps": []
        }])
        original = json.loads(status.read_text(encoding="utf-8"))["items"][0]
        original_path = Path(original["output_path"])

        with patch("dr_fetch._write_json", side_effect=OSError("simulated status failure")):
            failed = mark_fetch_processed(str(status), str(pool), [1], release=True)

        self.assertFalse(failed["passed"])
        self.assertTrue(original_path.exists())
        unchanged = json.loads(status.read_text(encoding="utf-8"))["items"][0]
        self.assertFalse(unchanged["processed"])
        self.assertEqual(unchanged["output_path"], str(original_path))

        resumed = mark_fetch_processed(str(status), str(pool), [1], release=True)
        self.assertTrue(resumed["passed"], resumed)
        self.assertFalse(original_path.exists())
        self.assertTrue(resumed["complete"])

    def test_release_delete_failure_restores_all_content_and_status(self):
        urls = ["https://example.org/a", "https://example.org/b"]
        queue = self.write_json("delete-queue.json", {"items": [{
            "url": url, "q_indices": [index], "priorities": ["medium"]
        } for index, url in enumerate(urls)]})
        status = self.root / "delete-status.json"
        init_fetch_run(str(queue), str(self.root / "delete-fetched"), str(status))
        batch = self.write_json("delete-batch.json", {"results": [{
            "url": url, "success": True, "content": f"Evidence {index}"
        } for index, url in enumerate(urls)]})
        ingest_fetch_batch(str(status), str(batch), "get")
        pool = self.write_json("delete-pool.json", [{
            "q_index": index, "facts": [self.fact(url)], "gaps": []
        } for index, url in enumerate(urls)])
        before = json.loads(status.read_text(encoding="utf-8"))
        original_paths = [Path(item["output_path"]) for item in before["items"]]
        original_contents = [path.read_text(encoding="utf-8") for path in original_paths]
        real_unlink = Path.unlink

        def fail_second_archive_delete(path, *args, **kwargs):
            if path.name == "0002.md" and path.parent.name == ".released":
                raise OSError("simulated delete failure")
            return real_unlink(path, *args, **kwargs)

        with patch.object(
            Path, "unlink", autospec=True, side_effect=fail_second_archive_delete
        ):
            result = mark_fetch_processed(str(status), str(pool), [1, 2], release=True)

        self.assertFalse(result["passed"])
        self.assertTrue(all(path.exists() for path in original_paths))
        self.assertEqual(
            [path.read_text(encoding="utf-8") for path in original_paths],
            original_contents,
        )
        restored = json.loads(status.read_text(encoding="utf-8"))
        self.assertTrue(all(not item["processed"] for item in restored["items"]))
        self.assertTrue(all(item["output_path"] for item in restored["items"]))

    def test_fetch_status_rejects_a_different_queue(self):
        status = self.root / "task2-progress.json"
        first_queue = self.write_json("first.json", {
            "items": [{"url": "https://example.org/a"}]
        })
        second_queue = self.write_json("second.json", {
            "items": [{"url": "https://example.org/b"}]
        })
        init_fetch_run(str(first_queue), str(self.root / "fetched"), str(status))
        result = init_fetch_run(
            str(second_queue), str(self.root / "fetched"), str(status)
        )
        self.assertFalse(result["passed"])
        self.assertIn("different queue", result["issues"][0])

    def test_fetch_status_rejects_changed_question_ownership(self):
        status = self.root / "task2-progress.json"
        first_queue = self.write_json("first-owned.json", {"items": [{
            "url": "https://example.org/a", "q_indices": [0],
            "priorities": ["high"],
        }]})
        second_queue = self.write_json("second-owned.json", {"items": [{
            "url": "https://example.org/a", "q_indices": [1],
            "priorities": ["medium"],
        }]})
        init_fetch_run(str(first_queue), str(self.root / "fetched"), str(status))

        result = init_fetch_run(
            str(second_queue), str(self.root / "fetched"), str(status)
        )

        self.assertFalse(result["passed"])
        self.assertIn("different queue", result["issues"][0])

    def test_extract_local_handles_text_docx_pdf_and_excludes_output_tree(self):
        from docx import Document
        from pypdf import PdfWriter
        from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

        source_dir = self.root / "sources"
        source_dir.mkdir()
        (source_dir / "notes.md").write_text("Local notes", encoding="utf-8")
        document = Document()
        document.add_paragraph("DOCX evidence")
        document.save(source_dir / "evidence.docx")

        writer = PdfWriter()
        page = writer.add_blank_page(width=612, height=792)
        font = DictionaryObject({
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        })
        page[NameObject("/Resources")] = DictionaryObject({
            NameObject("/Font"): DictionaryObject({
                NameObject("/F1"): writer._add_object(font),
            })
        })
        stream = DecodedStreamObject()
        stream.set_data(b"BT /F1 12 Tf 72 720 Td (PDF evidence) Tj ET")
        page[NameObject("/Contents")] = writer._add_object(stream)
        with (source_dir / "evidence.pdf").open("wb") as handle:
            writer.write(handle)

        output_dir = source_dir / "extracted"
        output_dir.mkdir()
        (output_dir / "old.txt").write_text("must not be re-ingested", encoding="utf-8")
        manifest = self.root / "local-manifest.json"
        result = extract_local([str(source_dir)], str(output_dir), str(manifest))

        self.assertTrue(result["passed"], result)
        self.assertEqual(result["file_count"], 3)
        data = json.loads(manifest.read_text(encoding="utf-8"))
        extracted = "\n".join(
            Path(item["output_path"]).read_text(encoding="utf-8")
            for item in data["files"] if item["status"] == "ok"
        )
        self.assertIn("DOCX evidence", extracted)
        self.assertIn("PDF evidence", extracted)
        self.assertNotIn("must not be re-ingested", extracted)

    def test_local_extraction_caps_large_documents(self):
        source = self.root / "large.txt"
        source.write_text("x" * 100, encoding="utf-8")
        manifest = self.root / "manifest.json"
        with patch.dict(os.environ, {"DEEP_RESEARCH_LOCAL_MAX_CHARS": "20"}):
            result = extract_local(
                [str(source)], str(self.root / "output"), str(manifest)
            )
        self.assertTrue(result["passed"], result)
        record = json.loads(manifest.read_text(encoding="utf-8"))["files"][0]
        self.assertTrue(record["truncated"])
        self.assertEqual(record["chars"], 20)
        self.assertEqual(record["original_chars"], 100)

    def test_online_manifest_reports_real_fetch_and_fallback_state(self):
        questions = [
            {"question": "Core", "priority": "high"},
            {"question": "Secondary", "priority": "medium"},
        ]
        outline = self.write_json("outline.json", self.outline(questions))
        pool = self.write_json("pool.json", [
            {"q_index": 0, "facts": [
                self.fact("https://example.org/a"),
                self.fact("https://data.gov/b"),
            ], "gaps": [], "controversies": []},
            {"q_index": 1, "facts": [], "gaps": ["not announced"], "controversies": []},
        ])
        search = self.write_json("search.json", {
            "engine": "searxng",
            "questions": [
                {"q_index": 0, "results": [{"url": "https://example.org/a"}],
                 "queries": [{"type": "main"}, {"type": "fallback"}]},
                {"q_index": 1, "results": [],
                 "queries": [{"type": "english_fallback"}]},
            ],
        })
        fetch = self.write_json("fetch.json", {"items": [
            {"url": "https://example.org/a", "success": True, "method": "get"},
            {"url": "https://data.gov/b", "success": True, "method": "dynamic"},
        ]})
        manifest = self.root / "task2-manifest.json"

        result = build_task2_manifest(
            str(outline), str(pool), str(manifest), str(search), str(fetch)
        )

        self.assertTrue(result["passed"], result)
        data = json.loads(manifest.read_text(encoding="utf-8"))
        self.assertEqual(data["fetch_method"], "Scrapling (1 browser fallbacks)")
        self.assertTrue(data["free_fallback"])
        self.assertTrue(data["english_fallback"])
        self.assertEqual(data["coverage_summary"], "insufficient")
        self.assertTrue(data["data_limited"])
        self.assertTrue(check_manifest(str(manifest))["passed"])

    def test_offline_manifest_accepts_yearless_local_sources(self):
        outline = self.write_json("outline.json", self.outline([{
            "question": "Local evidence", "priority": "medium"
        }]))
        local_path = str(self.root / "source.pdf")
        pool = self.write_json("pool.json", [{
            "q_index": 0,
            "facts": [self.fact(local_path, "")],
            "gaps": [],
            "controversies": [],
        }])
        manifest = self.root / "offline-manifest.json"

        result = build_task2_manifest(
            str(outline), str(pool), str(manifest), source_mode="offline"
        )

        self.assertTrue(result["passed"], result)
        data = json.loads(manifest.read_text(encoding="utf-8"))
        self.assertEqual(data["fetch_method"], "local_files")
        self.assertEqual(data["coverage_summary"], "adequate")
        self.assertEqual(data["unique_domains"], 1)

    def test_mixed_manifest_combines_web_and_yearless_local_sources(self):
        questions = [
            {"question": "Web evidence", "priority": "medium"},
            {"question": "Local evidence", "priority": "medium"},
        ]
        outline = self.write_json("outline.json", self.outline(questions))
        local_path = str((self.root / "local.pdf").resolve())
        pool = self.write_json("pool.json", [
            {"q_index": 0, "facts": [self.fact()], "gaps": [], "controversies": []},
            {"q_index": 1, "facts": [self.fact(local_path, "")], "gaps": [], "controversies": []},
        ])
        search = self.write_json("search.json", {
            "engine": "searxng", "questions": []
        })
        fetch = self.write_json("fetch.json", {"items": [{
            "success": True, "method": "get"
        }]})
        manifest = self.root / "mixed-manifest.json"
        result = build_task2_manifest(
            str(outline), str(pool), str(manifest), str(search), str(fetch),
            source_mode="mixed",
        )
        self.assertTrue(result["passed"], result)
        data = json.loads(manifest.read_text(encoding="utf-8"))
        self.assertEqual(data["coverage_summary"], "adequate")
        self.assertIn("local_files", data["fetch_method"])
        self.assertTrue(check_manifest(str(manifest))["passed"])

    def test_cli_help_and_manifest_validation_smoke(self):
        cli = TOOLS_DIR / "dr_tools.py"
        help_result = subprocess.run(
            [sys.executable, str(cli), "--help"],
            text=True, capture_output=True, check=False,
        )
        self.assertEqual(help_result.returncode, 0, help_result.stderr)
        self.assertIn("search-outline", help_result.stdout)

        invalid = self.write_json("invalid-manifest.json", {"task": 2})
        check_result = subprocess.run(
            [sys.executable, str(cli), "check-manifest", str(invalid)],
            text=True, capture_output=True, check=False,
        )
        self.assertEqual(check_result.returncode, 1)
        self.assertIn("FAIL", check_result.stdout)

        local_source = self.root / "本地资料.md"
        local_source.write_text("本地证据", encoding="utf-8")
        inputs_file = self.write_json("inputs.json", [str(local_source)])
        extract_result = subprocess.run([
            sys.executable, str(cli), "extract-local",
            "--inputs-file", str(inputs_file),
            "--output-dir", str(self.root / "cli-extracted"),
            "--manifest", str(self.root / "cli-local-manifest.json"),
        ], text=True, capture_output=True, check=False)
        self.assertEqual(extract_result.returncode, 0, extract_result.stderr)
        self.assertIn("PASS", extract_result.stdout)


if __name__ == "__main__":
    unittest.main()
