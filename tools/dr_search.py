#!/usr/bin/env python3
import concurrent.futures
import datetime
import json
import os
import re
import urllib.parse
import urllib.request
from urllib.parse import urlsplit, urlunsplit

from tld import get_fld

from dr_check import load_profile


DEFAULT_SEARXNG_URL = "https://search.h33.top/search"


def _read_json(path: str):
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def _write_json(path: str, value) -> None:
    parent = os.path.dirname(os.path.abspath(path))
    os.makedirs(parent, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, path)


def _normalize_url(url: str) -> str:
    try:
        parts = urlsplit(str(url).strip())
        port = parts.port
    except ValueError:
        return ""
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        return ""
    host = (parts.hostname or "").lower()
    if not host:
        return ""
    default_port = (parts.scheme == "http" and port == 80) or (
        parts.scheme == "https" and port == 443
    )
    normalized_host = f"[{host}]" if ":" in host else host
    netloc = normalized_host if not port or default_port else f"{normalized_host}:{port}"
    return urlunsplit((parts.scheme.lower(), netloc, parts.path or "/", parts.query, ""))


def _site_domain(value: str) -> str:
    text = str(value or "").strip().lower().rstrip(".")
    if not text:
        return ""
    domain = get_fld(text, fix_protocol=True, fail_silently=True)
    if domain:
        return domain.lower().rstrip(".")
    return (urlsplit(text if "://" in text else f"//{text}").hostname or "").lower()


def _flatten_questions(outline: dict) -> list[dict]:
    flattened = []
    q_index = 0
    target_year = outline.get("time_anchor", {}).get("target_year", "")
    suggestions = [
        domain for domain in (
            _site_domain(value) for value in (outline.get("source_suggestions") or [])
        ) if domain
    ]
    for chapter_index, chapter in enumerate(outline.get("chapters") or [], 1):
        for question in chapter.get("sub_questions") or []:
            flattened.append({
                "q_index": q_index,
                "chapter": chapter_index,
                "question": str(question.get("question", "")).strip(),
                "priority": question.get("priority", "medium"),
                "search_keywords": question.get("search_keywords") or [],
                "counter_keywords": question.get("counter_keywords") or [],
                "target_year": target_year,
                "source_suggestions": suggestions,
            })
            q_index += 1
    return flattened


def _substitute_year(value: str, year) -> str:
    return str(value).replace("{target_year}", str(year)).replace(
        "{CURRENT_YEAR}", str(year)
    )


def build_search_plan(outline: dict) -> list[dict]:
    plan = []
    for item in _flatten_questions(outline):
        keywords = [str(value).strip() for value in item["search_keywords"] if str(value).strip()]
        main_query = keywords[0] if keywords else item["question"]
        main_query = _substitute_year(main_query, item["target_year"])
        plan.append({**item, "query_type": "main", "query": main_query})
        if item["priority"] == "high":
            counters = [
                str(value).strip() for value in item["counter_keywords"] if str(value).strip()
            ]
            if counters:
                plan.append({
                    **item,
                    "query_type": "counter",
                    "query": _substitute_year(counters[0], item["target_year"]),
                })
            else:
                domains = [str(value).strip() for value in item["source_suggestions"] if str(value).strip()]
                if not domains:
                    continue
                plan.append({
                    **item,
                    "query_type": "site",
                    "query": f"site:{domains[0]} {main_query}",
                })
    return plan


def build_supplement_plan(outline: dict, questions: dict[int, dict],
                          source_domains: list[str] = None) -> list[dict]:
    """Build one extra query only for questions with inadequate first-pass coverage."""
    plan = []
    source_domains = source_domains or []
    for item in _flatten_questions(outline):
        state = questions.get(item["q_index"], {})
        if len(state.get("results", [])) >= 3:
            continue
        existing = {query.get("query") for query in state.get("queries", [])}
        keywords = [
            _substitute_year(str(value).strip(), item["target_year"])
            for value in item["search_keywords"] if str(value).strip()
        ]
        domains = [
            str(value).strip() for value in item["source_suggestions"] if str(value).strip()
        ]
        main_query = keywords[0] if keywords else _substitute_year(
            item["question"], item["target_year"]
        )
        candidates = [("fallback", query) for query in keywords[1:]]
        candidates.extend(
            ("source_fallback", f"site:{domain} {main_query}")
            for domain in source_domains
        )
        candidates.extend(
            ("fallback", f"site:{domain} {main_query}") for domain in domains
        )
        candidate = next(
            ((query_type, query) for query_type, query in candidates
             if query not in existing),
            None,
        )
        if candidate:
            query_type, query = candidate
            plan.append({**item, "query_type": query_type, "query": query})
    return plan


