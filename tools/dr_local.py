#!/usr/bin/env python3
import json
import os
import re
from pathlib import Path


SUPPORTED_SUFFIXES = {".md", ".txt", ".pdf", ".docx"}
DEFAULT_MAX_CHARS = 500_000


def _safe_name(path: Path, index: int) -> str:
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", path.stem).strip("-.") or "document"
    return f"{index:03d}-{stem}.txt"


def _extract_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".md", ".txt"}:
        return path.read_text(encoding="utf-8-sig")
    if suffix == ".pdf":
        from pypdf import PdfReader
        reader = PdfReader(str(path))
        return "\n\n".join(page.extract_text() or "" for page in reader.pages)
    if suffix == ".docx":
        from docx import Document
        document = Document(str(path))
        return "\n".join(paragraph.text for paragraph in document.paragraphs)
    raise ValueError(f"Unsupported file type: {suffix}")


def _collect_files(inputs: list[str], exclude_root: Path = None) -> tuple[list[Path], list[str]]:
    files = []
    warnings = []
    seen = set()
    for raw in inputs:
        path = Path(raw).expanduser().resolve()
        if not path.exists():
            warnings.append(f"Path not found: {path}")
            continue
        candidates = [path] if path.is_file() else sorted(
            item for item in path.rglob("*") if item.is_file()
        )
        for candidate in candidates:
            resolved = candidate.resolve()
            if exclude_root and (resolved == exclude_root or exclude_root in resolved.parents):
                continue
            if candidate.suffix.lower() not in SUPPORTED_SUFFIXES:
                warnings.append(f"Unsupported file skipped: {candidate}")
                continue
            if resolved not in seen:
                seen.add(resolved)
                files.append(resolved)
    return files, warnings


def extract_local(inputs: list[str], output_dir: str, manifest_path: str) -> dict:
    output = Path(output_dir).expanduser().resolve()
    files, warnings = _collect_files(inputs, exclude_root=output)
    output.mkdir(parents=True, exist_ok=True)
    max_chars = max(1, int(os.environ.get(
        "DEEP_RESEARCH_LOCAL_MAX_CHARS", str(DEFAULT_MAX_CHARS)
    )))
    records = []
    for index, source in enumerate(files, 1):
        target = output / _safe_name(source, index)
        try:
            text = _extract_text(source)
            if not text.strip():
                raise ValueError("No extractable text found")
            original_chars = len(text)
            truncated = original_chars > max_chars
            if truncated:
                text = text[:max_chars]
            temp_target = target.with_suffix(target.suffix + ".tmp")
            temp_target.write_text(text, encoding="utf-8", newline="\n")
            os.replace(temp_target, target)
            records.append({
                "source_path": str(source),
                "output_path": str(target),
                "type": source.suffix.lower().lstrip("."),
                "chars": len(text),
                "original_chars": original_chars,
                "truncated": truncated,
                "status": "ok",
            })
        except Exception as exc:
            records.append({
                "source_path": str(source),
                "output_path": "",
                "type": source.suffix.lower().lstrip("."),
                "chars": 0,
                "status": "error",
                "error": f"{type(exc).__name__}: {exc}",
            })
    manifest = {
        "version": 1,
        "source_mode": "offline",
        "files": records,
        "warnings": warnings,
    }
    os.makedirs(os.path.dirname(os.path.abspath(manifest_path)), exist_ok=True)
    tmp = manifest_path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, manifest_path)
    success_count = sum(1 for item in records if item["status"] == "ok")
    return {
        "passed": success_count > 0,
        "issues": [] if success_count > 0 else ["No supported local files were extracted"],
        "warnings": warnings + [
            item["error"] for item in records if item["status"] == "error"
        ],
        "manifest": manifest_path,
        "file_count": success_count,
    }
