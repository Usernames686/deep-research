#!/usr/bin/env python3
import json
import os
from pathlib import Path
from urllib.parse import urlsplit

from dr_gen import citation_key


def _read_json(path: str):
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def _write_json(path: str, value) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, path)


def _flatten_questions(outline: dict) -> list[dict]:
    questions = []
    q_index = 0
    for chapter in outline.get("chapters") or []:
        for question in chapter.get("sub_questions") or []:
            questions.append({
                "q_index": q_index,
                "question": question.get("question", ""),
                "priority": question.get("priority", "medium"),
            })
            q_index += 1
    return questions


def _diagnose(facts: list, gaps: list, search_question: dict) -> tuple[str, str]:
    joined = " ".join(
        str(item.get("reason", "") if isinstance(item, dict) else item).lower()
        for item in gaps
    )
    if any(token in joined for token in ("not announced", "尚未公布", "未发布")):
        return "timing_gap", "The requested data has not been published yet."
    if not search_question or not search_question.get("results"):
        return "engine_coverage_gap", "No usable search results were returned."
    if not facts:
        return "fetch_failure", "Search found candidates but no verifiable facts were extracted."
    return "topic_too_niche", "Public evidence remains too limited for the requested coverage."


def build_task2_manifest(outline_path: str, datapool_path: str, output_path: str,
                         search_results_path: str = None,
                         fetch_status_path: str = None,
                         cautions_path: str = None,
                         source_mode: str = "online") -> dict:
    outline = _read_json(outline_path)
    pool = _read_json(datapool_path)
    records = pool if isinstance(pool, list) else [pool]
    search = _read_json(search_results_path) if search_results_path and os.path.exists(
        search_results_path
    ) else {"questions": [], "engine": "none"}
    fetch = _read_json(fetch_status_path) if fetch_status_path and os.path.exists(
        fetch_status_path
    ) else {"items": []}
    search_by_q = {
        item.get("q_index"): item for item in search.get("questions", [])
    }
    records_by_q = {
        item.get("q_index", index): item for index, item in enumerate(records)
        if isinstance(item, dict)
    }
    target_year = outline.get("time_anchor", {}).get("target_year")
    anchor_mode = outline.get("time_anchor", {}).get("mode", "latest")
    coverage = []
    warnings = []
    for question in _flatten_questions(outline):
        record = records_by_q.get(question["q_index"], {})
        facts = record.get("facts") or []
        gaps = record.get("gaps") or []
        years = [str(fact.get("yr", "")) for fact in facts]
        recent = sum(
            1 for value in years
            if str(target_year) == value or str(int(target_year) - 1) == value
        ) if isinstance(target_year, int) else 0
        distinct_sources = {citation_key(fact) for fact in facts}
        required = 2 if question["priority"] == "high" else 1
        sufficient_facts = len(facts) >= required and len(distinct_sources) >= required
        local_only = bool(facts) and all(
            urlsplit(str(fact.get("url", ""))).scheme not in {"http", "https"}
            for fact in facts
        )
        current_enough = (
            source_mode == "offline" or anchor_mode == "relaxed" or recent > 0
            or (source_mode == "mixed" and local_only)
        )
        status = "adequate" if sufficient_facts and current_enough else "insufficient"
        item = {
            "q_index": question["q_index"],
            "status": status,
            "facts": len(facts),
            "recent": recent,
            "data_types": sorted({
                str(fact.get("data_type", "")) for fact in facts if fact.get("data_type")
            }),
            "gaps": gaps,
        }
        if status == "insufficient":
            diagnosis, actionable = _diagnose(
                facts, gaps, search_by_q.get(question["q_index"], {})
            )
            item["diagnosis"] = diagnosis
            item["actionable"] = actionable
            warnings.append(f"q_index {question['q_index']}: {diagnosis}")
        coverage.append(item)

    insufficient_count = sum(1 for item in coverage if item["status"] == "insufficient")
    total_questions = len(coverage)
    data_limited = bool(total_questions and insufficient_count * 3 >= total_questions)
    coverage_summary = (
        "adequate" if insufficient_count == 0
        else "insufficient" if data_limited
        else "partial"
    )

    facts = [fact for record in records for fact in (record.get("facts") or [])]
    source_keys = {citation_key(fact) for fact in facts}
    domains = set()
    for fact in facts:
        url = str(fact.get("url", ""))
        host = urlsplit(url).hostname
        if host:
            domains.add(host.lower())
        elif source_mode in {"offline", "mixed"} and url:
            domains.add(str(Path(url).expanduser().resolve()))
    fetch_items = fetch.get("items", []) if isinstance(fetch, dict) else []
    methods = {item.get("method") for item in fetch_items if item.get("success")}
    if source_mode == "offline":
        fetch_method = "local_files"
        engines = []
    else:
        fallback_count = sum(
            1 for item in fetch_items
            if item.get("success") and item.get("method") in {"stealthy", "dynamic"}
        )
        if methods:
            fetch_method = "Scrapling" + (
                f" ({fallback_count} browser fallbacks)" if fallback_count else ""
            )
        elif fetch_items:
            fetch_method = "failed"
        else:
            fetch_method = "not_recorded"
        search_engine = search.get("engine")
        engines = [search_engine] if search_engine and search_engine != "none" else []
        if source_mode == "mixed":
            fetch_method += " + local_files"

    manifest = {
        "task": 2,
        "version": 2,
        "source_mode": source_mode,
        "source_count": len(source_keys),
        "fact_count": len(facts),
        "unique_domains": len(domains),
        "search_engine": "+".join(engines) if engines else source_mode,
        "fetch_method": fetch_method,
        "engines": engines,
        "free_fallback": any(item.get("type") == "fallback"
                             for question in search.get("questions", [])
                             for item in question.get("queries", [])),
        "english_fallback": any(item.get("type") == "english_fallback"
                                 for question in search.get("questions", [])
                                 for item in question.get("queries", [])),
        "data_limited": data_limited,
        "data_pool_path": datapool_path,
        "cautions_path": cautions_path or "",
        "coverage": coverage,
        "coverage_summary": coverage_summary,
        "insufficient_count": insufficient_count,
        "total_sub_questions": total_questions,
        "search_layer_trace": {
            "structured_searxng": {
                "used": bool(engines),
                "queries": sum(len(item.get("queries", []))
                               for item in search.get("questions", [])),
                "urls_contributed": sum(len(item.get("results", []))
                                        for item in search.get("questions", [])),
            },
            "fetch": {
                "attempted": len(fetch_items),
                "succeeded": sum(1 for item in fetch_items if item.get("success")),
                "methods": sorted(value for value in methods if value),
            },
        },
    }
    _write_json(output_path, manifest)
    return {
        "passed": True,
        "issues": [],
        "warnings": warnings,
        "output": output_path,
        "source_count": len(source_keys),
        "fact_count": len(facts),
        "coverage_summary": coverage_summary,
        "data_limited": data_limited,
    }


