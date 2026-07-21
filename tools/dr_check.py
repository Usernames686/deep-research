#!/usr/bin/env python3
import json
import os
import re
from urllib.parse import urlparse

from lang_config import LANG_CONFIG, get_lang_config


# ── Profile loader ────────────────────────────────────────────────────────

_PROFILES_CACHE = None


def load_profile(mode: str) -> dict:
    global _PROFILES_CACHE
    if _PROFILES_CACHE is None:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(base, 'profiles.json')
        with open(path, 'r', encoding='utf-8-sig') as f:
            _PROFILES_CACHE = json.load(f)
    return _PROFILES_CACHE.get(mode, _PROFILES_CACHE.get('quick', {}))


# ── Mojibake & Encoding ──────────────────────────────────────────────────

MOJIBAKE_PATTERNS = [
    '\ufffd',
    '涓枃', '绯荤粺', '鍦ㄧ嚎',
    'ç³»', 'å·²',
]


def check_encoding(filepath: str) -> dict:
    issues = []
    with open(filepath, 'rb') as f:
        raw = f.read()
    if raw[:3] == b'\xef\xbb\xbf':
        issues.append("BOM detected at byte 0-2: EF BB BF")
        return {"passed": False, "issues": issues}
    try:
        text = raw.decode('utf-8')
    except UnicodeDecodeError as e:
        return {"passed": False, "issues": [f"Invalid UTF-8: {e}"]}
    for i, ch in enumerate(text):
        if ch == '\ufffd':
            line = text[:i].count('\n') + 1
            issues.append(f"Replacement character U+FFFD at line {line}")
            break
    for pattern in MOJIBAKE_PATTERNS[1:]:
        if pattern in text:
            lines = [i + 1 for i, line in enumerate(text.split('\n')) if pattern in line]
            issues.append(f"Mojibake pattern '{pattern}' at lines {lines[:3]}")
    qmark_lines = [i + 1 for i, line in enumerate(text.split('\n')) if re.search(r'\?{3,}', line)]
    if qmark_lines:
        issues.append(f"CP936 question-mark corruption at lines {qmark_lines[:5]}")
    return {"passed": len(issues) == 0, "issues": issues}


# ── Word Count ────────────────────────────────────────────────────────────

def _clean_text(filepath: str) -> str:
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        text = f.read()
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'^>\s?', '', text, flags=re.MULTILINE)
    text = re.sub(r'^[-*+]\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\d+\.\s+', '', text, flags=re.MULTILINE)
    text = text.replace('|', '')
    text = text.replace('`', '')
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'__(.+?)__', r'\1', text)
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    text = re.sub(r'_(.+?)_', r'\1', text)
    text = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', text)
    text = re.sub(r'!\[(.+?)\]\(.+?\)', r'\1', text)
    return text


def word_count(filepath: str) -> int:
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        return word_count_text(f.read())


def word_count_text(text: str) -> int:
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'^>\s?', '', text, flags=re.MULTILINE)
    text = re.sub(r'^[-*+]\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\d+\.\s+', '', text, flags=re.MULTILINE)
    text = text.replace('|', '').replace('`', '')
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'__(.+?)__', r'\1', text)
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    text = re.sub(r'_(.+?)_', r'\1', text)
    text = re.sub(r'!\[(.+?)\]\(.+?\)', r'\1', text)
    text = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', text)
    cleaned = re.sub(r'\s+', '', text)
    return len(cleaned)


# ── JSON Validation ───────────────────────────────────────────────────────


def json_validate(filepath: str) -> dict:
    try:
        with open(filepath, 'r', encoding='utf-8-sig') as f:
            json.load(f)
        return {"passed": True, "issues": []}
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        return {"passed": False, "issues": [str(e)]}


# ── Header Format Checks ──────────────────────────────────────────────────


def check_headers(filepath: str, lang: str = "zh") -> dict:
    issues = []
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        lines = f.readlines()
    cfg = get_lang_config(lang)
    structural_headings = {
        cfg['toc_heading'], cfg['refs_prefix'], cfg['disclaimer_title'],
        cfg.get('confidence_heading', ''),
    }
    for i, line in enumerate(lines):
        stripped = line.rstrip('\n\r')
        if cfg['check']['ch_has_number_check']:
            if (stripped.startswith('## ') and stripped not in structural_headings
                    and not re.match(r'^## \d+\.', stripped)):
                issues.append(f"Line {i + 1}: ## header should start with number: '{stripped[:60]}'")
        else:
            # zh: ## headers should NOT contain arabic numeral
            if re.match(r'^## .*[0-9]\.', stripped):
                issues.append(f"Line {i + 1}: ## header should not contain number: '{stripped[:60]}'")
        if re.match(r'^### [一二三四五六七八九十]', stripped):
            issues.append(f"Line {i + 1}: ### header uses Chinese numeral: '{stripped[:60]}'")
    return {"passed": len(issues) == 0, "issues": issues}