def _search_query(endpoint: str, query: str, lang: str, max_results: int,
                  timeout: int) -> list[dict]:
    endpoint_parts = urlsplit(endpoint)
    params = urllib.parse.parse_qsl(endpoint_parts.query, keep_blank_values=True)
    params.extend([("q", query), ("format", "json"), ("language", lang)])
    request_url = urlunsplit((
        endpoint_parts.scheme, endpoint_parts.netloc, endpoint_parts.path,
        urllib.parse.urlencode(params), "",
    ))
    request = urllib.request.Request(
        request_url,
        headers={"User-Agent": "deep-research/5.2.0-codex.1 (+structured-search)"},
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    results = []
    for raw in payload.get("results", [])[:max_results]:
        url = _normalize_url(raw.get("url", ""))
        if not url:
            continue
        results.append({
            "url": url,
            "title": str(raw.get("title", "")).strip(),
            "snippet": re.sub(r"\s+", " ", str(raw.get("content", ""))).strip(),
            "engine": str(raw.get("engine", "searxng")),
            "published_date": str(
                raw.get("publishedDate") or raw.get("published_date") or ""
            ),
        })
    return results


def _known_domains(sources_path: str) -> dict[str, int]:
    if not sources_path or not os.path.exists(sources_path):
        return {}
    data = _read_json(sources_path)
    domains = {}
    for source in data.get("sources", []):
        priority = int(source.get("priority", 3))
        for value in (source.get("health_url"), source.get("url_template")):
            domain = _site_domain(value)
            if domain:
                domains[domain] = min(priority, domains.get(domain, priority))
    return domains


def _source_fallback_domains(sources_path: str, lang: str) -> list[str]:
    if not sources_path or not os.path.exists(sources_path):
        return []
    data = _read_json(sources_path)
    ranked = []
    seen = set()
    for order, source in enumerate(data.get("sources", [])):
        languages = source.get("lang") or []
        if languages and lang not in languages:
            continue
        domain = _site_domain(source.get("url_template") or source.get("health_url"))
        if not domain or domain in seen:
            continue
        seen.add(domain)
        ranked.append((int(source.get("priority", 3)), order, domain))
    return [domain for _, _, domain in sorted(ranked)]


def _rank_result(result: dict, suggestions: list[str], known_domains: dict[str, int]) -> tuple:
    host = (urlsplit(result["url"]).hostname or "").lower()
    domain = _site_domain(host)
    suggestion_rank = 0 if domain and domain in suggestions else 1
    source_rank = known_domains.get(domain, 4)
    authority_rank = 0 if host.endswith((".gov", ".edu", ".org")) else 1
    years = [int(value) for value in re.findall(r"20\d{2}", result.get("published_date", ""))]
    date_rank = -max(years) if years else 0
    return suggestion_rank, source_rank, authority_rank, date_rank


def _execute_plan(plan: list[dict], endpoint: str, lang: str, max_results: int,
                  timeout: int, concurrency: int) -> tuple[list[list[dict]], list[dict]]:
    raw_results = [None] * len(plan)
    errors = []

    def execute(index_and_item):
        index, item = index_and_item
        try:
            result = _search_query(endpoint, item["query"], lang, max_results, timeout)
            return index, result, ""
        except Exception as exc:
            return index, [], f"{type(exc).__name__}: {exc}"

    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, concurrency)) as executor:
        for index, result, error in executor.map(execute, enumerate(plan)):
            raw_results[index] = result
            if error:
                errors.append({
                    "query": plan[index]["query"],
                    "type": plan[index]["query_type"],
                    "error": error,
                })
    return raw_results, errors


def _merge_results(questions: dict[int, dict], plan: list[dict],
                   raw_results: list[list[dict]]) -> None:
    for item, results in zip(plan, raw_results):
        target = questions[item["q_index"]]
        target["queries"].append({
            "type": item["query_type"], "query": item["query"],
            "result_count": len(results or []),
        })
        for result in results or []:
            candidate = dict(result)
            candidate["query_type"] = item["query_type"]
            target["results"].append(candidate)