def check_manifest(path: str) -> dict:
    try:
        data = _read_json(path)
    except Exception as exc:
        return {"passed": False, "issues": [f"Failed to read manifest: {exc}"]}
    issues = []
    required = {
        "task": int, "version": int, "source_mode": str,
        "source_count": int, "fact_count": int,
        "unique_domains": int, "fetch_method": str, "engines": list,
        "free_fallback": bool, "english_fallback": bool,
        "data_limited": bool, "coverage": list,
        "coverage_summary": str, "insufficient_count": int,
        "total_sub_questions": int,
    }
    for field, expected_type in required.items():
        if field not in data:
            issues.append(f"Missing manifest field '{field}'")
        elif not isinstance(data[field], expected_type):
            issues.append(f"Manifest field '{field}' must be {expected_type.__name__}")
    if data.get("coverage_summary") not in {"adequate", "partial", "insufficient"}:
        issues.append("Invalid coverage_summary")
    if data.get("task") != 2:
        issues.append("Manifest task must be 2")
    if data.get("version") != 2:
        issues.append("Manifest version must be 2")
    if data.get("source_mode") not in {"online", "offline", "mixed"}:
        issues.append("Invalid source_mode")
    coverage = data.get("coverage")
    if isinstance(coverage, list):
        if data.get("total_sub_questions") != len(coverage):
            issues.append("total_sub_questions does not match coverage length")
        for index, item in enumerate(coverage):
            if not isinstance(item, dict):
                issues.append(f"coverage[{index}] must be an object")
                continue
            if item.get("status") not in {"adequate", "insufficient"}:
                issues.append(f"coverage[{index}] has invalid status")
    return {"passed": not issues, "issues": issues}
