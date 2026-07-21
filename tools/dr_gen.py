#!/usr/bin/env python3
import json
import locale
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from dr_check import check_encoding, load_profile, word_count_text
from lang_config import get_lang_config, CHINESE_NUMERALS, LANG_CONFIG


# ── Source Extraction ─────────────────────────────────────────────────────

SOURCE_PATTERN = re.compile(r'[（(]([^）)]+?)[，,]\s*(\d{4})[）)]')


def extract_sources(filepath: str) -> dict:
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        content = f.read()
    matches = SOURCE_PATTERN.findall(content)
    seen = set()
    unique = []
    for inst, year in matches:
        key = inst.strip()
        if key and key not in seen:
            seen.add(key)
            unique.append(key)
    return {
        "source_count": len(unique),
        "sources": unique,
        "sources_joined": "、".join(sorted(unique)),
        "total_mentions": len(matches),
    }


# ── TOC Generation ─────────────────────────────────────────────────────────


def _github_anchor(text: str) -> str:
    """Generate a GitHub-compatible heading anchor.

    Mirrors cmark-gfm + utf8proc: keep only Unicode letters (L), digits (N),
    spaces (Z), underscore (_), and hyphen (-). Drop all punctuation and symbols.
    """
    import unicodedata
    text = text.lower()
    result = []
    for ch in text:
        cat = unicodedata.category(ch)
        if cat.startswith(('L', 'N')) or ch in (' ', '_', '-'):
            result.append(ch)
    text = ''.join(result)
    text = re.sub(r'\s+', '-', text)
    text = re.sub(r'-+', '-', text)
    text = text.strip('-')
    return text


def generate_toc(outline_path: str) -> dict:
    with open(outline_path, 'r', encoding='utf-8-sig') as f:
        outline = json.load(f)
    chapters = outline.get('chapters', [])
    lang = outline.get('language', 'zh')
    cfg = get_lang_config(lang)
    lines = []
    for i, ch in enumerate(chapters):
        prefix = cfg['toc_prefix'](i + 1)
        title = ch.get('title', '')
        label = f"{prefix} {title}" if lang != 'zh' else f"{prefix}{title}"
        anchor = _github_anchor(label)
        lines.append(f"- [{label}](#{anchor})")
    return {
        "chapter_count": len(chapters),
        "toc_lines": lines,
        "toc_text": '\n'.join(lines),
    }


# ── Metadata Block Generation ─────────────────────────────────────────────


def generate_metadata(word_count: int, reading_time: int, data_until: str,
                       generate_time: str, depth_mode: str,
                       source_count: int, top_sources: list,
                       skill_version: str = "",
                       lang: str = "zh") -> dict:
    cfg = get_lang_config(lang)
    fields = cfg['metadata_fields']
    s = cfg['sep']
    fs = cfg['field_sep']
    version_str = f"{s}{fields[5]}{fs}{skill_version}" if skill_version else ""
    line1 = (
        f"> {cfg['metadata_label']}"
        f"{fields[0]}{fs}{word_count}"
        f"{s}{fields[1]}{fs}{reading_time} {cfg['minute_unit']}"
        f"{s}{fields[2]}{fs}{data_until}"
        f"{s}{fields[3]}{fs}{generate_time}"
        f"{s}{fields[4]}{fs}{depth_mode}{version_str}"
    )
    sorted_sources = sorted(top_sources)[:8]
    src_fmt = cfg['refs_count_format']
    count_text = src_fmt(source_count) if callable(src_fmt) else src_fmt.format(count=source_count)
    if lang == 'zh':
        source_str = "、".join(sorted_sources)
        line2 = f"> {cfg['references_label']}{source_str} 等 · {count_text}"
    else:
        source_str = ", ".join(sorted_sources)
        line2 = f"> {cfg['references_label']}{source_str} et al. · {count_text}"
    return {
        "metadata_line": line1,
        "source_line": line2,
        "full_block": line1 + '\n>\n' + line2,
    }


# ── Chapter Mapping ───────────────────────────────────────────────────────


def map_chapters(outline_path: str) -> dict:
    with open(outline_path, 'r', encoding='utf-8-sig') as f:
        outline = json.load(f)
    chapters = outline.get('chapters', [])
    mapping = {}
    for i, ch in enumerate(chapters):
        sqs = ch.get('sub_questions', [])
        chapter_num = i + 1
        mapping[chapter_num] = {
            "title": ch.get('title', ''),
            "sections": ch.get('sections', []),
            "sub_questions": [
                {"question": sq.get('question', ''), "priority": sq.get('priority', 'medium')}
                for sq in sqs
            ],
            "sub_question_count": len(sqs),
        }
    return {"chapter_count": len(chapters), "mapping": mapping, "chapter_numbers": list(mapping.keys())}


# ── Hyperlinked Reference List ────────────────────────────────────────────


def _normalize_url(url: str) -> str:
    value = str(url or '').strip()
    if not value:
        return ''
    parts = urlsplit(value)
    if parts.scheme in {'http', 'https'} and parts.netloc:
        scheme = parts.scheme.lower()
        host = (parts.hostname or '').lower()
        port = parts.port
        default_port = (scheme == 'http' and port == 80) or (scheme == 'https' and port == 443)
        netloc = host if not port or default_port else f"{host}:{port}"
        path = parts.path or '/'
        return urlunsplit((scheme, netloc, path, parts.query, ''))
    try:
        return str(Path(value).expanduser().resolve())
    except (OSError, RuntimeError):
        return value


