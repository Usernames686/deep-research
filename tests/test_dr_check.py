import json
import sys
import tempfile
import unittest
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS_DIR))

from dr_check import (  # noqa: E402
    check_datapool,
    check_headers,
    check_outline,
    validate_chapter,
)


class DataPoolValidationTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)

    def tearDown(self):
        self.tempdir.cleanup()

    def write_json(self, name, value):
        path = self.root / name
        path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        return path

    def base_fact(self, **overrides):
        fact = {
            "src": "Example Institute",
            "yr": "2026",
            "met": "Metric",
            "val": 1,
            "u": "%",
            "ctx": "Published result",
            "url": "https://example.com/report",
            "title": "Report",
            "conf": "high",
            "data_type": "actual",
        }
        fact.update(overrides)
        return fact

    def base_record(self, facts=None, gaps=None, **overrides):
        record = {
            "q_index": 0,
            "priority": "medium",
            "question": "Question",
            "src": ["example.com"],
            "facts": [self.base_fact()] if facts is None else facts,
            "controversies": [],
            "gaps": [] if gaps is None else gaps,
        }
        record.update(overrides)
        return record

    def test_empty_pool_fails(self):
        result = check_datapool(str(self.write_json("pool.json", [])), "quick")
        self.assertFalse(result["passed"])

    def test_gap_only_record_is_valid(self):
        record = self.base_record(facts=[], gaps=["No public data"])
        result = check_datapool(
            str(self.write_json("pool.json", [record])), "quick", strict=True
        )
        self.assertTrue(result["passed"], result["issues"])

    def test_source_specific_gap_is_valid_and_requires_url_and_reason(self):
        valid = self.base_record(facts=[], gaps=[{
            "url": "https://example.com/report", "reason": "No relevant fact",
        }])
        result = check_datapool(
            str(self.write_json("source-gap.json", [valid])), "quick", strict=True
        )
        self.assertTrue(result["passed"], result["issues"])

        invalid = self.base_record(facts=[], gaps=[{"url": "https://example.com/report"}])
        result = check_datapool(
            str(self.write_json("invalid-source-gap.json", [invalid])),
            "quick", strict=True,
        )
        self.assertFalse(result["passed"])
        self.assertTrue(any("missing 'reason'" in issue for issue in result["issues"]))

    def test_strict_quick_requires_confidence_and_data_type(self):
        fact = self.base_fact()
        del fact["conf"]
        del fact["data_type"]
        record = self.base_record(facts=[fact])
        result = check_datapool(
            str(self.write_json("pool.json", [record])), "quick", strict=True
        )
        self.assertFalse(result["passed"])
        self.assertTrue(any("conf" in issue for issue in result["issues"]))

    def test_legacy_missing_new_fields_only_warns(self):
        fact = self.base_fact()
        del fact["conf"]
        del fact["data_type"]
        record = {"question": "Q", "src": ["x"], "facts": [fact]}
        result = check_datapool(str(self.write_json("pool.json", [record])), "quick")
        self.assertTrue(result["passed"], result["issues"])
        self.assertTrue(result["warnings"])

    def test_invalid_enums_fail(self):
        fact = self.base_fact(conf="certain", data_type="guess")
        result = check_datapool(
            str(self.write_json("pool.json", [self.base_record(facts=[fact])])),
            "quick",
            strict=True,
        )
        self.assertFalse(result["passed"])
        self.assertGreaterEqual(len(result["issues"]), 2)

    def test_standard_mode_requires_valid_recency_classification(self):
        fact = self.base_fact(cur="current")
        result = check_datapool(
            str(self.write_json("standard.json", [self.base_record(facts=[fact])])),
            "standard", strict=True,
        )
        self.assertTrue(result["passed"], result["issues"])
        fact["cur"] = "fresh"
        invalid = check_datapool(
            str(self.write_json("invalid-standard.json", [
                self.base_record(facts=[fact])
            ])),
            "standard", strict=True,
        )
        self.assertFalse(invalid["passed"])

    def test_offline_fact_may_have_no_year(self):
        fact = self.base_fact(yr="", url="/tmp/source.pdf")
        result = check_datapool(
            str(self.write_json("pool.json", [self.base_record(facts=[fact])])),
            "quick",
            source_mode="offline",
            strict=True,
        )
        self.assertTrue(result["passed"], result["issues"])

    def test_mixed_mode_validates_web_and_local_facts_independently(self):
        local_fact = self.base_fact(yr="", url="/tmp/source.pdf")
        web_fact = self.base_fact(url="https://example.com/report")
        result = check_datapool(
            str(self.write_json("pool.json", [
                self.base_record(facts=[local_fact, web_fact])
            ])),
            "quick", source_mode="mixed", strict=True,
        )
        self.assertTrue(result["passed"], result["issues"])

        web_fact["yr"] = ""
        invalid = check_datapool(
            str(self.write_json("invalid-pool.json", [
                self.base_record(facts=[local_fact, web_fact])
            ])),
            "quick", source_mode="mixed", strict=True,
        )
        self.assertFalse(invalid["passed"])

    def test_high_priority_coverage_is_warning_not_error(self):
        record = self.base_record(priority="high")
        result = check_datapool(
            str(self.write_json("pool.json", [record])), "quick", strict=True
        )
        self.assertTrue(result["passed"], result["issues"])
        self.assertTrue(any("priority=high" in item for item in result["warnings"]))

    def test_strict_pool_requires_array_and_sequential_question_indices(self):
        record = self.base_record()
        object_result = check_datapool(
            str(self.write_json("object.json", record)), "quick", strict=True
        )
        self.assertFalse(object_result["passed"])

        records = [record, self.base_record(q_index=0, question="Second")]
        index_result = check_datapool(
            str(self.write_json("indices.json", records)), "quick", strict=True
        )
        self.assertFalse(index_result["passed"])
        self.assertTrue(any("sequential" in issue for issue in index_result["issues"]))

    def test_strict_pool_enforces_source_mode_and_profile_limits(self):
        offline_web = check_datapool(
            str(self.write_json("offline-web.json", [self.base_record()])),
            "quick", source_mode="offline", strict=True,
        )
        self.assertFalse(offline_web["passed"])
        self.assertTrue(any("absolute local path" in issue
                            for issue in offline_web["issues"]))

        facts = [
            self.base_fact(url=f"https://example.com/{index}")
            for index in range(6)
        ]
        over_limit = check_datapool(
            str(self.write_json("over-limit.json", [self.base_record(facts=facts)])),
            "quick", strict=True,
        )
        self.assertFalse(over_limit["passed"])
        self.assertTrue(any("facts exceed" in issue for issue in over_limit["issues"]))
        self.assertTrue(any("sources exceed" in issue for issue in over_limit["issues"]))

    def test_strict_pool_can_verify_outline_mapping(self):
        outline = self.write_json("outline.json", {
            "chapters": [{"sub_questions": [{
                "question": "Expected question", "priority": "high",
            }]}],
        })
        record = self.base_record(question="Different question", priority="medium")
        result = check_datapool(
            str(self.write_json("mapped.json", [record])), "quick", strict=True,
            outline_path=str(outline),
        )
        self.assertFalse(result["passed"])
        self.assertTrue(any("question does not match" in issue
                            for issue in result["issues"]))
        self.assertTrue(any("priority does not match" in issue
                            for issue in result["issues"]))


