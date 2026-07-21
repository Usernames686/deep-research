#!/usr/bin/env python3
import asyncio
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path


STANDARD_BATCH_SIZE = 6
BROWSER_BATCH_SIZE = 2


def _read_json(path: str):
    with open(path, "r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def _write_json(path: str, value) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    temporary = path + ".tmp"
    with open(temporary, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    os.replace(temporary, path)


def _fingerprint(items: list[dict]) -> str:
    identity = [{
        "url": str(item.get("url", "")).strip(),
        "q_indices": item.get("q_indices", []),
        "priorities": item.get("priorities", []),
    } for item in items]
    payload = json.dumps(
        identity, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _status_summary(status: dict) -> dict:
    items = status.get("items", [])
    counts = {
        state: sum(1 for item in items if item.get("status") == state)
        for state in ("pending", "success", "failed")
    }
    unprocessed = sum(
        1 for item in items
        if item.get("status") == "success" and not item.get("processed", False)
    )
    return {
        "total": len(items), **counts, "unprocessed": unprocessed,
        "fetch_complete": counts["pending"] == 0,
        "complete": counts["pending"] == 0 and unprocessed == 0,
    }


def _attempt_class(method: str) -> str:
    return "browser" if method in {"dynamic", "stealthy"} else method


def _already_attempted(item: dict, method: str) -> bool:
    requested = _attempt_class(method)
    return any(
        _attempt_class(str(attempt.get("method", ""))) == requested
        for attempt in item.get("attempts", [])
    )


def init_fetch_run(queue_path: str, output_dir: str, status_path: str) -> dict:
    queue = _read_json(queue_path)
    queue_items = queue.get("items") or []
    urls = [str(item.get("url", "")).strip() for item in queue_items]
    if not urls or any(not url for url in urls):
        return {"passed": False, "issues": ["Fetch queue is empty or contains invalid URLs"]}

    fingerprint = _fingerprint(queue_items)
    output = Path(output_dir).expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    if os.path.exists(status_path):
        status = _read_json(status_path)
        if status.get("queue_fingerprint") != fingerprint:
            return {"passed": False, "issues": [
                "Existing fetch status belongs to a different queue"
            ]}
        return {
            "passed": True, "issues": [], "resumed": True,
            "status": status_path, **_status_summary(status),
        }

    status = {
        "version": 1,
        "queue_path": str(Path(queue_path).expanduser().resolve()),
        "queue_fingerprint": fingerprint,
        "output_dir": str(output),
        "items": [],
    }
    for index, item in enumerate(queue_items, 1):
        status["items"].append({
            "index": index,
            "url": urls[index - 1],
            "title": item.get("title", ""),
            "q_indices": item.get("q_indices", []),
            "priorities": item.get("priorities", []),
            "status": "pending",
            "attempts": [],
            "method": "",
            "output_path": "",
            "content_length": 0,
            "original_content_length": 0,
            "truncated": False,
            "error": "",
            "processed": False,
            "content_released": False,
            "datapool_digest": "",
        })
    _write_json(status_path, status)
    return {
        "passed": True, "issues": [], "resumed": False,
        "status": status_path, **_status_summary(status),
    }


def _ingest_payload(status: dict, payload: dict, method: str) -> dict:
    results = payload.get("results")
    if not isinstance(results, list):
        return {"passed": False, "issues": ["Fetch batch must contain a results array"]}
    by_url = {item["url"]: item for item in status.get("items", [])}
    output_dir = Path(status["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)
    warnings = []
    matched = 0
    ingested = 0
    for result in results:
        url = str(result.get("url", ""))
        item = by_url.get(url)
        if item is None:
            warnings.append(f"Result URL is not present in the fetch queue: {url}")
            continue
        matched += 1
        if _already_attempted(item, method):
            warnings.append(f"Duplicate {method} result ignored for URL: {url}")
            continue
        ingested += 1
        success = bool(result.get("success")) and bool(str(result.get("content", "")).strip())
        error = str(result.get("error", ""))
        if result.get("success") and not success and not error:
            error = "Fetcher returned empty content"
        item["attempts"].append({
            "method": method,
            "success": success,
            "error": error,
        })
        if success:
            target = output_dir / f"{item['index']:04d}.md"
            temporary = target.with_suffix(".md.tmp")
            content = str(result.get("content", ""))
            temporary.write_text(content, encoding="utf-8", newline="\n")
            os.replace(temporary, target)
            item.update({
                "status": "success",
                "method": method,
                "output_path": str(target),
                "content_length": len(content),
                "original_content_length": int(
                    result.get("original_content_length", len(content))
                ),
                "truncated": bool(result.get("truncated")),
                "error": "",
                "processed": False,
                "content_released": False,
                "datapool_digest": "",
            })
        else:
            item.update(status="failed", method=method, error=error or "Fetch failed")
    if not matched:
        return {"passed": False, "issues": ["Fetch batch matched no queued URLs"],
                "warnings": warnings}
    return {"passed": True, "issues": [], "warnings": warnings,
            "ingested": ingested}


def ingest_fetch_batch(status_path: str, batch_path: str, method: str) -> dict:
    status = _read_json(status_path)
    payload = _read_json(batch_path)
    result = _ingest_payload(status, payload, method)
    if not result["passed"]:
        return result
    _write_json(status_path, status)
    return {**result, "status": status_path, **_status_summary(status)}


def fetch_progress(status_path: str, state: str = "unfinished", limit: int = 0) -> dict:
    status = _read_json(status_path)
    if state not in {"pending", "failed", "success", "unfinished", "unprocessed"}:
        return {"passed": False, "issues": [f"Invalid fetch state: {state}"]}
    items = status.get("items", [])
    if state == "unfinished":
        selected = [item for item in items if item.get("status") != "success"]
    elif state == "unprocessed":
        selected = [
            item for item in items
            if item.get("status") == "success" and not item.get("processed", False)
        ]
    else:
        selected = [item for item in items if item.get("status") == state]
    if limit > 0:
        selected = selected[:limit]
    compact = [{
        "index": item.get("index"),
        "url": item.get("url"),
        "status": item.get("status"),
        "attempts": len(item.get("attempts", [])),
        "error": item.get("error", ""),
        "output_path": item.get("output_path", ""),
        "q_indices": item.get("q_indices", []),
    } for item in selected]
    return {
        "passed": True, "issues": [], "state": state,
        "selected": compact, **_status_summary(status),
    }


def _has_source_gap(record: dict, url: str) -> bool:
    return any(
        isinstance(gap, dict)
        and str(gap.get("url", "")).strip() == url
        and bool(str(gap.get("reason", "")).strip())
        for gap in (record.get("gaps") or [])
    )


def _rollback_release_moves(moved: list[tuple[Path, Path, bytes]]) -> list[str]:
    issues = []
    for original, archived, content in reversed(moved):
        try:
            if archived.exists():
                os.replace(archived, original)
            elif not original.exists():
                temporary = original.with_name(original.name + ".restore.tmp")
                temporary.write_bytes(content)
                os.replace(temporary, original)
        except OSError as exc:
            issues.append(f"Failed to restore {original}: {exc}")
    return issues


def mark_fetch_processed(status_path: str, datapool_path: str,
                         indices: list[int], release: bool = False) -> dict:
    status = _read_json(status_path)
    original_status = copy.deepcopy(status)
    pool = _read_json(datapool_path)
    if not isinstance(pool, list):
        return {"passed": False, "issues": ["Incremental data pool must be an array"]}
    records = {
        record.get("q_index", index): record
        for index, record in enumerate(pool) if isinstance(record, dict)
    }
    by_index = {item.get("index"): item for item in status.get("items", [])}
    issues = []
    selected = []
    for index in sorted(set(indices)):
        item = by_index.get(index)
        if item is None:
            issues.append(f"Unknown fetch item index: {index}")
            continue
        if item.get("status") != "success":
            issues.append(f"Fetch item {index} is not successful")
            continue
        q_indices = item.get("q_indices", [])
        if not q_indices:
            issues.append(f"Fetch item {index} has no owning q_index")
        for q_index in q_indices:
            record = records.get(q_index)
            if record is None:
                issues.append(f"Fetch item {index}: data pool has no q_index {q_index}")
                continue
            has_fact = any(
                str(fact.get("url", "")) == item.get("url")
                for fact in (record.get("facts") or []) if isinstance(fact, dict)
            )
            has_gap = _has_source_gap(record, item.get("url", ""))
            if not has_fact and not has_gap:
                issues.append(
                    f"Fetch item {index}: q_index {q_index} has neither a matching fact "
                    "nor a source-specific gap"
                )
            for fact in (record.get("facts") or []):
                if not isinstance(fact, dict) or str(fact.get("url", "")) != item.get("url"):
                    continue
                required = (
                    "src", "yr", "met", "val", "u", "ctx", "url", "title",
                    "conf", "data_type",
                )
                missing = [field for field in required if field not in fact]
                if missing:
                    issues.append(
                        f"Fetch item {index}: matching fact missing {', '.join(missing)}"
                    )
                if fact.get("conf") not in {"high", "medium", "low"}:
                    issues.append(f"Fetch item {index}: matching fact has invalid conf")
                if fact.get("data_type") not in {"actual", "estimate", "forecast"}:
                    issues.append(f"Fetch item {index}: matching fact has invalid data_type")
        selected.append(item)
    release_moves = []
    output_root_value = status.get("output_dir")
    if release and not output_root_value:
        issues.append("Fetch status has no output directory")
    output_root = Path(output_root_value).resolve() if output_root_value else None
    release_root = output_root / ".released" if output_root else None
    if release:
        for item in selected:
            if not item.get("output_path"):
                issues.append(f"Fetch item {item.get('index')} has no content path to release")
                continue
            target = Path(item["output_path"]).resolve()
            if output_root not in target.parents:
                issues.append(
                    f"Refusing to release content outside fetch output directory: {target}"
                )
                continue
            if not target.is_file():
                issues.append(f"Fetch content is missing or not a file: {target}")
                continue
            archived = release_root / f"{item['index']:04d}.md"
            if archived.exists():
                issues.append(f"Release archive already exists: {archived}")
                continue
            try:
                content = target.read_bytes()
            except OSError as exc:
                issues.append(f"Failed to snapshot fetch content {target}: {exc}")
                continue
            release_moves.append((item, target, archived, content))
    if issues:
        return {"passed": False, "issues": issues}

    digest = hashlib.sha256(Path(datapool_path).read_bytes()).hexdigest()
    moved = []
    if release_moves:
        release_root.mkdir(parents=True, exist_ok=True)
        for _, target, archived, content in release_moves:
            try:
                os.replace(target, archived)
                moved.append((target, archived, content))
            except OSError as exc:
                rollback_issues = _rollback_release_moves(moved)
                return {"passed": False, "issues": [
                    f"Failed to release {target}: {exc}", *rollback_issues,
                ]}

    released = 0
    for item in selected:
        item["processed"] = True
        item["datapool_digest"] = digest
        if release:
            item["output_path"] = ""
            item["content_released"] = True
            released += 1
    try:
        _write_json(status_path, status)
    except OSError as exc:
        rollback_issues = _rollback_release_moves(moved)
        return {"passed": False, "issues": [
            f"Failed to update fetch status: {exc}", *rollback_issues,
        ]}
    for _, archived, _ in moved:
        try:
            archived.unlink()
        except OSError as exc:
            rollback_issues = _rollback_release_moves(moved)
            try:
                _write_json(status_path, original_status)
            except OSError as status_exc:
                rollback_issues.append(f"Failed to restore fetch status: {status_exc}")
            return {"passed": False, "issues": [
                f"Failed to delete released content {archived}: {exc}",
                *rollback_issues,
            ]}
    if release_root and release_root.exists():
        try:
            release_root.rmdir()
        except OSError:
            pass
    return {
        "passed": True, "issues": [], "processed": len(selected),
        "released": released, "status": status_path, **_status_summary(status),
    }


def _load_mcp_module():
    module_path = Path(__file__).resolve().parents[1] / "scrapling-mcp-server.py"
    spec = importlib.util.spec_from_file_location("deep_research_scrapling_mcp", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load Scrapling fetch implementation")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


async def _run_bulk_fetch(urls: list[str], timeout: int, method: str) -> list[dict]:
    module = _load_mcp_module()
    return await module._bulk_fetch(
        urls, module._clamp_timeout(timeout), method, "markdown"
    )


def fetch_pending(status_path: str, method: str = "get", limit: int = 0,
                  timeout: int = 12, state: str = "unfinished") -> dict:
    if method not in {"get", "dynamic", "stealthy"}:
        return {"passed": False, "issues": [f"Invalid fetch method: {method}"]}
    if state not in {"pending", "failed", "unfinished"}:
        return {"passed": False, "issues": [f"Invalid fetch state: {state}"]}
    batch_limit = BROWSER_BATCH_SIZE if method in {"dynamic", "stealthy"} else STANDARD_BATCH_SIZE
    if limit <= 0:
        limit = batch_limit
    limit = min(limit, batch_limit)
    status = _read_json(status_path)
    items = status.get("items", [])
    eligible = [
        item for item in items
        if (item.get("status") != "success" if state == "unfinished"
            else item.get("status") == state)
        and not _already_attempted(item, method)
    ]
    urls = [item["url"] for item in eligible[:limit]]
    if not urls:
        return {"passed": True, "issues": [], "fetched": 0,
                "exhausted": sum(
                    1 for item in items
                    if item.get("status") != "success" and _already_attempted(item, method)
                ),
                "status": status_path, **_status_summary(status)}
    try:
        raw_results = asyncio.run(_run_bulk_fetch(urls, timeout, method))
    except Exception as exc:
        return {"passed": False, "issues": [f"Direct Scrapling fetch failed: {type(exc).__name__}: {exc}"]}
    payload_results = []
    for result in raw_results:
        payload_results.append({
            "url": result.get("url", ""),
            "success": bool(result.get("success")),
            "content": result.get("content", ""),
            "error": result.get("error", ""),
            "original_content_length": result.get("original_content_length", 0),
            "truncated": bool(result.get("truncated")),
        })
    status = _read_json(status_path)
    result = _ingest_payload(status, {"results": payload_results}, method)
    if not result["passed"]:
        return result
    _write_json(status_path, status)
    return {**result, "fetched": len(urls), "status": status_path,
            **_status_summary(status)}