def citation_key(fact: dict) -> tuple:
    url = _normalize_url(fact.get('url', ''))
    if url:
        return ('url', url)
    return (
        'source', str(fact.get('src', '')).strip(), str(fact.get('yr', '')).strip(),
        str(fact.get('title', '')).strip(),
    )


def _citation_entries(datapool_path: str) -> list[dict]:
    data = _read_json_handle_bom(datapool_path)
    records = data if isinstance(data, list) else [data]
    seen = set()
    entries = []
    for record in records:
        for fact in record.get('facts') or []:
            if not isinstance(fact, dict):
                continue
            key = citation_key(fact)
            if key in seen:
                continue
            seen.add(key)
            entries.append({
                'number': len(entries) + 1,
                'key': list(key),
                'src': str(fact.get('src', '')).strip(),
                'yr': str(fact.get('yr', '')).strip(),
                'title': str(fact.get('title', '')).strip(),
                'url': str(fact.get('url', '')).strip(),
            })
    return entries


def generate_citation_map(datapool_path: str, output_path: str = None) -> dict:
    entries = _citation_entries(datapool_path)
    result = {'version': 1, 'entries': entries, 'count': len(entries)}
    if output_path:
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        tmp = output_path + '.tmp'
        with open(tmp, 'w', encoding='utf-8', newline='\n') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
            f.write('\n')
        os.replace(tmp, output_path)
        result['output'] = output_path
    return result


def generate_refs(datapool_path: str, numbered: bool = False, lang: str = "zh") -> dict:
    cfg = get_lang_config(lang)
    raw_entries = _citation_entries(datapool_path)
    entries = [
        (entry['src'], entry['yr'], entry['title'] or entry['src'], entry['url'])
        for entry in raw_entries
    ]
    if not numbered:
        entries.sort(key=lambda item: (item[0].lower(), item[2]))

    src_fmt = cfg['refs_count_format']
    count_text = src_fmt(len(entries)) if callable(src_fmt) else src_fmt.format(count=len(entries))
    lines = [f"{cfg['refs_prefix']}\n", f"{count_text}\n"]
    if numbered:
        for i, (inst, yr, title, url) in enumerate(entries, 1):
            label = f"{title} · {inst}" + (f" · {yr}" if yr else "")
            lines.append(f"({i}) [{label}]({url})" if url else f"({i}) {label}")
        ref_text = '\n'.join(lines[:2]) + '\n\n' + '\n\n'.join(lines[2:])
    else:
        for inst, yr, title, url in entries:
            label = f"{title} · {inst}" + (f" · {yr}" if yr else "")
            lines.append(f"- [{label}]({url})" if url else f"- {label}")
        ref_text = '\n'.join(lines)
    return {"source_count": len(entries), "ref_lines": lines, "ref_text": ref_text}


# ── Convert Citations to Numeric Index ────────────────────────────────────

CITATION_RE = re.compile(r'[（(]([^）)]+?)[，,]\s*(\d{4})[）)]')

_UTF8_SIG = 'utf-8-sig'


def _read_json_handle_bom(path: str):
    with open(path, 'r', encoding=_UTF8_SIG) as f:
        return json.load(f)


# ── Search Engine Detection ─────────────────────────────────────────────────


def detect_engine() -> dict:
    import json as _json
    import urllib.request as _req
    import urllib.error as _err

    try:
        endpoint = os.environ.get("SEARXNG_URL", "https://search.h33.top/search")
        separator = "&" if "?" in endpoint else "?"
        r = _req.Request(
            f"{endpoint}{separator}q=test&format=json",
            headers={"User-Agent": "Mozilla/5.0"},
            method="GET",
        )
        timeout = max(1.0, float(os.environ.get("SEARXNG_DETECT_TIMEOUT", "5")))
        with _req.urlopen(r, timeout=timeout) as resp:
            data = _json.loads(resp.read().decode("utf-8"))
            if isinstance(data, dict) and "results" in data:
                return {"engine": "searxng", "available": True}
    except Exception:
        pass

    return {"engine": "none", "available": False}