# ── Chapter Number Compliance ─────────────────────────────────────────────


def check_chapter_numbers(filepath: str, lang: str = "zh") -> dict:
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        lines = f.readlines()
    cfg = get_lang_config(lang)
    pattern = re.compile(cfg['check']['ch_number_pattern'])
    hits = [i + 1 for i, line in enumerate(lines) if pattern.match(line.rstrip('\n\r'))]
    return {"passed": len(hits) >= 1, "chapter_lines": hits, "count": len(hits)}


# ── Metadata Check ────────────────────────────────────────────────────────


def check_metadata(filepath: str, lang: str = "zh") -> dict:
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        content = f.read()
    cfg = get_lang_config(lang)
    issues = []
    meta_match = re.search(cfg['check']['metadata_pattern'], content)
    if not meta_match:
        return {"passed": False, "issues": [f"Metadata line '{cfg['metadata_label']}' not found"]}
    meta_line = content[meta_match.end():].split('\n')[0]
    for field in cfg['metadata_fields']:
        if field not in meta_line:
            issues.append(f"Metadata field '{field}' missing")
    if not re.search(cfg['check']['references_pattern'], content):
        issues.append(f"Reference source line '{cfg['references_label']}' not found")
    return {"passed": len(issues) == 0, "issues": issues}


# ── TOC Check ─────────────────────────────────────────────────────────────


def check_toc(filepath: str, expected: int = None, lang: str = "zh") -> dict:
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        lines = f.readlines()
    issues = []
    cfg = get_lang_config(lang)
    toc_heading = cfg['toc_heading']
    toc_headings = [i for i, line in enumerate(lines) if line.strip() == toc_heading]
    if len(toc_headings) == 0:
        return {"passed": False, "issues": [f"'{toc_heading}' heading not found"], "count": 0}
    elif len(toc_headings) > 1:
        issues.append(f"'{toc_heading}' appears {len(toc_headings)} times (should be 1)")
    toc_start = toc_headings[0]
    toc_entries = 0
    for line in lines[toc_start + 1:]:
        stripped = line.strip()
        if stripped.startswith('## '):
            break
        if stripped.startswith('- ['):
            toc_entries += 1
    if expected is not None and toc_entries != expected:
        issues.append(f"TOC has {toc_entries} entries, expected {expected}")
    return {"passed": len(issues) == 0, "issues": issues, "count": toc_entries}


# ── Tail Check ────────────────────────────────────────────────────────────


def check_tail(filepath: str, lang: str = "zh") -> dict:
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        content = f.read()
    cfg = get_lang_config(lang)
    issues = []
    refs_title = cfg['check']['tail_refs']
    disc_title = cfg['check']['tail_disclaimer']
    conf_title = cfg['check'].get('tail_confidence')

    accepted_refs = [refs_title, "## 数据来源"]
    for title in accepted_refs:
        if title in content:
            break
    else:
        issues.append(f"Tail section '{refs_title}' not found")
    if disc_title not in content:
        issues.append(f"'{disc_title}' not found")
    if conf_title:
        if conf_title not in content:
            issues.append(f"Confidence section '{conf_title}' not found")
        else:
            # Verify data type row exists within confidence section
            start = content.index(conf_title) + len(conf_title)
            after = content[start:]
            next_heading = after.find('\n## ')
            block = after[:next_heading] if next_heading != -1 else after
            data_type_label = cfg.get('confidence_labels', {}).get(
                'data_type', 'Data Type'
            )
            has_data_type_pct = bool(re.search(
                rf'^\*\*{re.escape(data_type_label)}\*\*.*\d+\s*\(\d+%\)',
                block,
                re.MULTILINE,
            ))
            if not has_data_type_pct:
                issues.append(
                    f"Confidence section missing data-type row '**{data_type_label}**'"
                )
    return {"passed": len(issues) == 0, "issues": issues}


# ── Year Density ──────────────────────────────────────────────────────────


def year_density(filepath: str, target_year: int) -> dict:
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        content = f.read()
    years = re.findall(r'20[2-9]\d', content)
    if not years:
        return {"passed": False, "issues": ["No year data found"], "density": 0, "total": 0}
    total = len(years)
    target_count = sum(1 for y in years if int(y) in (target_year, target_year - 1))
    density = target_count / total
    return {
        "passed": density >= 0.5,
        "density": round(density, 3),
        "target_count": target_count,
        "total": total,
        "issues": [] if density >= 0.5 else [f"Year density {density:.1%} < 50% (target={target_year})"],
    }


# ── Data Pool Check ───────────────────────────────────────────────────────


def _flatten_outline_questions(outline: dict) -> list[dict]:
    return [
        question
        for chapter in (outline.get('chapters') or [])
        if isinstance(chapter, dict)
        for question in (chapter.get('sub_questions') or [])
        if isinstance(question, dict)
    ]