class OutlineAndChapterTests(unittest.TestCase):
    def test_english_confidence_heading_is_structural(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "chapter.md"
            path.write_text("## Confidence Assessment\n", encoding="utf-8")
            self.assertTrue(check_headers(str(path), "en")["passed"])

    def test_outline_uses_profile_limits(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "outline.json"
            chapters = []
            for index in range(5):
                chapters.append({
                    "title": f"Chapter {index}",
                    "description": "Judgment",
                    "sections": ["Part"],
                    "sub_questions": [{
                        "question": "Question",
                        "priority": "medium",
                        "search_keywords": ["question {target_year}"],
                        "data_targets": ["Metric A", "Metric B"],
                        "counter_keywords": ["counter"] if index == 0 else [],
                    }],
                })
            path.write_text(json.dumps({
                "title": "Title",
                "type": "Technical",
                "depth_mode": "quick",
                "language": "en",
                "time_anchor": {"mode": "latest", "target_year": 2026},
                "source_suggestions": ["example.com", "example.org", "example.edu"],
                "chapters": chapters,
            }), encoding="utf-8")
            result = check_outline(str(path))
            self.assertTrue(result["passed"], result["issues"])

    def test_outline_rejects_mode_mismatch_and_incomplete_search_contract(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "outline.json"
            chapters = [{
                "title": f"Chapter {index}", "description": "Judgment",
                "sections": ["Part"],
                "sub_questions": [{
                    "question": "Question", "priority": "high",
                    "search_keywords": [], "counter_keywords": [],
                    "data_targets": ["Only one"],
                }],
            } for index in range(5)]
            path.write_text(json.dumps({
                "title": "Title", "type": "Technical", "depth_mode": "quick",
                "language": "en",
                "time_anchor": {"mode": "latest", "target_year": 2026},
                "source_suggestions": ["https://example.com"],
                "chapters": chapters,
            }), encoding="utf-8")

            result = check_outline(str(path), mode="standard")

            self.assertFalse(result["passed"])
            self.assertTrue(any("does not match requested" in issue
                                for issue in result["issues"]))
            self.assertTrue(any("search_keywords" in issue
                                for issue in result["issues"]))
            self.assertTrue(any("data_targets" in issue
                                for issue in result["issues"]))
            self.assertTrue(any("counter_keywords" in issue
                                for issue in result["issues"]))

    def test_chapter_validation_checks_expected_titles_and_depth(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "chapter-1.md"
            path.write_text(
                "> Core judgment\n\n"
                "### 1.1 Part\n\n"
                "First paragraph.\n\nSecond paragraph.\n\n"
                "Third paragraph.\n\nFourth paragraph.\n",
                encoding="utf-8",
            )
            result = validate_chapter(
                str(path), ["Part"], mode="quick", lang="en", chapter_num=1
            )
            self.assertTrue(result["passed"], result)


if __name__ == "__main__":
    unittest.main()