def convert_citations(report_path: str, datapool_path: str, output_path: str = None, lang: str = "zh") -> dict:
    with open(report_path, 'r', encoding='utf-8-sig') as f:
        content = f.read()

    cfg = get_lang_config(lang)

    # Check: report should NOT contain （机构，年份） patterns
    legacy_cites = re.findall(r'[（(][^）)]+?[，,]\s*\d{4}[）)]', content)
    if legacy_cites:
        issues = [f"Found {len(legacy_cites)} legacy （机构，年份） citations — chapter agents must use (N) format"]
        return {"passed": False, "issues": issues, "changes": 0}

    entries = _citation_entries(datapool_path)

    # Scan body for [N] patterns
    split_marker = cfg['refs_prefix']
    body = content.split(split_marker)[0] if split_marker in content else content
    body_refs = set(re.findall(r'(?<!!)\[(\d+)\](?!\()', body))
    body_refs.update(re.findall(r'\[\((\d+)\)\]\(#ref\1\)', body))

    issues = []
    for num in sorted(body_refs, key=int):
        num_i = int(num)
        if num_i < 1 or num_i > len(entries):
            issues.append(f"Body references ({num}) which has no data-pool entry")

    # Build reference section
    entry_lines = []
    for entry in entries:
        num = entry['number']
        inst, yr, url = entry['src'], entry['yr'], entry['url']
        title = entry['title'] or inst
        label = title if title == inst else f"{title} · {inst}"
        label = label + (f" · {yr}" if yr else "")
        anchor = f'<a id="ref{num}"></a>'
        if url:
            entry_lines.append(f'{anchor}({num}) [{label}]({url})')
        else:
            entry_lines.append(f'{anchor}({num}) {label}')

    ref_text = f'{cfg["refs_prefix"]}\n\n' + '\n\n'.join(entry_lines)

    # Insert/replace refs section
    old_section = re.search(
        rf'{re.escape(cfg["refs_prefix"])}.*?(?=\n## |\Z)', content, re.DOTALL
    )
    if old_section:
        prefix = content[:old_section.start()].rstrip()
        suffix = content[old_section.end():].lstrip('\n')
        new_content = prefix + '\n\n' + ref_text
        if suffix:
            new_content += '\n\n' + suffix
    else:
        new_content = content.rstrip() + '\n\n' + ref_text
    if content.endswith('\n') and not new_content.endswith('\n'):
        new_content += '\n'

    # Validate: every [N] in body has matching ref anchor
    ref_anchors = set(re.findall(r'<a id="ref(\d+)"></a>', new_content))
    missing_in_refs = body_refs - ref_anchors
    if missing_in_refs:
        issues.append(
            f"Citations without matching reference: [{', '.join(sorted(missing_in_refs, key=int))}]")

    # Convert [N] → [(N)](#refN)
    BODY_CITE_RE = re.compile(r'(?<!!)\[(\d+)\](?!\()')
    new_content = BODY_CITE_RE.sub(r'[(\1)](#ref\1)', new_content)

    # Clean up structural headings from other languages
    foreign_headings = set()
    for code, lcfg in LANG_CONFIG.items():
        if code == lang:
            continue
        foreign_headings.add(lcfg['refs_prefix'])
        foreign_headings.add(lcfg['disclaimer_title'])
        foreign_headings.add(lcfg['toc_heading'])
    for heading in foreign_headings:
        pattern = re.compile(
            rf'^{re.escape(heading)}\s*$.*?(?=\n## |\Z)',
            re.MULTILINE | re.DOTALL
        )
        new_content = pattern.sub('', new_content)

    # Write output
    output = output_path or report_path
    os.makedirs(os.path.dirname(os.path.abspath(output)), exist_ok=True)
    tmp = output + '.tmp'
    with open(tmp, 'w', encoding='utf-8', newline='\n') as f:
        f.write(new_content)
    os.replace(tmp, output)

    return {
        "passed": len(issues) == 0,
        "changes": len(entries),
        "output": output,
        "issues": issues,
        "citation_count": len(body_refs),
        "ref_count": len(ref_anchors),
    }


# ── Encoding-safe stdin reader (cross-platform) ─────────────────────────────


def _read_stdin() -> str:
    raw = sys.stdin.buffer.read()
    if not raw:
        return ''
    try:
        return raw.decode('utf-8')
    except UnicodeDecodeError:
        pass
    try:
        return raw.decode(locale.getpreferredencoding())
    except (UnicodeDecodeError, LookupError):
        pass
    return raw.decode('utf-8', errors='replace')


# ── JSON Write (atomic, encoding-safe) ─────────────────────────────────────


def write_json(filepath: str) -> dict:
    raw = _read_stdin()
    if not raw.strip():
        return {"passed": False, "issues": ["Empty input from stdin"]}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        return {"passed": False, "issues": [f"JSON parse error: {e}"]}
    tmp = filepath + '.tmp'
    try:
        with open(tmp, 'w', encoding='utf-8', newline='\n') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write('\n')
        os.replace(tmp, filepath)
    except (OSError, IOError) as e:
        return {"passed": False, "issues": [f"Write failed: {e}"]}
    return {"passed": True, "issues": [], "size": os.path.getsize(filepath)}


# ── Markdown Write (encoding-safe, Mojibake-free) ─────────────────────────


def write_md(filepath: str) -> dict:
    raw = _read_stdin()
    if not raw.strip():
        return {"passed": False, "issues": ["Empty input from stdin"]}
    tmp = filepath + '.tmp'
    try:
        with open(tmp, 'w', encoding='utf-8', newline='\n') as f:
            f.write(raw)
        os.replace(tmp, filepath)
    except (OSError, IOError) as e:
        return {"passed": False, "issues": [f"Write failed: {e}"]}
    enc_check = check_encoding(filepath)
    if not enc_check['passed']:
        return {"passed": False, "issues": [f"Write succeeded but Mojibake detected: {enc_check['issues']}"]}
    return {"passed": True, "issues": [], "size": os.path.getsize(filepath)}


# ── Prepare Chapter Skeleton ──────────────────────────────────────────────