def check_datapool(filepath: str, mode: str, source_mode: str = 'online',
                   strict: bool = False, outline_path: str = None) -> dict:
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError as e:
            return {"passed": False, "issues": [f"Invalid JSON: {e}"]}
    issues = []
    warnings = []
    if source_mode not in {'online', 'offline', 'mixed'}:
        return {"passed": False, "issues": [f"Invalid source mode: {source_mode}"],
                "warnings": [], "record_count": 0, "source_count": 0, "fact_count": 0}
    if strict and not isinstance(data, list):
        return {"passed": False, "issues": ["Strict data pool must be an array"],
                "warnings": [], "record_count": 0, "source_count": 0, "fact_count": 0}
    if not isinstance(data, (list, dict)):
        return {"passed": False, "issues": ["Top-level data pool must be an array or object"],
                "warnings": [], "record_count": 0, "source_count": 0, "fact_count": 0}
    records = data if isinstance(data, list) else [data]
    if not records:
        return {"passed": False, "issues": ["Data pool must contain at least one record"],
                "warnings": [], "record_count": 0, "source_count": 0, "fact_count": 0}
    required_fields = {'question': str, 'src': list, 'facts': list}
    compatibility_fields = {'q_index': int, 'priority': str, 'gaps': list,
                            'controversies': list}
    fact_required = ['src', 'yr', 'met', 'val', 'u', 'ctx', 'url']
    fact_new = ['title', 'conf', 'data_type']
    conf_values = {'high', 'medium', 'low'}
    data_type_values = {'actual', 'estimate', 'forecast'}
    cur_values = {'current', 'recent', 'dated'}
    profile = load_profile(mode)
    max_context = profile.get('max_context_chars', 0)
    max_facts = profile.get('max_facts_per_question', 0)
    max_sources = profile.get('max_sources_per_question', 0)
    for i, rec in enumerate(records):
        if not isinstance(rec, dict):
            issues.append(f"Record {i}: should be object")
            continue
        for field, ftype in required_fields.items():
            if field not in rec:
                issues.append(f"Record {i}: missing field '{field}'")
            elif not isinstance(rec[field], ftype):
                issues.append(f"Record {i}: '{field}' should be {ftype.__name__}")
        for field, ftype in compatibility_fields.items():
            if field not in rec:
                message = f"Record {i}: legacy record missing '{field}'"
                (issues if strict else warnings).append(message)
            elif not isinstance(rec[field], ftype):
                issues.append(f"Record {i}: '{field}' should be {ftype.__name__}")
        priority = rec.get('priority', 'medium')
        if priority not in {'high', 'medium', 'low'}:
            issues.append(f"Record {i}: invalid priority '{priority}'")
        facts_value = rec.get('facts', [])
        facts = facts_value if isinstance(facts_value, list) else []
        gaps = rec.get('gaps') if isinstance(rec.get('gaps'), list) else []
        for j, gap in enumerate(gaps):
            if isinstance(gap, str):
                if not gap.strip():
                    issues.append(f"Record {i} gap {j}: string must not be empty")
                continue
            if not isinstance(gap, dict):
                issues.append(f"Record {i} gap {j}: should be a string or object")
                continue
            gap_url = str(gap.get('url', '')).strip()
            reason = str(gap.get('reason', '')).strip()
            if not gap_url:
                issues.append(f"Record {i} gap {j}: missing 'url'")
            if not reason:
                issues.append(f"Record {i} gap {j}: missing 'reason'")
            parsed_gap_url = urlparse(gap_url)
            if gap_url and source_mode == 'online' and not (
                parsed_gap_url.scheme in {'http', 'https'} and parsed_gap_url.netloc
            ):
                issues.append(f"Record {i} gap {j}: online 'url' must be http(s)")
        if not facts and not gaps:
            issues.append(f"Record {i}: requires at least one fact or one gap")
        if max_facts and len(facts) > max_facts:
            issues.append(
                f"Record {i}: {len(facts)} facts exceed {mode} limit {max_facts}"
            )
        priority = rec.get('priority', 'medium')
        distinct_sources = {
            str(fact.get('url') or fact.get('src') or '').strip()
            for fact in facts if isinstance(fact, dict)
        } - {''}
        if max_sources and len(distinct_sources) > max_sources:
            issues.append(
                f"Record {i}: {len(distinct_sources)} sources exceed "
                f"{mode} limit {max_sources}"
            )
        if priority == 'high' and (len(facts) < 2 or len(distinct_sources) < 2):
            warnings.append(
                f"Record {i}: priority=high has {len(facts)} fact(s) from "
                f"{len(distinct_sources)} distinct source(s)"
            )
        for j, fact in enumerate(facts):
            if not isinstance(fact, dict):
                issues.append(f"Record {i} fact {j}: should be object")
                continue
            for field in fact_required:
                if field not in fact:
                    issues.append(f"Record {i} fact {j}: missing '{field}'")
            for field in fact_new:
                if field not in fact:
                    message = f"Record {i} fact {j}: legacy fact missing '{field}'"
                    (issues if strict else warnings).append(message)
            url_val = fact.get('url')
            if not url_val or not str(url_val).strip():
                issues.append(f"Record {i} fact {j}: 'url' is empty or null")
                is_web_url = False
            else:
                parsed = urlparse(str(url_val))
                is_web_url = parsed.scheme in {'http', 'https'} and bool(parsed.netloc)
                if source_mode == 'online' and not is_web_url:
                    issues.append(f"Record {i} fact {j}: online 'url' must be http(s)")
                elif source_mode == 'offline' and (
                    is_web_url or not os.path.isabs(os.path.expanduser(str(url_val)))
                ):
                    issues.append(
                        f"Record {i} fact {j}: offline 'url' must be an absolute local path"
                    )
                elif source_mode == 'mixed' and not is_web_url and not os.path.isabs(
                    os.path.expanduser(str(url_val))
                ):
                    issues.append(
                        f"Record {i} fact {j}: mixed local 'url' must be an absolute path"
                    )
            year = str(fact.get('yr', '')).strip()
            year_required = source_mode == 'online' or (
                source_mode == 'mixed' and is_web_url
            )
            if year_required and strict and not re.fullmatch(r'20\d{2}', year):
                issues.append(f"Record {i} fact {j}: online 'yr' must be a four-digit year")
            conf = str(fact.get('conf', '')).lower()
            if conf and conf not in conf_values:
                issues.append(f"Record {i} fact {j}: invalid conf '{conf}'")
            dtype = str(fact.get('data_type', '')).lower()
            if dtype and dtype not in data_type_values:
                issues.append(f"Record {i} fact {j}: invalid data_type '{dtype}'")
            ctx = str(fact.get('ctx', ''))
            if max_context and len(ctx) > max_context:
                issues.append(
                    f"Record {i} fact {j}: ctx has {len(ctx)} chars, limit is {max_context}"
                )
            if mode == 'quick':
                if 'cur' in fact:
                    issues.append(f"Record {i} fact {j}: quick mode should not have 'cur'")
            else:
                if 'cur' not in fact:
                    issues.append(f"Record {i} fact {j}: {mode} mode should have 'cur'")
                elif str(fact.get('cur', '')).lower() not in cur_values:
                    issues.append(f"Record {i} fact {j}: invalid cur '{fact.get('cur')}'")
    for i, rec in enumerate(records):
        for j, fact in enumerate(rec.get('facts') or []):
            for field in ('src', 'title', 'ctx'):
                val = str(fact.get(field, ''))
                if re.search(r'\?{3,}', val) or '\ufffd' in val:
                    issues.append(f"Record {i} fact {j}: mojibake in '{field}'")
    if strict:
        q_indices = [
            rec.get('q_index') if isinstance(rec, dict) else None for rec in records
        ]
        expected_indices = list(range(len(records)))
        if q_indices != expected_indices:
            issues.append(
                f"Strict q_index values must be sequential {expected_indices}; got {q_indices}"
            )
    if outline_path:
        try:
            with open(outline_path, 'r', encoding='utf-8-sig') as f:
                outline_questions = _flatten_outline_questions(json.load(f))
        except Exception as exc:
            issues.append(f"Failed to read outline for data-pool validation: {exc}")
            outline_questions = []
        if len(records) != len(outline_questions):
            issues.append(
                f"Data pool has {len(records)} records but outline has "
                f"{len(outline_questions)} sub-questions"
            )
        for index, (record, question) in enumerate(zip(records, outline_questions)):
            if not isinstance(record, dict):
                continue
            if record.get('q_index') != index:
                issues.append(f"Record {index}: q_index must match outline position {index}")
            if str(record.get('question', '')).strip() != str(
                question.get('question', '')
            ).strip():
                issues.append(f"Record {index}: question does not match outline")
            if record.get('priority') != question.get('priority', 'medium'):
                issues.append(f"Record {index}: priority does not match outline")
    all_srcs = set()
    total_facts = 0
    for rec in records:
        for s in rec.get('src', []):
            all_srcs.add(s)
        total_facts += len(rec.get('facts', []))
    return {
        "passed": len(issues) == 0,
        "issues": issues,
        "warnings": warnings,
        "record_count": len(records),
        "source_count": len(all_srcs),
        "fact_count": total_facts,
    }