def _rank_questions(questions: dict[int, dict], flattened: list[dict],
                    known_domains: dict[str, int], max_results: int) -> int:
    question_meta = {item["q_index"]: item for item in flattened}
    total_urls = 0
    for q_index, item in questions.items():
        seen = set()
        deduped = []
        suggestions = question_meta[q_index]["source_suggestions"]
        for result in sorted(
            item["results"], key=lambda value: _rank_result(value, suggestions, known_domains)
        ):
            if result["url"] in seen:
                continue
            seen.add(result["url"])
            deduped.append(result)
        item["results"] = deduped[:max_results]
        item["status"] = "adequate" if len(item["results"]) >= 3 else "insufficient"
        total_urls += len(item["results"])
    return total_urls


def search_outline(outline_path: str, sources_path: str, output_path: str,
                   trace_path: str, mode: str = None, endpoint: str = None,
                   timeout: int = 10, concurrency: int = 6) -> dict:
    outline = _read_json(outline_path)
    depth_mode = mode or outline.get("depth_mode", "standard")
    profile = load_profile(depth_mode)
    max_results = profile.get("search_results_per_question", 8)
    endpoint = endpoint or os.environ.get("SEARXNG_URL", DEFAULT_SEARXNG_URL)
    lang = outline.get("language", "en")
    flattened = _flatten_questions(outline)
    plan = build_search_plan(outline)
    known_domains = _known_domains(sources_path)
    source_domains = _source_fallback_domains(sources_path, lang)
    questions = {item["q_index"]: {
        "q_index": item["q_index"],
        "question": item["question"],
        "priority": item["priority"],
        "queries": [],
        "results": [],
    } for item in flattened}
    raw_results, errors = _execute_plan(
        plan, endpoint, lang, max_results, timeout, concurrency
    )
    _merge_results(questions, plan, raw_results)
    _rank_questions(questions, flattened, known_domains, max_results)

    supplement_plan = build_supplement_plan(outline, questions, source_domains)
    supplement_results, supplement_errors = _execute_plan(
        supplement_plan, endpoint, lang, max_results, timeout, concurrency
    )
    errors.extend(supplement_errors)
    _merge_results(questions, supplement_plan, supplement_results)
    total_urls = _rank_questions(questions, flattened, known_domains, max_results)
    all_plan = plan + supplement_plan

    generated_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
    payload = {
        "version": 1,
        "engine": "searxng",
        "endpoint": endpoint,
        "generated_at": generated_at,
        "mode": depth_mode,
        "questions": list(questions.values()),
        "errors": errors,
    }
    trace = {
        "version": 1,
        "engine": "searxng",
        "available": len(all_plan) > len(errors),
        "queries_total": len(all_plan),
        "initial_queries": len(plan),
        "fallback_queries": len(supplement_plan),
        "source_fallback_queries": sum(
            1 for item in supplement_plan if item["query_type"] == "source_fallback"
        ),
        "queries_succeeded": len(all_plan) - len(errors),
        "queries_failed": len(errors),
        "result_urls": total_urls,
        "questions_total": len(questions),
        "questions_insufficient": sum(
            1 for item in questions.values() if item["status"] == "insufficient"
        ),
        "generated_at": generated_at,
    }
    _write_json(output_path, payload)
    _write_json(trace_path, trace)
    return {
        "passed": bool(plan) and trace["queries_succeeded"] > 0,
        "issues": [] if trace["queries_succeeded"] > 0 else ["All search queries failed"],
        "warnings": [item["error"] for item in errors],
        "output": output_path,
        "trace": trace_path,
        **trace,
    }


def build_fetch_queue(search_results_path: str, output_path: str,
                      mode: str) -> dict:
    data = _read_json(search_results_path)
    profile = load_profile(mode)
    per_question = profile.get("max_fetch_urls_per_question", 4)
    by_url = {}
    order = []
    for question in data.get("questions", []):
        for result in question.get("results", [])[:per_question]:
            url = result.get("url", "")
            if not url:
                continue
            if url not in by_url:
                by_url[url] = {
                    "url": url,
                    "title": result.get("title", ""),
                    "q_indices": [],
                    "priorities": [],
                    "status": "pending",
                }
                order.append(url)
            by_url[url]["q_indices"].append(question.get("q_index"))
            by_url[url]["priorities"].append(question.get("priority", "medium"))
    queue = {
        "version": 1,
        "mode": mode,
        "batch_size": 6,
        "browser_batch_size": 2,
        "items": [by_url[url] for url in order],
    }
    _write_json(output_path, queue)
    return {
        "passed": bool(order),
        "issues": [] if order else ["Search results produced no fetchable URLs"],
        "output": output_path,
        "url_count": len(order),
    }