def prepare_chapter(outline_path: str, datapool_path: str,
                    chapter_num: int, total_chapters: int, mode: str) -> dict:
    with open(outline_path, 'r', encoding='utf-8-sig') as f:
        outline = json.load(f)
    with open(datapool_path, 'r', encoding='utf-8-sig') as f:
        data = json.load(f)

    chapters = outline.get('chapters', [])
    lang = outline.get('language', 'zh')
    cfg = get_lang_config(lang)

    if chapter_num < 1 or chapter_num > len(chapters):
        return {"passed": False, "issues": [f"Chapter {chapter_num} out of range (1-{len(chapters)})"]}

    ch = chapters[chapter_num - 1]
    title = ch.get('title', '')
    sections = ch.get('sections', [])
    sub_questions = ch.get('sub_questions', [])

    prof = load_profile(mode)
    total_limit = prof.get('max_chars', 3000)
    per_chapter_target = total_limit // max(total_chapters, 1)

    pool_records = data if isinstance(data, list) else [data]
    sq_questions = [sq.get('question', '') for sq in sub_questions]

    citation_numbers = {
        tuple(entry['key']): entry['number']
        for entry in generate_citation_map(datapool_path)['entries']
    }
    relevant_facts = []
    for rec in pool_records:
        rec_q = rec.get('question', '')
        match_score = sum(1 for sq in sq_questions if any(
            kw.lower() in rec_q.lower() for kw in sq.split() if len(kw) > 2
        ))
        if match_score > 0:
            facts = rec.get('facts') or []
            for fact in facts:
                relevant_facts.append({
                    "source": fact.get('src', ''),
                    "year": fact.get('yr', ''),
                    "metric": fact.get('met', ''),
                    "value": fact.get('val'),
                    "unit": fact.get('u', ''),
                    "context": fact.get('ctx', ''),
                    "citation_number": citation_numbers.get(citation_key(fact)),
                })

    relevant_facts.sort(key=lambda x: x.get('year', ''), reverse=True)

    lines = []
    prefix_str = cfg['chapter_heading'](chapter_num, title)
    lines.append(f"# {title}")
    lines.append(f"\n> " + ("Core judgment for this chapter." if lang != 'zh' else "本章核心判断。") + "\n")
    per_section_est = per_chapter_target // max(len(sections), 1)
    char_note = "chars" if lang != 'zh' else "字"
    lines.append(f"> **{'Word target' if lang != 'zh' else '字数参考'}**：{'chapter target' if lang != 'zh' else '本章目标'} ≈ {per_chapter_target} {char_note}（{'per section' if lang != 'zh' else '每节'} ~{per_section_est} {char_note}）| sections: {len(sections)} | {'pre-matched facts' if lang != 'zh' else '预匹配事实'}: {len(relevant_facts)}\n")

    for idx, section in enumerate(sections):
        sec_num = idx + 1
        lines.append(f"### {chapter_num}.{sec_num} {section}\n")
        section_facts = [f for f in relevant_facts if section in f.get('context', '') or sec_num <= 2]
        if not section_facts:
            section_facts = relevant_facts[:2] if relevant_facts else []
            if section_facts:
                relevant_facts = relevant_facts[2:]
        for fact in section_facts[:3]:
            val_str = f"{fact['value']}{fact['unit']}" if fact['value'] is not None else fact['context']
            citation = f"[{fact['citation_number']}]" if fact.get('citation_number') else ""
            lines.append(f"- {fact['metric']}: {val_str}{citation}")
        lines.append("")

    skeleton = '\n'.join(lines)
    return {
        "passed": True,
        "skeleton": skeleton,
        "chapter_title": title,
        "fact_count": len(relevant_facts),
        "estimated_words": per_chapter_target,
    }


# ── Assemble Final Report ─────────────────────────────────────────────────