def check_outline(filepath: str, mode: str = None) -> dict:
    try:
        with open(filepath, 'r', encoding='utf-8-sig') as f:
            outline = json.load(f)
    except Exception as exc:
        return {"passed": False, "issues": [f"Failed to read outline: {exc}"],
                "warnings": []}
    issues = []
    warnings = []
    if not isinstance(outline, dict):
        return {"passed": False, "issues": ["Outline must be an object"],
                "warnings": []}
    for field in (
        'title', 'type', 'depth_mode', 'language', 'time_anchor',
        'source_suggestions', 'chapters',
    ):
        if field not in outline:
            issues.append(f"Missing outline field '{field}'")
    depth_mode = mode or outline.get('depth_mode', 'standard')
    if mode and outline.get('depth_mode') != mode:
        issues.append(
            f"Outline depth_mode '{outline.get('depth_mode')}' does not match requested '{mode}'"
        )
    if outline.get('depth_mode') not in {'quick', 'standard', 'deep'}:
        issues.append("depth_mode must be quick, standard, or deep")
    if outline.get('language') not in LANG_CONFIG:
        issues.append(f"Unsupported outline language '{outline.get('language')}'")
    suggestions = outline.get('source_suggestions')
    if not isinstance(suggestions, list) or not 3 <= len(suggestions) <= 8:
        issues.append("source_suggestions must contain 3-8 domains")
    elif any(
        not str(value).strip()
        or any(token in str(value) for token in ('://', '/', '?', '#', '@'))
        or '.' not in str(value).strip().rstrip('.')
        for value in suggestions
    ):
        issues.append("source_suggestions must contain bare website domains")
    profile = load_profile(depth_mode)
    chapters = outline.get('chapters') if isinstance(outline.get('chapters'), list) else []
    if not chapters:
        issues.append("Outline must contain chapters")
    if len(chapters) < profile.get('min_chapters', 0):
        issues.append(
            f"Outline has {len(chapters)} chapters; {depth_mode} requires at least "
            f"{profile.get('min_chapters', 0)}"
        )
    max_chapters = profile.get('max_chapters', 0)
    if max_chapters and len(chapters) > max_chapters:
        issues.append(
            f"Outline has {len(chapters)} chapters; {depth_mode} allows at most {max_chapters}"
        )
    q_index = 0
    has_counter = False
    for chapter_index, chapter in enumerate(chapters, 1):
        if not isinstance(chapter, dict):
            issues.append(f"Chapter {chapter_index}: should be object")
            continue
        for field in ('title', 'description', 'sections', 'sub_questions'):
            if field not in chapter:
                issues.append(f"Chapter {chapter_index}: missing '{field}'")
        if not str(chapter.get('title', '')).strip():
            issues.append(f"Chapter {chapter_index}: title must not be empty")
        if not str(chapter.get('description', '')).strip():
            issues.append(f"Chapter {chapter_index}: description must not be empty")
        sections = chapter.get('sections') if isinstance(chapter.get('sections'), list) else []
        min_sections = profile.get('min_sections', 0)
        max_sections = profile.get('max_sections', 0)
        if len(sections) < min_sections or (max_sections and len(sections) > max_sections):
            issues.append(
                f"Chapter {chapter_index}: {len(sections)} sections outside "
                f"{min_sections}-{max_sections} range"
            )
        if any(not str(section).strip() for section in sections):
            issues.append(f"Chapter {chapter_index}: section titles must not be empty")
        questions = chapter.get('sub_questions') if isinstance(
            chapter.get('sub_questions'), list
        ) else []
        if not questions:
            issues.append(f"Chapter {chapter_index}: requires at least one sub-question")
        for question in questions:
            if not isinstance(question, dict) or not str(question.get('question', '')).strip():
                issues.append(f"Sub-question {q_index}: missing question text")
            priority = question.get('priority', 'medium') if isinstance(question, dict) else ''
            if priority not in {'high', 'medium', 'low'}:
                issues.append(f"Sub-question {q_index}: invalid priority '{priority}'")
            search_keywords = question.get('search_keywords', []) if isinstance(
                question, dict
            ) else []
            if not isinstance(search_keywords, list) or not any(
                str(item).strip() for item in search_keywords
            ):
                issues.append(f"Sub-question {q_index}: requires search_keywords")
            data_targets = question.get('data_targets', []) if isinstance(
                question, dict
            ) else []
            if not isinstance(data_targets, list) or not 2 <= len([
                item for item in data_targets if str(item).strip()
            ]) <= 3:
                issues.append(f"Sub-question {q_index}: requires 2-3 data_targets")
            counter = question.get('counter_keywords', []) if isinstance(question, dict) else []
            if priority == 'high' and not any(str(item).strip() for item in counter):
                issues.append(f"Sub-question {q_index}: high priority requires counter_keywords")
            has_counter = has_counter or bool([item for item in counter if str(item).strip()])
            q_index += 1
    if q_index and not has_counter:
        warnings.append("Outline has no counter-view search keywords")
    anchor = outline.get('time_anchor', {})
    if not isinstance(anchor, dict) or anchor.get('mode') not in {
        'latest', 'relaxed', 'user_specified'
    }:
        issues.append("time_anchor.mode must be latest, relaxed, or user_specified")
    if not isinstance(anchor, dict) or not isinstance(anchor.get('target_year'), int):
        issues.append("time_anchor.target_year must be an integer")
    return {
        "passed": not issues, "issues": issues, "warnings": warnings,
        "chapter_count": len(chapters), "sub_question_count": q_index,
        "mode": depth_mode,
    }


