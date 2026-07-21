import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS_DIR))

from dr_check import (  # noqa: E402
    check_citations,
    check_datapool,
    check_outline,
    load_profile,
    qa_report,
    validate_all_chapters,
    word_count,
)
from dr_gen import (  # noqa: E402
    assemble_report,
    cleanup_run,
    convert_citations,
    detect_engine,
    generate_confidence_section,
    generate_citation_map,
    refresh_metadata,
)
from lang_config import LANG_CONFIG  # noqa: E402


class ReportGenerationTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.outline = self.root / "outline.json"
        self.outline.write_text(json.dumps({
            "title": "Test Report",
            "language": "en",
            "depth_mode": "quick",
            "chapters": [{"title": "Finding", "sections": ["Evidence"]}],
        }), encoding="utf-8")
        self.pool = self.root / "pool.json"
        self.pool.write_text(json.dumps([{
            "q_index": 0,
            "priority": "medium",
            "question": "Question",
            "src": ["Example"],
            "facts": [{
                "src": "Example",
                "yr": "",
                "met": "Metric",
                "val": 1,
                "u": "%",
                "ctx": "Context",
                "url": str(self.root / "source.pdf"),
                "title": "Local source",
                "conf": "high",
                "data_type": "actual",
            }],
            "controversies": [],
            "gaps": [],
        }]), encoding="utf-8")
        self.chapters = self.root / "chapters"
        self.chapters.mkdir()

    def tearDown(self):
        self.tempdir.cleanup()

    def write_chapter(self):
        (self.chapters / "chapter-1.md").write_text(
            "> Core judgment\n\n### 1.1 Evidence\n\nEvidence paragraph [1].\n",
            encoding="utf-8",
        )

    def run_report_e2e(self, suffix, lang, mode, time_anchor, target_year):
        profile = load_profile(mode)
        chapter_count = profile["min_chapters"]
        section_count = profile["min_sections"]
        min_paragraphs = profile["min_paragraphs"]
        min_tables = profile["min_tables"]
        vocabulary = {
            "zh": {
                "title": "端到端研究报告", "type": "技术研究",
                "chapter": "结论", "section": "证据",
                "question": "发生了什么变化", "judgment": "核心判断",
                "paragraph": "该段说明数据、因果关系与适用边界",
            },
            "en": {
                "title": "End-to-End Research Report", "type": "Technical research",
                "chapter": "Finding", "section": "Evidence",
                "question": "What changed", "judgment": "Core judgment",
                "paragraph": "This paragraph explains evidence, causality, and scope",
            },
            "ar": {
                "title": "تقرير بحث متكامل", "type": "بحث تقني",
                "chapter": "النتيجة", "section": "الأدلة",
                "question": "ما الذي تغير", "judgment": "الحكم الأساسي",
                "paragraph": "تشرح هذه الفقرة الأدلة والعلاقة السببية وحدود الاستنتاج",
            },
        }[lang]
        root = self.root / suffix
        root.mkdir()
        chapter_dir = root / "chapters"
        chapter_dir.mkdir()
        chapters = []
        records = []
        cur_values = []

        for index in range(1, chapter_count + 1):
            if mode == "quick":
                fact_year = target_year
            elif time_anchor == "relaxed":
                fact_year = target_year - 10
            else:
                fact_year = (target_year, target_year - 1, target_year - 3)[
                    (index - 1) % 3
                ]
            if fact_year == target_year:
                cur = "current"
            elif fact_year == target_year - 1:
                cur = "recent"
            else:
                cur = "dated"
            section_titles = [
                f"{vocabulary['section']} {section}" for section in range(1, section_count + 1)
            ]
            question = f"{vocabulary['question']} {index}?"
            chapters.append({
                "title": f"{vocabulary['chapter']} {index}",
                "description": vocabulary["judgment"],
                "sections": section_titles,
                "sub_questions": [{
                    "question": question,
                    "priority": "medium",
                    "search_keywords": [f"evidence {index} {target_year}"],
                    "counter_keywords": ["counter evidence"] if index == 1 else [],
                    "data_targets": ["metric", "context"],
                }],
            })
            fact = {
                "src": f"Source {index}", "yr": str(fact_year),
                "met": "Metric", "val": index, "u": "%",
                "ctx": "Published evidence",
                "url": f"https://source{index}.example.com/report",
                "title": f"Evidence {index}", "conf": "high",
                "data_type": "actual",
            }
            if mode != "quick":
                fact["cur"] = cur
                cur_values.append(cur)
            records.append({
                "q_index": index - 1, "priority": "medium", "question": question,
                "src": [f"Source {index}"], "facts": [fact],
                "controversies": [], "gaps": [],
            })

            lines = [f"> {vocabulary['judgment']}", ""]
            paragraph_number = 0
            for section_number, section_title in enumerate(section_titles, 1):
                lines.extend([f"### {index}.{section_number} {section_title}", ""])
                paragraph_number += 1
                citation = f" [{index}]" if paragraph_number == 1 else ""
                lines.extend([
                    f"{vocabulary['paragraph']} {paragraph_number}; {fact_year}.{citation}", "",
                ])
            while paragraph_number < min_paragraphs:
                paragraph_number += 1
                lines.extend([
                    f"{vocabulary['paragraph']} {paragraph_number}; {fact_year}.", "",
                ])
            if min_tables:
                lines.extend([
                    "| Metric | Value |", "|---|---|", f"| Evidence | {index} |", "",
                ])
            (chapter_dir / f"chapter-{index}.md").write_text(
                "\n".join(lines), encoding="utf-8"
            )

        outline = root / "outline.json"
        outline.write_text(json.dumps({
            "title": vocabulary["title"], "type": vocabulary["type"],
            "language": lang, "depth_mode": mode,
            "time_anchor": {"mode": time_anchor, "target_year": target_year},
            "source_suggestions": ["example.com", "example.org", "example.edu"],
            "chapters": chapters,
        }, ensure_ascii=False), encoding="utf-8")
        pool = root / "data-pool.json"
        pool.write_text(json.dumps(records, ensure_ascii=False), encoding="utf-8")
        manifest = root / "task2_manifest.json"
        manifest.write_text(json.dumps({
            "coverage": [
                {"q_index": index, "status": "adequate"}
                for index in range(chapter_count)
            ],
            "coverage_summary": "adequate", "data_limited": False,
            "unique_domains": chapter_count,
        }), encoding="utf-8")

        outline_result = check_outline(str(outline), mode=mode)
        self.assertTrue(outline_result["passed"], outline_result["issues"])
        pool_result = check_datapool(
            str(pool), mode, source_mode="online", strict=True,
            outline_path=str(outline),
        )
        self.assertTrue(pool_result["passed"], pool_result["issues"])
        chapter_result = validate_all_chapters(
            str(chapter_dir), outline_path=str(outline), mode=mode, lang=lang,
        )
        self.assertTrue(chapter_result["passed"], chapter_result["failed_chapters"])

        citation_map_path = root / "citation-map.json"
        citation_map = generate_citation_map(str(pool), str(citation_map_path))
        self.assertEqual(citation_map["count"], chapter_count)
        self.assertTrue(citation_map_path.is_file())
        output = root / "report.md"
        assembled = assemble_report(
            str(outline), str(chapter_dir), str(pool), mode, target_year,
            output_path=str(output), lang_override=lang,
        )
        self.assertTrue(assembled["passed"], assembled["issues"])

        first_conversion = convert_citations(str(output), str(pool), lang=lang)
        self.assertTrue(first_conversion["passed"], first_conversion["issues"])
        converted = output.read_bytes()
        second_conversion = convert_citations(str(output), str(pool), lang=lang)
        self.assertTrue(second_conversion["passed"], second_conversion["issues"])
        self.assertEqual(output.read_bytes(), converted)

        confidence_command = [
            sys.executable, str(TOOLS_DIR / "dr_tools.py"),
            "generate-confidence-section", "--datapool", str(pool),
            "--manifest", str(manifest), "--report", str(output),
            "--lang", lang,
        ]
        confidence = subprocess.run(
            confidence_command, check=False, capture_output=True, text=True
        )
        self.assertEqual(confidence.returncode, 0, confidence.stderr or confidence.stdout)
        with_confidence = output.read_bytes()
        confidence_again = subprocess.run(
            confidence_command, check=False, capture_output=True, text=True
        )
        self.assertEqual(
            confidence_again.returncode, 0,
            confidence_again.stderr or confidence_again.stdout,
        )
        self.assertEqual(output.read_bytes(), with_confidence)

        refreshed = refresh_metadata(str(output), str(pool), lang=lang)
        self.assertTrue(refreshed["passed"], refreshed["issues"])
        final_content = output.read_bytes()
        refreshed_again = refresh_metadata(str(output), str(pool), lang=lang)
        self.assertTrue(refreshed_again["passed"], refreshed_again["issues"])
        self.assertEqual(output.read_bytes(), final_content)
        qa = qa_report(
            str(output), mode=mode, target_year=target_year,
            lang=lang, time_anchor=time_anchor,
        )
        self.assertTrue(qa["passed"], qa["failures"])
        content = output.read_text(encoding="utf-8")
        config = LANG_CONFIG[lang]
        self.assertTrue(content.startswith(f"# {vocabulary['title']}\n"))
        metadata_position = content.index(config["metadata_label"])
        toc_position = content.index(config["toc_heading"])
        confidence_position = content.index(config["confidence_heading"])
        references_position = content.index(config["refs_prefix"])
        disclaimer_position = content.index(config["disclaimer_title"])
        self.assertLess(metadata_position, toc_position)
        self.assertLess(toc_position, confidence_position)
        self.assertLess(confidence_position, references_position)
        self.assertLess(references_position, disclaimer_position)
        return {"qa": qa, "cur_values": cur_values, "output": output}

    def test_missing_chapter_does_not_write_output(self):
        output = self.root / "missing.md"
        result = assemble_report(
            str(self.outline), str(self.chapters), str(self.pool),
            "quick", 2026, output_path=str(output), lang_override="en",
        )
        self.assertFalse(result["passed"])
        self.assertFalse(output.exists())

    def test_assembly_preserves_old_reports_and_protects_existing_output(self):
        self.write_chapter()
        old = self.root / "Test Report-20200101-000000.md"
        old.write_text("old", encoding="utf-8")
        output = self.root / "custom.md"
        first = assemble_report(
            str(self.outline), str(self.chapters), str(self.pool),
            "quick", 2026, output_path=str(output), lang_override="en",
        )
        second = assemble_report(
            str(self.outline), str(self.chapters), str(self.pool),
            "quick", 2026, output_path=str(output), lang_override="en",
        )
        self.assertTrue(first["passed"], first["issues"])
        self.assertFalse(second["passed"])
        self.assertTrue(old.exists())

    def test_language_mismatch_fails_before_writing(self):
        self.write_chapter()
        output = self.root / "mismatch.md"
        result = assemble_report(
            str(self.outline), str(self.chapters), str(self.pool),
            "quick", 2026, output_path=str(output), lang_override="zh",
        )
        self.assertFalse(result["passed"])
        self.assertFalse(output.exists())

    def test_citations_include_yearless_local_source_and_are_idempotent(self):
        self.write_chapter()
        citation_map = generate_citation_map(str(self.pool))
        self.assertEqual(citation_map["count"], 1)
        self.assertEqual(citation_map["entries"][0]["yr"], "")
        output = self.root / "report.md"
        assembled = assemble_report(
            str(self.outline), str(self.chapters), str(self.pool),
            "quick", 2026, output_path=str(output), lang_override="en",
        )
        self.assertTrue(assembled["passed"], assembled["issues"])
        first = convert_citations(str(output), str(self.pool), lang="en")
        second = convert_citations(str(output), str(self.pool), lang="en")
        self.assertTrue(first["passed"], first["issues"])
        self.assertTrue(second["passed"], second["issues"])
        self.assertTrue(check_citations(str(output), "en")["passed"])
        content = output.read_text(encoding="utf-8")
        self.assertEqual(content.count('<a id="ref1"></a>'), 1)

    def test_refresh_metadata_matches_final_report(self):
        self.write_chapter()
        output = self.root / "report.md"
        assembled = assemble_report(
            str(self.outline), str(self.chapters), str(self.pool),
            "quick", 2026, output_path=str(output), lang_override="en",
        )
        self.assertTrue(assembled["passed"], assembled["issues"])
        convert_citations(str(output), str(self.pool), lang="en")
        with output.open("a", encoding="utf-8") as f:
            f.write("\nAdditional final text.\n")
        result = refresh_metadata(str(output), str(self.pool), lang="en")
        self.assertTrue(result["passed"], result["issues"])
        content = output.read_text(encoding="utf-8")
        match = re.search(r"Word Count: (\d+)", content)
        self.assertIsNotNone(match)
        self.assertEqual(int(match.group(1)), word_count(str(output)))

    def test_cleanup_requires_marker_and_valid_temp_run_name(self):
        with tempfile.TemporaryDirectory() as parent:
            run = Path(parent) / "codex-deep-research-test"
            run.mkdir()
            denied = cleanup_run(str(run))
            self.assertFalse(denied["passed"])
            (run / ".deep-research-run.json").write_text(
                json.dumps({"kind": "deep-research-run"}), encoding="utf-8"
            )
            allowed = cleanup_run(str(run))
            self.assertTrue(allowed["passed"], allowed["issues"])
            self.assertFalse(run.exists())

    def test_confidence_section_is_native_for_all_supported_languages(self):
        manifest = self.root / "manifest.json"
        manifest.write_text(json.dumps({
            "coverage": [{"q_index": 0, "status": "adequate"}],
            "coverage_summary": "adequate",
            "data_limited": False,
            "unique_domains": 1,
        }), encoding="utf-8")
        required_labels = {
            "source_type", "authoritative", "industry", "media",
            "data_type", "actual", "estimate", "forecast", "distribution",
            "high", "medium", "low", "coverage", "adequate", "insufficient",
            "limitations", "limited", "none", "discrepancies",
            "discrepancy_note", "rating", "no_data", "inference_note",
        }
        self.assertEqual(len(LANG_CONFIG), 19)
        for lang, config in LANG_CONFIG.items():
            with self.subTest(lang=lang):
                labels = config["confidence_labels"]
                self.assertEqual(set(labels), required_labels)
                result = generate_confidence_section(
                    str(self.pool), str(manifest), lang=lang
                )
                self.assertTrue(result["passed"], result["issues"])
                self.assertIn(config["confidence_heading"], result["section"])
                for key in ("source_type", "data_type", "distribution",
                            "coverage", "limitations", "rating"):
                    self.assertIn(labels[key], result["section"])

    def test_detect_engine_uses_configured_endpoint_and_short_timeout(self):
        response = MagicMock()
        response.read.return_value = b'{"results": []}'
        response.__enter__.return_value = response
        with patch.dict(os.environ, {
            "SEARXNG_URL": "https://search.example/api?existing=1",
            "SEARXNG_DETECT_TIMEOUT": "2",
        }), patch("urllib.request.urlopen", return_value=response) as urlopen:
            result = detect_engine()
        self.assertTrue(result["available"])
        request = urlopen.call_args.args[0]
        self.assertIn("existing=1&q=test&format=json", request.full_url)
        self.assertEqual(urlopen.call_args.kwargs["timeout"], 2.0)

    def test_multilingual_modes_complete_full_temporary_report_chain(self):
        cases = [
            ("zh-quick-latest", "zh", "quick", "latest", 2026),
            ("en-standard-relaxed", "en", "standard", "relaxed", 2026),
            ("ar-quick-latest", "ar", "quick", "latest", 2026),
            ("en-deep-user", "en", "deep", "user_specified", 2024),
        ]
        for suffix, lang, mode, time_anchor, target_year in cases:
            with self.subTest(lang=lang, mode=mode, time_anchor=time_anchor):
                result = self.run_report_e2e(
                    suffix, lang, mode, time_anchor, target_year
                )
                year_check = result["qa"]["checks"]["year_density"]
                if time_anchor == "relaxed":
                    self.assertTrue(year_check["skipped"])
                else:
                    self.assertFalse(year_check.get("skipped", False))
                if mode == "standard":
                    self.assertEqual(set(result["cur_values"]), {"dated"})
                elif mode == "deep":
                    self.assertEqual(
                        set(result["cur_values"]), {"current", "recent", "dated"}
                    )

    def test_arabic_quick_report_completes_assembly_and_qa_chain(self):
        outline = self.root / "outline-ar.json"
        chapters = []
        records = []
        for index in range(1, 6):
            question = f"السؤال {index}"
            chapters.append({
                "title": f"الفصل {index}",
                "description": "حكم تحليلي",
                "sections": ["الأدلة"],
                "sub_questions": [{
                    "question": question,
                    "priority": "medium",
                    "search_keywords": [f"بيانات {index} 2026"],
                    "counter_keywords": ["رأي مخالف"] if index == 1 else [],
                    "data_targets": ["المؤشر", "السياق"],
                }],
            })
            records.append({
                "q_index": index - 1,
                "priority": "medium",
                "question": question,
                "src": [f"Source {index}"],
                "facts": [{
                    "src": f"Source {index}", "yr": "2026",
                    "met": "Metric", "val": index, "u": "%",
                    "ctx": "Published evidence",
                    "url": f"https://example{index}.com/report",
                    "title": f"Evidence {index}", "conf": "high",
                    "data_type": "actual",
                }],
                "controversies": [], "gaps": [],
            })
        outline.write_text(json.dumps({
            "title": "تقرير تجريبي", "type": "بحث تقني",
            "language": "ar", "depth_mode": "quick",
            "time_anchor": {"mode": "latest", "target_year": 2026},
            "source_suggestions": ["example.com", "example.org", "example.edu"],
            "chapters": chapters,
        }, ensure_ascii=False), encoding="utf-8")
        pool = self.root / "pool-ar.json"
        pool.write_text(json.dumps(records, ensure_ascii=False), encoding="utf-8")
        chapter_dir = self.root / "chapters-ar"
        chapter_dir.mkdir()
        for index in range(1, 6):
            (chapter_dir / f"chapter-{index}.md").write_text(
                "> الخلاصة الأساسية\n\n"
                f"### {index}.1 الأدلة\n\n"
                f"الفقرة الأولى تعرض بيانات عام 2026 [{index}].\n\n"
                "الفقرة الثانية تشرح العلاقة السببية.\n\n"
                "الفقرة الثالثة تقارن التفسيرات.\n\n"
                "الفقرة الرابعة تقدم الحكم النهائي.\n",
                encoding="utf-8",
            )
        manifest = self.root / "manifest-ar.json"
        manifest.write_text(json.dumps({
            "coverage": [
                {"q_index": index, "status": "adequate"} for index in range(5)
            ],
            "coverage_summary": "adequate", "data_limited": False,
            "unique_domains": 5,
        }), encoding="utf-8")
        output = self.root / "arabic-report.md"

        assembled = assemble_report(
            str(outline), str(chapter_dir), str(pool), "quick", 2026,
            output_path=str(output), lang_override="ar",
        )
        self.assertTrue(assembled["passed"], assembled["issues"])
        confidence = subprocess.run([
            sys.executable, str(TOOLS_DIR / "dr_tools.py"),
            "generate-confidence-section", "--datapool", str(pool),
            "--manifest", str(manifest), "--report", str(output),
            "--lang", "ar",
        ], check=False, capture_output=True, text=True)
        self.assertEqual(confidence.returncode, 0, confidence.stderr or confidence.stdout)
        self.assertTrue(convert_citations(
            str(output), str(pool), lang="ar"
        )["passed"])
        self.assertTrue(refresh_metadata(
            str(output), str(pool), lang="ar"
        )["passed"])

        qa = qa_report(
            str(output), mode="quick", target_year=2026,
            lang="ar", time_anchor="latest",
        )

        self.assertTrue(qa["passed"], qa["failures"])


if __name__ == "__main__":
    unittest.main()