def assemble_report(outline_path: str, chapters_dir: str,
                    datapool_path: str,
                    mode: str, target_year: int,
                    wordcount_path: str = None,
                    output_path: str = None,
                    lang_override: str = None,
                    overwrite: bool = False) -> dict:
    import datetime
    issues = []

    try:
        with open(outline_path, 'r', encoding='utf-8-sig') as f:
            outline = json.load(f)
    except Exception as e:
        return {"passed": False, "issues": [f"Failed to read outline: {e}"]}

    title = outline.get('title', '报告')
    lang = outline.get('language', 'zh')
    if lang_override and lang_override not in LANG_CONFIG:
        return {"passed": False, "issues": [f"Unsupported language: {lang_override}"]}
    if lang_override and lang_override != lang:
        return {"passed": False, "issues": [
            f"Language mismatch: outline={lang}, --lang={lang_override}"
        ]}
    cfg = get_lang_config(lang)
    now = datetime.datetime.now()

    # Sanitize title for filesystem: replace Windows-invalid chars with '-'
    # Invalid on Windows: < > : " / \ | ? *
    safe_title = re.sub(r'[<>:"/\\|?*]', '-', title)
    # Also trim trailing dots/spaces (Windows issue)
    safe_title = safe_title.rstrip('. ') or 'report'

    if not output_path:
        skill_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        output_path = os.path.join(
            skill_dir, 'reports', lang,
            f"{safe_title}-{now.strftime('%Y%m%d-%H%M%S')}.md",
        )
    elif os.path.isdir(output_path) or not output_path.endswith('.md'):
        base = os.path.join(output_path, f"{safe_title}-{now.strftime('%Y%m%d-%H%M%S')}.md")
        output_path = base
    chapters = outline.get('chapters', [])
    depth_mode = outline.get('depth_mode', mode)

    chapter_files = []
    for i in range(1, len(chapters) + 1):
        path = os.path.join(chapters_dir, f"chapter-{i}.md")
        if os.path.exists(path) and os.path.getsize(path) > 0:
            chapter_files.append((i, path))
        else:
            issues.append(f"Missing chapter file: chapter-{i}.md")

    if issues:
        return {"passed": False, "issues": issues, "output_path": output_path}

    toc_result = generate_toc(outline_path)
    toc_text = toc_result['toc_text']

    chapter_texts = []
    for num, fpath in sorted(chapter_files):
        with open(fpath, 'r', encoding='utf-8-sig') as f:
            content = f.read().strip()
        content = re.sub(r'^#{1,2} .+?\n+', '', content, count=1)
        heading = cfg['chapter_heading'](num, chapters[num - 1].get('title', ''))
        chapter_texts.append(f'{heading}\n\n{content}')

    data_until = f"{target_year}" if lang != 'zh' else f"{target_year}年"
    generate_time = now.strftime("%Y-%m-%d %H:%M:%S")

    try:
        refs = generate_refs(datapool_path, lang=lang)
        total_sources = refs['source_count']
        ref_text = refs['ref_text']
    except Exception as e:
        return {"passed": False, "issues": [f"Source extraction failed: {e}"],
                "output_path": output_path}

    try:
        with open(datapool_path, 'r', encoding='utf-8-sig') as f:
            dp_data = json.load(f)
        records = dp_data if isinstance(dp_data, list) else [dp_data]
        source_freq = {}
        for rec in records:
            for fact in rec.get('facts') or []:
                src = fact.get('src', '')
                if src:
                    source_freq[src] = source_freq.get(src, 0) + 1
        top_sources = sorted(source_freq, key=source_freq.get, reverse=True)[:8]
    except Exception:
        top_sources = []

    script_dir = os.path.dirname(os.path.abspath(__file__))
    version_path = os.path.join(script_dir, '..', 'VERSION')
    try:
        with open(version_path, 'r', encoding='utf-8-sig') as f:
            version = f.read().strip()
    except Exception:
        version = ""

    toc_heading = cfg['toc_heading']
    promo = cfg.get('promo_line') or get_lang_config('en').get('promo_line', '')

    def build_report(count: int, reading_time: int) -> str:
        meta = generate_metadata(
            word_count=count, reading_time=reading_time,
            data_until=data_until, generate_time=generate_time,
            depth_mode=depth_mode, source_count=total_sources,
            top_sources=top_sources, skill_version=version, lang=lang,
        )
        report_parts = [
            f"# {title}\n", f"{meta['full_block']}\n",
            toc_heading, "\n", toc_text, "\n",
            '\n\n'.join(chapter_texts), "\n\n---\n\n", ref_text,
            f"\n\n{cfg['disclaimer_title']}\n\n{cfg['disclaimer_text']}\n",
            f"\n{cfg['report_generated'].format(time=generate_time)}\n",
            f"{promo}\n",
        ]
        return '\n'.join(report_parts)

    total_wc = 0
    reading_time = 1
    full_report = ''
    for _ in range(6):
        full_report = build_report(total_wc, reading_time)
        new_count = word_count_text(full_report)
        new_reading = max(1, round(new_count / 800))
        if (new_count, new_reading) == (total_wc, reading_time):
            break
        total_wc, reading_time = new_count, new_reading
    full_report = build_report(total_wc, reading_time)

    parent = os.path.dirname(os.path.abspath(output_path))
    os.makedirs(parent, exist_ok=True)
    if os.path.exists(output_path) and not overwrite:
        return {"passed": False, "issues": [
            f"Output already exists; pass --overwrite to replace it: {output_path}"
        ], "output_path": output_path}

    tmp = output_path + '.tmp'
    try:
        with open(tmp, 'w', encoding='utf-8', newline='\n') as f:
            f.write(full_report)
        os.replace(tmp, output_path)
    except Exception as e:
        return {"passed": False, "issues": [f"Write failed: {e}"]}

    enc_check = check_encoding(output_path)
    if not enc_check['passed']:
        issues.append(f"Encoding issue in assembled report: {enc_check['issues']}")

    line_count = full_report.count('\n') + 1

    return {
        "passed": len(issues) == 0,
        "output_path": output_path,
        "line_count": line_count,
        "chapter_count": len(chapter_files),
        "word_count": total_wc,
        "issues": issues,
    }


def _metadata_values(content: str, lang: str) -> dict:
    cfg = get_lang_config(lang)
    line = next(
        (item for item in content.splitlines()
         if item.startswith(f"> {cfg['metadata_label']}")),
        '',
    )
    values = {}
    if not line:
        return values
    body = line[len(f"> {cfg['metadata_label']}"):]
    for part in body.split(cfg['sep']):
        for field in cfg['metadata_fields']:
            prefix = f"{field}{cfg['field_sep']}"
            if part.startswith(prefix):
                values[field] = part[len(prefix):].strip()
                break
    return values