# ── Chapter Validation (single-command for sub-agents) ─────────────────


def _chapter_metrics(filepath: str) -> dict:
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        content = f.read()
    lines = content.splitlines()
    nonempty = [line.strip() for line in lines if line.strip()]
    check_lines = nonempty[1:] if nonempty and nonempty[0].startswith('#') else nonempty
    has_bq = bool(check_lines and check_lines[0].startswith('>'))
    table_count = sum(1 for line in nonempty if re.match(r'^\|?\s*:?-{3,}', line))
    section_lines = [line.strip() for line in lines if line.startswith('### ')]

    prose = re.sub(r'```.*?```', '', content, flags=re.DOTALL)
    blocks = re.split(r'\n\s*\n', prose)
    paragraphs = 0
    for block in blocks:
        stripped = block.strip()
        if not stripped:
            continue
        block_lines = [line.strip() for line in stripped.splitlines() if line.strip()]
        if not block_lines:
            continue
        if all(line.startswith(('#', '>', '|', '-', '*', '+')) for line in block_lines):
            continue
        paragraphs += 1
    return {
        'content': content, 'has_blockquote': has_bq, 'paragraphs': paragraphs,
        'tables': table_count, 'section_lines': section_lines,
    }


def validate_chapter(filepath: str, expected_sections=0, mode: str = None,
                     lang: str = 'zh', chapter_num: int = None) -> dict:
    results = {}
    enc = check_encoding(filepath)
    results['encoding'] = enc['passed']
    hdr = check_headers(filepath, lang=lang)
    results['headers'] = hdr['passed']
    try:
        wc = word_count(filepath)
    except Exception:
        wc = 0
    results['word_count'] = wc
    metrics = _chapter_metrics(filepath)
    results['has_blockquote'] = metrics['has_blockquote']
    results['paragraphs'] = metrics['paragraphs']
    results['tables'] = metrics['tables']
    section_headers = [line[4:].strip() for line in metrics['section_lines']]
    results['sections'] = section_headers
    results['section_count'] = len(section_headers)
    if isinstance(expected_sections, list):
        expected_titles = expected_sections
        results['sections_ok'] = len(section_headers) == len(expected_titles)
        for index, title in enumerate(expected_titles, 1):
            prefix = f"{chapter_num}.{index} " if chapter_num else ''
            expected = prefix + str(title)
            if index > len(section_headers) or section_headers[index - 1] != expected:
                results['sections_ok'] = False
    else:
        results['sections_ok'] = expected_sections == 0 or len(section_headers) == expected_sections
    profile = load_profile(mode) if mode else {}
    min_paragraphs = profile.get('min_paragraphs', 0)
    min_tables = profile.get('min_tables', 0)
    results['paragraphs_ok'] = results['paragraphs'] >= min_paragraphs
    results['tables_ok'] = results['tables'] >= min_tables
    checks = [results['encoding'], results['headers'], results['has_blockquote'],
              results['sections_ok'], results['paragraphs_ok'], results['tables_ok']]
    results['passed'] = all(checks)
    return results