def refresh_metadata(report_path: str, datapool_path: str = None,
                     lang: str = 'zh') -> dict:
    with open(report_path, 'r', encoding='utf-8-sig') as f:
        content = f.read()
    cfg = get_lang_config(lang)
    values = _metadata_values(content, lang)
    fields = cfg['metadata_fields']
    if not values:
        return {'passed': False, 'issues': ['Metadata line not found']}
    data_until = values.get(fields[2], '')
    generate_time = values.get(fields[3], '')
    depth_mode = values.get(fields[4], 'standard')
    version = values.get(fields[5], '')

    if datapool_path:
        entries = _citation_entries(datapool_path)
        source_count = len(entries)
        frequencies = {}
        for entry in entries:
            if entry['src']:
                frequencies[entry['src']] = frequencies.get(entry['src'], 0) + 1
        top_sources = sorted(frequencies, key=frequencies.get, reverse=True)[:8]
    else:
        source_count = len(set(re.findall(r'<a id="ref(\d+)"></a>', content)))
        top_sources = []

    block_pattern = re.compile(
        rf'^> {re.escape(cfg["metadata_label"])}.*?\n>\n> '
        rf'{re.escape(cfg["references_label"])}.*?$',
        re.MULTILINE,
    )
    if not block_pattern.search(content):
        return {'passed': False, 'issues': ['Complete metadata block not found']}

    count = word_count_text(content)
    reading_time = max(1, round(count / 800))
    refreshed = content
    for _ in range(6):
        block = generate_metadata(
            word_count=count, reading_time=reading_time,
            data_until=data_until, generate_time=generate_time,
            depth_mode=depth_mode, source_count=source_count,
            top_sources=top_sources, skill_version=version, lang=lang,
        )['full_block']
        refreshed = block_pattern.sub(block, content, count=1)
        new_count = word_count_text(refreshed)
        new_reading = max(1, round(new_count / 800))
        if (new_count, new_reading) == (count, reading_time):
            break
        count, reading_time = new_count, new_reading

    tmp = report_path + '.tmp'
    with open(tmp, 'w', encoding='utf-8', newline='\n') as f:
        f.write(refreshed)
    os.replace(tmp, report_path)
    return {
        'passed': True, 'issues': [], 'word_count': count,
        'reading_time': reading_time, 'source_count': source_count,
    }


def cleanup_run(tmpdir: str) -> dict:
    path = Path(tmpdir).expanduser().resolve()
    allowed_roots = {
        Path(tempfile.gettempdir()).resolve(), Path('/tmp').resolve(),
        Path('/private/tmp').resolve(),
    }
    if not any(root == path.parent or root in path.parents for root in allowed_roots):
        return {'passed': False, 'issues': [f"Run directory is outside temporary roots: {path}"]}
    if not path.name.startswith('codex-deep-research-'):
        return {'passed': False, 'issues': ["Run directory name has invalid prefix"]}
    marker = path / '.deep-research-run.json'
    try:
        data = json.loads(marker.read_text(encoding='utf-8-sig'))
    except Exception as exc:
        return {'passed': False, 'issues': [f"Valid run marker not found: {exc}"]}
    if data.get('kind') != 'deep-research-run':
        return {'passed': False, 'issues': ["Run marker kind is invalid"]}
    shutil.rmtree(path)
    return {'passed': True, 'issues': [], 'removed': str(path)}


# ── Confidence Assessment Section ────────────────────────────────────────

AUTHORITY_KEYWORDS = [
    'gov', 'edu', 'org', 'university', 'institute', 'academy',
    '统计局', '科学院', '教育部', '发改委', '央行', '人民银行',
    'world bank', 'imf', 'oecd', 'who', 'united nations',
    'national bureau', 'ministry', 'commission', '研究中心', '研究院',
    '基金会', '基金', 'association',
    # Academic / journal signals
    'arxiv', 'doi.org', 'pnas', 'nature.com', 'science.org',
    'springer', 'iopscience', 'ieee', 'nasa', 'esa',
    'un.org', 'who.int', 'worldbank',
]

MEDIA_KEYWORDS = [
    'news', '媒体', '新闻', '报道', 'blog', '自媒体', '公众号',
    'times', 'post', 'herald', 'tribune', '记者', '日报', '晚报',
    '晨报', 'weekly', 'magazine', '广播', '电视台',
]


def _classify_source(src: str) -> str:
    """Classify a source as 'authoritative', 'media', or 'industry'."""
    s = src.lower().strip()
    if not s:
        return 'industry'
    for kw in AUTHORITY_KEYWORDS:
        if kw in s:
            return 'authoritative'
    for kw in MEDIA_KEYWORDS:
        if kw in s:
            return 'media'
    return 'industry'


def _source_text(fact: dict) -> str:
    parts = [fact.get('src', ''), fact.get('url', ''), fact.get('title', '')]
    return ' '.join(str(p) for p in parts if p).lower()


def _infer_confidence(fact: dict) -> str:
    """Return high/medium/low; use explicit conf when present."""
    conf = (fact.get('conf') or '').strip().lower()
    if conf in ('high', 'medium', 'low'):
        return conf
    src_class = _classify_source(_source_text(fact))
    if src_class == 'authoritative':
        return 'high'
    if src_class == 'media':
        return 'medium'
    # arxiv / doi / peer-reviewed hints in URL or title
    text = _source_text(fact)
    if any(k in text for k in ('arxiv', 'doi.org', 'nature.com', 'science.org',
                               'iopscience', 'springer', 'ieee', 'nasa', 'esa')):
        return 'high'
    return 'medium'


def _infer_data_type(fact: dict) -> str:
    """Return actual/estimate/forecast; use explicit data_type when present."""
    dtype = (fact.get('data_type') or '').strip().lower()
    if dtype in ('actual', 'estimate', 'forecast'):
        return dtype
    text = ' '.join(str(fact.get(k, '')) for k in ('ctx', 'met', 'title')).lower()
    if any(k in text for k in ('预测', 'forecast', 'projected', 'projection', '预计到', '有望达到')):
        return 'forecast'
    if any(k in text for k in ('估算', '预估', '预计', 'estimate', '约', '大约', '左右')):
        return 'estimate'
    return 'actual'





def generate_confidence_section(datapool_path: str, manifest_path: str,
                                lang: str = 'zh') -> dict:
    """Generate the Confidence Assessment markdown section from data-pool + manifest.

    Returns dict with 'passed' (bool), 'section' (str, markdown), 'issues' (list).
    """
    issues = []
    try:
        with open(datapool_path, 'r', encoding='utf-8-sig') as f:
            pool = json.load(f)
    except Exception as e:
        return {'passed': False, 'section': '',
                'issues': [f"Failed to read data-pool: {e}"]}

    try:
        with open(manifest_path, 'r', encoding='utf-8-sig') as f:
            manifest = json.load(f)
    except Exception as e:
        return {'passed': False, 'section': '',
                'issues': [f"Failed to read manifest: {e}"]}

    records = pool if isinstance(pool, list) else [pool]

    # ── Aggregate stats ──
    total_facts = 0
    conf_counts = {'high': 0, 'medium': 0, 'low': 0}
    type_counts = {'actual': 0, 'estimate': 0, 'forecast': 0}
    src_class_counts = {'authoritative': 0, 'industry': 0, 'media': 0}
    controversies_total = 0
    explicit_conf = 0
    explicit_dtype = 0

    for rec in records:
        for fact in rec.get('facts') or []:
            total_facts += 1
            if (fact.get('conf') or '').strip().lower() in conf_counts:
                explicit_conf += 1
            if (fact.get('data_type') or '').strip().lower() in type_counts:
                explicit_dtype += 1
            c = _infer_confidence(fact)
            conf_counts[c] += 1
            t = _infer_data_type(fact)
            type_counts[t] += 1
            src_class_counts[_classify_source(_source_text(fact))] += 1
        controversies_total += len(rec.get('controversies') or [])

    has_inferred_fields = total_facts > 0 and (
        explicit_conf < total_facts or explicit_dtype < total_facts
    )

    # ── Coverage from manifest ──
    coverage_list = manifest.get('coverage') or []
    adequate = sum(1 for c in coverage_list if c.get('status') == 'adequate')
    insufficient = sum(1 for c in coverage_list if c.get('status') == 'insufficient')
    total_subq = len(coverage_list)
    data_limited = manifest.get('data_limited', False)
    unique_domains = manifest.get('unique_domains', 0)

    # ── Build lines ──
    cfg = get_lang_config(lang)
    labels = cfg['confidence_labels']
    field_sep = cfg.get('field_sep', ': ')
    heading = cfg.get('confidence_heading', '## Confidence Assessment')
    lines = [heading, '']

    # ── 1. Source type (粗分) ──
    auth = src_class_counts['authoritative']
    ind = src_class_counts['industry']
    med = src_class_counts['media']
    academic_src_pct = round(auth / total_facts * 100) if total_facts > 0 else 0
    lines.append(f"**{labels['source_type']}**{field_sep}"
                 f"{labels['authoritative']} {auth} · "
                 f"{labels['industry']} {ind} · "
                 f"{labels['media']} {med}")
    lines.append('')

    # ── 2. Data type (MANDATORY — never omitted) ──
    act = type_counts['actual']
    est = type_counts['estimate']
    fct = type_counts['forecast']
    if total_facts > 0:
        act_pct = round(act / total_facts * 100)
        est_pct = round(est / total_facts * 100)
        fct_pct = round(fct / total_facts * 100)
    else:
        act_pct = est_pct = fct_pct = 0
    lines.append(f"**{labels['data_type']}**{field_sep}"
                 f"{labels['actual']} {act} ({act_pct}%) · "
                 f"{labels['estimate']} {est} ({est_pct}%) · "
                 f"{labels['forecast']} {fct} ({fct_pct}%)")
    lines.append('')

    # ── 3. Confidence distribution ──
    high = conf_counts['high']
    medium = conf_counts['medium']
    low = conf_counts['low']
    if total_facts > 0:
        high_pct = round(high / total_facts * 100)
    else:
        high_pct = 0
    lines.append(f"**{labels['distribution']}**{field_sep}"
                 f"{labels['high']} {high} ({high_pct}%) · "
                 f"{labels['medium']} {medium} · "
                 f"{labels['low']} {low}")
    lines.append('')

    # ── 4. Coverage ──
    if total_subq > 0:
        lines.append(f"**{labels['coverage']}**{field_sep}"
                     f"{adequate}/{total_subq} {labels['adequate']} · "
                     f"{insufficient}/{total_subq} {labels['insufficient']}")
        lines.append('')

    # ── 5. Data limitation ──
    if data_limited:
        label_limited = labels['limited']
    else:
        label_limited = labels['none']
    lines.append(f"**{labels['limitations']}**{field_sep}{label_limited}")
    lines.append('')

    # ── 6. Controversies (conditional) ──
    if controversies_total > 0:
        lines.append(f"**{labels['discrepancies']}**{field_sep}"
                     f"{controversies_total} {labels['discrepancy_note']}")
        lines.append('')

    # ── 7. Score & rating ──
    if total_facts > 0:
        score = (high / total_facts) * 40 + (act / total_facts) * 30
        if total_subq > 0:
            score += (adequate / total_subq) * 20
        if not data_limited:
            score += 10
        score = round(score)

        if score >= 75:
            label_verdict = cfg['verdict_labels']['reliable']
        elif score >= 50:
            label_verdict = cfg['verdict_labels']['moderate']
        else:
            label_verdict = cfg['verdict_labels']['caution']

        lines.append(f"**{labels['rating']}**{field_sep}{label_verdict} ({score}/100)")
        lines.append('')

    else:
        score = 0
        label_verdict = labels['no_data']

    # ── Quick-mode note (last, conditional) ──
    if has_inferred_fields:
        lines.append(labels['inference_note'])
        lines.append('')

    section = '\n'.join(lines)

    # ── Machine-readable summary (language-agnostic, numbers only) ──
    coverage_summary = manifest.get('coverage_summary', 'unknown')
    adequate_subq = adequate
    total_subq_count = total_subq
    summary = {
        'coverage': coverage_summary,
        'total_facts': total_facts,
        'high_pct': high_pct if total_facts > 0 else 0,
        'medium_pct': round(medium / total_facts * 100) if total_facts > 0 else 0,
        'low_pct': round(low / total_facts * 100) if total_facts > 0 else 0,
        'actual_pct': act_pct if total_facts > 0 else 0,
        'est_pct': est_pct if total_facts > 0 else 0,
        'fct_pct': fct_pct if total_facts > 0 else 0,
        'auth_pct': academic_src_pct,
        'data_limited': data_limited,
        'controversies': controversies_total,
        'adequate_subq': adequate_subq,
        'total_subq': total_subq_count,
        'verdict_label': label_verdict,
        'score': score,
    }
    return {'passed': True, 'section': section, 'issues': issues, 'summary': summary}