# ── Batch Chapter Validation (Parallel) ───────────────────────────────────


def validate_all_chapters(chapters_dir: str, chapter_count: int = None,
                          expected_sections: int = 0, outline_path: str = None,
                          mode: str = None, lang: str = 'zh') -> dict:
    from concurrent.futures import ThreadPoolExecutor, as_completed
    chapters = []
    if outline_path:
        with open(outline_path, 'r', encoding='utf-8-sig') as f:
            outline = json.load(f)
        chapters = outline.get('chapters', [])
        chapter_count = len(chapters)
        mode = mode or outline.get('depth_mode')
        lang = lang or outline.get('language', 'zh')
    chapter_count = int(chapter_count or 0)
    if chapter_count < 1:
        return {"passed": False, "total": 0, "passed_count": 0,
                "failed_count": 0, "results": {}, "failed_chapters": {},
                "issues": ["chapter_count must be at least 1"]}
    results = {}
    with ThreadPoolExecutor(max_workers=min(chapter_count, 8)) as ex:
        futures = {}
        for i in range(1, chapter_count + 1):
            path = os.path.join(chapters_dir, f"chapter-{i}.md")
            if not os.path.exists(path):
                results[i] = {"passed": False, "error": f"chapter-{i}.md not found"}
                continue
            expected = chapters[i - 1].get('sections', []) if chapters else expected_sections
            futures[ex.submit(
                validate_chapter, path, expected, mode, lang, i
            )] = i
        for fut in as_completed(futures):
            chapter_num = futures[fut]
            try:
                result = fut.result()
                results[chapter_num] = result
            except Exception as e:
                results[chapter_num] = {"passed": False, "error": str(e)}
    sorted_results = {k: results[k] for k in sorted(results.keys())}
    failed_chapters = {str(num): r for num, r in sorted_results.items()
                       if not r.get('passed', False)}
    return {
        "passed": len(failed_chapters) == 0,
        "total": chapter_count,
        "passed_count": chapter_count - len(failed_chapters),
        "failed_count": len(failed_chapters),
        "results": sorted_results,
        "failed_chapters": failed_chapters,
    }