def escape_currency(report_path: str) -> dict:
    """Escape unescaped dollar signs to prevent LaTeX math mode rendering.

    Platforms like Zhihu, Typora, Obsidian and GitHub with MathJax interpret
    $ as inline math delimiter. This function escapes standalone $ used as
    currency prefix, while skipping protected contexts.
    """
    with open(report_path, 'r', encoding='utf-8-sig') as f:
        content = f.read()

    # Repair stale promo placeholders from pre-fix escape_currency runs
    content = re.sub(
        r'\[deep-research\]\(__URL_\d+__\)',
        '[deep-research](https://github.com/hoolulu/deep-research)',
        content,
    )

    changes = 0
    protected = {}
    counter = [0]

    def _protect(pattern, template='__DOLLAR_SAFE_{}__', flags=0):
        nonlocal content
        def replacer(m):
            counter[0] += 1
            key = template.format(counter[0])
            protected[key] = m.group(0)
            return key
        content = re.sub(pattern, replacer, content, flags=flags)

    # Protect contexts where $ should NOT be escaped
    _protect(r'```.*?```', '__CODE_BLOCK_{}__', re.DOTALL)  # fenced code blocks
    _protect(r'`[^`]+`', '__INLINE_CODE_{}__')             # inline code
    _protect(r'\[([^\[\]]*)\]\(([^)]*)\)', '__MD_LINK_{}__')  # markdown links (before URLs)
    _protect(r'https?://[^\s\)]+', '__URL_{}__')            # bare URLs
    _protect(r'<[^>]+>', '__HTML_TAG_{}__')                 # HTML tags (anchors etc.)
    _protect(r'^\|[-:]+\|', '__TABLE_SEP_{}__', re.MULTILINE)  # table separators

    # Strategy: escape ALL $ that are followed by a digit (currency pattern)
    # while skipping those already escaped (\$)
    def _escape_dollar(m):
        nonlocal changes
        changes += 1
        return m.group(1) + '\\' + m.group(2)

    # Match $ that is NOT preceded by backslash, and IS followed by a digit
    content = re.sub(r'(^|[^\\])(\$)(?=\d)', _escape_dollar, content)

    # Restore protected segments in reverse insertion order so markdown links
    # restored after URL placeholders still get their URLs expanded.
    for key, val in reversed(list(protected.items())):
        content = content.replace(key, val)

    issues = []
    if re.search(r'\]\(__URL_\d+__\)', content):
        issues.append('Unresolved __URL_N__ placeholders in markdown links')

    # Write back
    tmp = report_path + '.tmp'
    with open(tmp, 'w', encoding='utf-8', newline='\n') as f:
        f.write(content)
    os.replace(tmp, report_path)

    return {'passed': len(issues) == 0, 'issues': issues, 'changes': changes}