# ── Full QA Report ────────────────────────────────────────────────────────


def check_report_structure(filepath: str, lang: str = 'zh') -> dict:
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        content = f.read()
    cfg = get_lang_config(lang)
    issues = []
    lines = content.splitlines()
    if not lines or not lines[0].startswith('# '):
        issues.append("First line must be the report title")
    metadata_match = re.search(cfg['check']['metadata_pattern'], content)
    toc_pos = content.find(cfg['toc_heading'])
    first_chapter = re.search(cfg['check']['ch_number_pattern'], content, re.MULTILINE)
    if metadata_match is None:
        issues.append("Metadata must appear before the table of contents")
    elif toc_pos != -1 and metadata_match.start() > toc_pos:
        issues.append("Metadata appears after the table of contents")
    if toc_pos == -1:
        issues.append("Table of contents heading not found")
    elif first_chapter and toc_pos > first_chapter.start():
        issues.append("Table of contents appears after the first chapter")
    return {"passed": not issues, "issues": issues}


def check_citations(filepath: str, lang: str = 'zh') -> dict:
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        content = f.read()
    cfg = get_lang_config(lang)
    body = content.split(cfg['refs_prefix'], 1)[0]
    converted = set(re.findall(r'\[\((\d+)\)\]\(#ref\1\)', body))
    unconverted = set(re.findall(r'(?<!!)\[(\d+)\](?!\()', body))
    anchors = set(re.findall(r'<a id="ref(\d+)"></a>', content))
    issues = []
    warnings = []
    if unconverted:
        issues.append(
            "Unconverted citations: " + ', '.join(sorted(unconverted, key=int))
        )
    missing = converted - anchors
    if missing:
        issues.append(
            "Citations without reference anchors: " + ', '.join(sorted(missing, key=int))
        )
    orphaned = anchors - converted
    if orphaned:
        warnings.append(
            "Reference entries not cited in body: " + ', '.join(sorted(orphaned, key=int))
        )
    return {
        "passed": not issues, "issues": issues, "warnings": warnings,
        "citation_count": len(converted), "reference_count": len(anchors),
    }


def check_formula_syntax(filepath: str) -> dict:
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        content = f.read()
    content = re.sub(r'```.*?```', '', content, flags=re.DOTALL)
    content = re.sub(r'`[^`]*`', '', content)
    issues = []
    if '$$' in content:
        issues.append("Found unescaped $$ math delimiter")
    if re.search(r'(?<!\\)\\[\[\]]', content):
        issues.append("Found LaTeX display-math delimiter")
    if re.search(r'(?<!\\)\$(?!\s|\d)(?:[^$\n]|\\\$)+(?<!\\)\$', content):
        issues.append("Found unescaped inline-math delimiter")
    return {"passed": not issues, "issues": issues}


def _run_checks_concurrent(filepath: str, target_year: int, lang: str = "zh",
                           time_anchor: str = 'latest') -> dict:
    from concurrent.futures import ThreadPoolExecutor, as_completed

    def _wc(p):
        wc = word_count(p)
        return {'word_count': wc}

    def _toc(p, expected):
        return {'toc': check_toc(p, expected=expected, lang=lang)}

    results = {}
    with ThreadPoolExecutor(max_workers=6) as ex:
        futures = {
            ex.submit(check_encoding, filepath): 'encoding',
            ex.submit(_wc, filepath): 'word_count_raw',
            ex.submit(check_headers, filepath, lang): 'headers',
            ex.submit(check_chapter_numbers, filepath, lang): 'chapter_numbers',
            ex.submit(check_metadata, filepath, lang): 'metadata',
            ex.submit(check_tail, filepath, lang): 'tail',
            ex.submit(check_report_structure, filepath, lang): 'structure',
            ex.submit(check_citations, filepath, lang): 'citations',
            ex.submit(check_formula_syntax, filepath): 'formula_syntax',
        }
        if time_anchor == 'relaxed':
            results['year_density'] = {
                'passed': True, 'skipped': True, 'density': None,
                'issues': [], 'reason': 'relaxed time anchor',
            }
        else:
            futures[ex.submit(year_density, filepath, target_year)] = 'year_density'
        for fut in as_completed(futures):
            key = futures[fut]
            try:
                result = fut.result()
                if key == 'word_count_raw':
                    results['word_count_raw'] = result['word_count']
                else:
                    results[key] = result
            except Exception as e:
                results[key] = {"passed": False, "issues": [f"Check error: {e}"]}
    expected = results.get('chapter_numbers', {}).get('count', 0)
    results['toc'] = check_toc(filepath, expected=expected, lang=lang)
    return results


def qa_report(filepath: str, mode: str, target_year: int, lang: str = "zh",
              time_anchor: str = 'latest') -> dict:
    raw = _run_checks_concurrent(filepath, target_year, lang, time_anchor)
    results = {}
    results['encoding'] = raw.get('encoding', {"passed": False, "issues": ["missing"]})
    results['headers'] = raw.get('headers', {"passed": False, "issues": ["missing"]})
    results['chapter_numbers'] = raw.get('chapter_numbers', {"passed": False, "issues": ["missing"]})
    results['metadata'] = raw.get('metadata', {"passed": False, "issues": ["missing"]})
    results['toc'] = raw.get('toc', {"passed": False, "issues": ["missing"]})
    results['tail'] = raw.get('tail', {"passed": False, "issues": ["missing"]})
    results['year_density'] = raw.get('year_density', {"passed": False, "issues": ["missing"]})
    results['structure'] = raw.get('structure', {"passed": False, "issues": ["missing"]})
    results['citations'] = raw.get('citations', {"passed": False, "issues": ["missing"]})
    results['formula_syntax'] = raw.get(
        'formula_syntax', {"passed": False, "issues": ["missing"]}
    )
    wc = raw.get('word_count_raw', 0)
    prof = load_profile(mode)
    limit = prof.get('max_chars', 3000)
    results['word_count'] = {"passed": True, "count": wc, "limit": limit, "exceeded": wc > limit,
                              "issues": [] if wc <= limit else [f"{wc} > {limit} limit (informational)"]}
    chapter_count = results['chapter_numbers'].get('count', 0)
    minimum = prof.get('min_chapters', 0)
    maximum = prof.get('max_chapters', 0)
    chapter_issues = []
    if chapter_count < minimum:
        chapter_issues.append(f"{chapter_count} chapters < {minimum} minimum")
    if maximum and chapter_count > maximum:
        chapter_issues.append(f"{chapter_count} chapters > {maximum} maximum")
    results['chapter_profile'] = {"passed": not chapter_issues, "issues": chapter_issues,
                                  "count": chapter_count, "minimum": minimum,
                                  "maximum": maximum}
    all_passed = all(r.get('passed', False) for r in results.values())
    failures = {name: r.get('issues', []) for name, r in results.items()
                if not r.get('passed', False) and r.get('issues')}
    warnings = []
    for name, result in results.items():
        for warning in result.get('warnings', []):
            warnings.append(f"{name}: {warning}")
    if wc > limit:
        warnings.append(f"word_count: {wc} > {limit} limit")
    return {
        "passed": all_passed,
        "file": filepath,
        "mode": mode,
        "target_year": target_year,
        "time_anchor": time_anchor,
        "checks": results,
        "failures": failures,
        "warnings": warnings,
    }


# ── Chapter Depth Balance ────────────────────────────────────────────────


def check_depth_balance(chapters_dir: str, chapter_count: int,
                        threshold: float = 0.5) -> dict:
    """Check if any chapter is significantly shorter than average.
    threshold=0.5 means flag if a chapter < 50% of average line count.
    Language-agnostic — pure line count comparison."""
    issues = []
    lengths = []
    for i in range(1, chapter_count + 1):
        path = os.path.join(chapters_dir, f"chapter-{i}.md")
        try:
            with open(path, 'r', encoding='utf-8-sig') as f:
                lines = f.readlines()
            lengths.append((i, len(lines)))
        except FileNotFoundError:
            lengths.append((i, 0))
            issues.append(f"Chapter {i}: file not found")

    if not lengths:
        return {"passed": False, "issues": ["No chapter files found"]}

    avg = sum(n for _, n in lengths) / len(lengths)
    thin = [(i, n) for i, n in lengths if n < avg * threshold and n > 0]
    for i, n in thin:
        issues.append(
            f"Chapter {i}: {n} lines ({n/avg:.0%} of avg {avg:.0f} lines) "
            f"— below {threshold:.0%} threshold"
        )

    return {"passed": len(issues) == 0, "issues": issues,
            "chapters": [{"num": i, "lines": n} for i, n in lengths],
            "average": round(avg, 1)}
