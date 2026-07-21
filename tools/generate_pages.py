#!/usr/bin/env python3
"""Generate the GitHub Pages index or the file:// compatible local browser."""

import base64
import argparse
import hashlib
import html
import json
import os
import pathlib
import re
import shutil
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from lang_config import LANG_CONFIG, get_lang_config


_SKILL_DIR = pathlib.Path(__file__).resolve().parent.parent
REPORTS_DIR = str(_SKILL_DIR / "reports")
OUTPUT_DIR = str(_SKILL_DIR / "gh-pages")
LOCAL_OUTPUT_DIR = str(_SKILL_DIR / "reports-browser")
API_BASE = "https://api.github.com"

LANG_NAMES = {
    "zh": "中文", "en": "English", "ja": "日本語", "ko": "한국어",
    "es": "Español", "fr": "Français", "de": "Deutsch", "pt": "Português",
    "it": "Italiano", "nl": "Nederlands", "sv": "Svenska", "ru": "Русский",
    "ar": "العربية", "hi": "हिन्दी", "vi": "Tiếng Việt",
    "id": "Bahasa Indonesia", "th": "ไทย", "tr": "Türkçe", "pl": "Polski",
}
MODE_LABELS = {"quick": "Quick", "standard": "Standard", "deep": "Deep"}


def _api_get(path):
    token = os.environ.get("GITHUB_TOKEN", "")
    repo = _safe_repo(os.environ.get("GITHUB_REPOSITORY", "hoolulu/deep-research"))
    request = urllib.request.Request(f"{API_BASE}/repos/{repo}/{path}")
    request.add_header("Accept", "application/vnd.github.v3+json")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def _safe_repo(value: str) -> str:
    return value if re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", value or "") \
        else "hoolulu/deep-research"


def _relative_report_path(path: str) -> str:
    full_path = pathlib.Path(path).resolve()
    try:
        return full_path.relative_to(_SKILL_DIR).as_posix()
    except ValueError:
        normalized = str(path).replace("\\", "/")
        marker = normalized.find("reports/")
        return normalized[marker:] if marker >= 0 else full_path.as_posix()


def _extract_lang(relative_path: str) -> str:
    parts = pathlib.PurePosixPath(relative_path).parts
    if len(parts) >= 3 and parts[0] == "reports" and parts[1] in LANG_CONFIG:
        return parts[1]
    return "en"


def _metadata_value(metadata: str, field: str) -> str:
    match = re.search(rf"(?:^| · ){re.escape(field)}\s*[:：]\s*([^·]+)", metadata)
    return match.group(1).strip() if match else ""


def parse_content(content: str, path: str) -> dict:
    """Parse report metadata using the same language config as report assembly."""
    relative_path = _relative_report_path(path)
    lang = _extract_lang(relative_path)
    config = get_lang_config(lang)
    title_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else pathlib.Path(path).name

    metadata_pattern = rf"^>\s*{re.escape(config['metadata_label'])}\s*(.+)$"
    metadata_match = re.search(metadata_pattern, content, re.MULTILINE)
    metadata = metadata_match.group(1) if metadata_match else ""
    fields = config["metadata_fields"]
    mode = _metadata_value(metadata, fields[4]).lower() if len(fields) > 4 else ""
    if mode not in MODE_LABELS:
        mode = "standard"
    word_value = _metadata_value(metadata, fields[0]) if fields else ""
    digits = re.search(r"[\d,]+", word_value)
    word_count = int(digits.group(0).replace(",", "")) if digits else 0
    if word_count == 0:
        word_count = len(re.sub(r"\s+", "", content))

    count_pattern = re.escape(config["refs_count_format"]).replace(
        re.escape("{count}"), r"(\d+)"
    )
    source_match = re.search(count_pattern, content)
    if source_match:
        sources = int(source_match.group(1))
    else:
        anchors = [int(value) for value in re.findall(r'<a id="ref(\d+)"></a>', content)]
        sources = max(anchors) if anchors else 0

    date_match = re.search(r"(\d{4})(\d{2})(\d{2})", pathlib.Path(path).name)
    date = "-".join(date_match.groups()) if date_match else ""
    return {
        "title": title,
        "path": relative_path,
        "lang": lang,
        "lang_name": LANG_NAMES.get(lang, lang),
        "mode": mode,
        "word_count": word_count,
        "date": date,
        "sources": sources,
    }


def fmt(number):
    if number >= 10000:
        return f"{round(number / 10000, 1)}w" if number % 10000 else f"{number // 10000}w"
    if number >= 1000:
        return f"{round(number / 1000, 1)}k" if number % 1000 else f"{number // 1000}k"
    return str(number)


def _json_for_script(value) -> str:
    return (json.dumps(value, ensure_ascii=False)
            .replace("</", "<\\/")
            .replace("\u2028", "\\u2028")
            .replace("\u2029", "\\u2029"))


def _load_local_report(report: dict, reports_dir: str = None) -> str | None:
    if "_content" in report:
        return str(report["_content"])
    root = pathlib.Path(reports_dir or REPORTS_DIR).resolve()
    report_path = pathlib.PurePosixPath(str(report.get("path", "")))
    parts = report_path.parts
    if "reports" in parts:
        relative_parts = parts[parts.index("reports") + 1:]
        candidate = root.joinpath(*relative_parts).resolve()
    elif report_path.is_absolute():
        candidate = pathlib.Path(str(report_path)).resolve()
    else:
        candidate = root.joinpath(*parts).resolve()
    if candidate != root and root not in candidate.parents:
        return None
    try:
        return candidate.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError):
        return None


def _write_lazy_payloads(reports: list[dict], out_dir: str,
                         reports_dir: str = None) -> dict[str, str]:
    data_dir = pathlib.Path(out_dir) / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    payloads = {}
    expected = set()
    for index, report in enumerate(reports):
        content = _load_local_report(report, reports_dir)
        if content is None:
            continue
        digest = hashlib.sha256(str(report.get("path", "")).encode("utf-8")).hexdigest()[:12]
        filename = f"{index:04d}-{digest}.js"
        expected.add(filename)
        payload = (
            f"window.__DR_REPORT_LOADED__({_json_for_script(str(index))},"
            f"{_json_for_script(content)});\n"
        )
        target = data_dir / filename
        temporary = target.with_suffix(".js.tmp")
        temporary.write_text(payload, encoding="utf-8", newline="\n")
        os.replace(temporary, target)
        payloads[str(index)] = f"data/{filename}"
    for stale in data_dir.glob("*.js"):
        if stale.name not in expected:
            stale.unlink()
    return payloads


def _escape(value) -> str:
    return html.escape(str(value), quote=True)


def _href(path: str, local: bool, base: str) -> str:
    quoted = urllib.parse.quote(str(path), safe="/._-~")
    return f"../{quoted}" if local else f"{base}/{quoted}"


def gen_html(reports, local=False, out_dir=None, reports_dir=None):
    out_dir = out_dir or OUTPUT_DIR
    pathlib.Path(out_dir).mkdir(parents=True, exist_ok=True)
    payloads = _write_lazy_payloads(reports, out_dir, reports_dir) if local else {}
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    repo = _safe_repo(os.environ.get("GITHUB_REPOSITORY", "hoolulu/deep-research"))
    base = f"https://github.com/{repo}/blob/main"

    lang_counts = {}
    for report in reports:
        lang_counts[report["lang"]] = lang_counts.get(report["lang"], 0) + 1
    lang_order = sorted(
        lang_counts.items(),
        key=lambda item: (0 if item[0] == "zh" else 1 if item[0] == "en" else 2, -item[1]),
    )
    chips = "".join(
        f'<button class="lc" data-lc="{_escape(code)}" onclick="fc(this)">'
        f'{_escape(LANG_NAMES.get(code, code))} <span>{count}</span></button>'
        for code, count in lang_order
    )
    language_options = "".join(
        f'<option value="{_escape(code)}">{_escape(LANG_NAMES.get(code, code))}</option>'
        for code in lang_counts
    )
    mode_options = "".join(
        f'<option value="{_escape(mode)}">{_escape(MODE_LABELS.get(mode, mode.title()))}</option>'
        for mode in sorted({report["mode"] for report in reports})
    )

    rows = []
    for index, report in enumerate(reports):
        mode = report["mode"] if report["mode"] in MODE_LABELS else "standard"
        data_src = payloads.get(str(index), "")
        rows.append(
            f'<tr data-lang="{_escape(report["lang"])}" data-mode="{_escape(mode)}" '
            f'data-word="{int(report["word_count"])}" data-sources="{int(report["sources"])}" '
            f'data-date="{_escape(report["date"])}" data-rid="{index}" '
            f'data-src="{_escape(data_src)}">'
            f'<td class="n">{index + 1}</td>'
            f'<td class="tc"><a href="{_escape(_href(report["path"], local, base))}" '
            f'target="_blank" rel="noopener noreferrer">{_escape(report["title"])}</a></td>'
            f'<td>{_escape(report["lang_name"])}</td>'
            f'<td><span class="mb mb-{mode}">{_escape(MODE_LABELS[mode])}</span></td>'
            f'<td class="m">{_escape(fmt(report["word_count"]))}</td>'
            f'<td class="m">{int(report["sources"])}</td>'
            f'<td class="m">{_escape(report["date"])}</td></tr>'
        )

    preview_html = ""
    preview_css = ""
    preview_js = ""
    if local:
        preview_html = '''
<div id="pv" class="pv" hidden><div class="pv-shell">
  <header class="pv-head"><h2 id="pv-title"></h2>
    <button type="button" onclick="ex('pdf')" title="Export PDF">PDF</button>
    <button type="button" onclick="ex('docx')" title="Export DOCX">DOCX</button>
    <button type="button" onclick="tt()" title="Table of contents">TOC</button>
    <button type="button" onclick="pc()" title="Close" aria-label="Close">&#10005;</button>
  </header>
  <nav id="pv-toc" class="pv-toc" hidden></nav>
  <article id="pv-body" class="pv-body"></article>
</div></div>'''
        preview_css = '''
.pv{position:fixed;inset:0;background:rgba(0,0,0,.5);z-index:10}.pv-shell{max-width:900px;height:100%;margin:auto;background:var(--bg);display:flex;flex-direction:column;position:relative}.pv-head{display:flex;align-items:center;gap:8px;padding:10px 16px;border-bottom:1px solid var(--border)}.pv-head h2{flex:1;min-width:0;font-size:15px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.pv-head button,.pg button{border:1px solid var(--border);background:var(--bg);padding:5px 9px;border-radius:5px;cursor:pointer}.pv-body{flex:1;overflow:auto;padding:20px;line-height:1.7;overflow-wrap:anywhere}.pv-body h1{font-size:24px}.pv-body h2{font-size:20px;margin-top:24px}.pv-body h3{font-size:17px;margin-top:20px}.pv-body table{border-collapse:collapse;width:100%;font-size:14px}.pv-body th,.pv-body td{border:1px solid var(--border);padding:6px 10px}.pv-body pre{overflow:auto}.pv-body blockquote{border-left:4px solid var(--accent);margin:12px 0;padding:4px 16px;background:var(--canvas)}.pv-toc{position:absolute;right:8px;top:52px;width:min(320px,90vw);max-height:60vh;overflow:auto;background:var(--bg);border:1px solid var(--border);padding:8px;z-index:2}.pv-toc a{display:block;padding:4px 8px;color:var(--fg);text-decoration:none}.pv-toc .l3{padding-left:24px;font-size:12px}'''
        preview_js = r'''
var RC={},RW={};
window.__DR_REPORT_LOADED__=function(k,m){RC[k]=m;if(RW[k]){RW[k].resolve(m);delete RW[k]}};
function lib(src,name){if(window[name])return Promise.resolve();return new Promise(function(resolve,reject){var s=document.createElement('script');s.src=src;s.onload=function(){window[name]?resolve():reject(new Error(name+' unavailable'))};s.onerror=reject;document.head.appendChild(s)})}
function body(k,src){if(RC[k]!==undefined)return Promise.resolve(RC[k]);return new Promise(function(resolve,reject){RW[k]={resolve:resolve,reject:reject};var s=document.createElement('script');s.src=src;s.onload=function(){if(RC[k]===undefined){delete RW[k];reject(new Error('Report payload missing'))}};s.onerror=function(){delete RW[k];reject(new Error('Report payload failed'))};document.head.appendChild(s)})}
function po(row){var k=row.dataset.rid,src=row.dataset.src;if(!src)return;var title=row.querySelector('a').textContent;document.getElementById('pv-title').textContent=title;var pv=document.getElementById('pv'),pb=document.getElementById('pv-body');pv.hidden=false;pb.textContent='Loading...';document.body.style.overflow='hidden';Promise.all([body(k,src),lib('marked.min.js','marked'),lib('dompurify.min.js','DOMPurify')]).then(function(v){var rendered=marked.parse(v[0]);pb.innerHTML=DOMPurify.sanitize(rendered,{USE_PROFILES:{html:true},FORBID_TAGS:['script','style','iframe','object','embed','form','input','button','textarea','select'],FORBID_ATTR:['style']});pb.querySelectorAll('a').forEach(function(a){a.rel='noopener noreferrer'});toc()}).catch(function(){pb.textContent='Unable to load this report.'})}
function pc(){document.getElementById('pv').hidden=true;document.body.style.overflow=''}
function tt(){var t=document.getElementById('pv-toc');t.hidden=!t.hidden}
function toc(){var panel=document.getElementById('pv-toc'),pb=document.getElementById('pv-body');panel.textContent='';pb.querySelectorAll('h1,h2,h3').forEach(function(h,i){if(!h.id)h.id='toc-'+i;var a=document.createElement('a');a.href='#'+encodeURIComponent(h.id);a.textContent=h.textContent;if(h.tagName==='H3')a.className='l3';a.onclick=function(e){e.preventDefault();h.scrollIntoView({behavior:'smooth'});panel.hidden=true};panel.appendChild(a)})}
document.getElementById('b').addEventListener('click',function(e){var a=e.target.closest('a');if(!a)return;var row=a.closest('tr');if(row&&row.dataset.src){e.preventDefault();po(row)}});
function ex(kind){var title=document.getElementById('pv-title').textContent.replace(/[<>:"/\\|?*]/g,'_')||'report',node=document.getElementById('pv-body');if(kind==='pdf'){lib('html2pdf.bundle.min.js','html2pdf').then(function(){html2pdf().from(node).set({filename:title+'.pdf',margin:.5,html2canvas:{scale:2},jsPDF:{unit:'in',format:'a4'}}).save()})}else{lib('html-docx.min.js','htmlDocx').then(function(){var blob=htmlDocx.asBlob('<!doctype html><html><meta charset="utf-8"><body>'+node.innerHTML+'</body></html>');var u=URL.createObjectURL(blob),a=document.createElement('a');a.href=u;a.download=title+'.docx';a.click();setTimeout(function(){URL.revokeObjectURL(u)},1000)})}}
'''

    heading = "Your Reports" if local else "Deep Research Reports"
    subtitle = "Browse your locally generated research reports" if local else "Browse all generated reports"
    document = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'self' data: blob:; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; object-src 'none'; base-uri 'none'; form-action 'none'">
<title>{_escape(heading)}</title><link rel="icon" href="favicon.svg"><style>
:root{{--fg:#1f2328;--bg:#fff;--canvas:#f6f8fa;--border:#d0d7de;--accent:#0969da;--muted:#656d76;--green:#1a7f37;--orange:#9a6700;--font:-apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans",sans-serif;--mono:ui-monospace,SFMono-Regular,Menlo,monospace}}
*{{box-sizing:border-box}}body{{margin:0;font-family:var(--font);color:var(--fg);background:var(--bg);line-height:1.5}}.w{{max-width:1100px;margin:auto;padding:24px 16px}}h1{{font-size:24px;margin:0}}.sub{{color:var(--muted);margin:4px 0 20px}}.filters{{display:flex;gap:8px;flex-wrap:wrap;margin:12px 0}}input,select{{border:1px solid var(--border);border-radius:5px;padding:7px 10px;background:var(--bg)}}input{{flex:1;min-width:220px}}.lc{{border:1px solid var(--border);border-radius:16px;background:var(--bg);padding:4px 10px;margin:0 4px 8px 0;cursor:pointer}}.lc.s{{background:var(--accent);color:#fff;border-color:var(--accent)}}.lc span{{font-size:11px;color:var(--muted)}}.table{{border:1px solid var(--border);border-radius:6px;overflow:hidden}}table{{width:100%;border-collapse:collapse;font-size:14px}}th,td{{padding:8px 12px;text-align:left;border-bottom:1px solid var(--border)}}th{{background:var(--canvas);cursor:pointer}}tr:last-child td{{border-bottom:0}}.tc a{{color:var(--accent);text-decoration:none;font-weight:500}}.n,.m{{font-family:var(--mono);font-size:12px;color:var(--muted)}}.mb{{font-size:11px;font-weight:600}}.mb-quick{{color:var(--green)}}.mb-standard{{color:var(--accent)}}.mb-deep{{color:var(--orange)}}.hidden{{display:none}}.pg,.foot{{display:flex;justify-content:space-between;align-items:center;gap:8px;margin-top:10px;color:var(--muted);font-size:12px}}{preview_css}
@media(max-width:700px){{.w{{padding:16px 8px}}thead{{display:none}}tbody tr{{display:block;padding:10px;border-bottom:1px solid var(--border)}}td{{display:block;border:0;padding:3px}}td.n{{display:none}}}}
</style></head><body>{preview_html}<main class="w">
<h1>{_escape(heading)}</h1><p class="sub">{_escape(subtitle)}</p><div>{chips}</div>
<div class="filters"><input id="q" placeholder="Search reports" oninput="filterRows()"><select id="l" onchange="filterRows()"><option value="">All languages</option>{language_options}</select><select id="m" onchange="filterRows()"><option value="">All depths</option>{mode_options}</select><span id="count">{len(reports)} reports</span></div>
<div class="table"><table><thead><tr><th>#</th><th onclick="sortRows(1)">Report</th><th onclick="sortRows(2)">Language</th><th onclick="sortRows(3)">Depth</th><th onclick="sortRows(4)">Words</th><th onclick="sortRows(5)">Sources</th><th onclick="sortRows(6)">Date</th></tr></thead><tbody id="b">{''.join(rows)}</tbody></table></div>
<div class="pg"><span id="page-info"></span><span><button onclick="page(-1)">Prev</button> <button onclick="page(1)">Next</button></span></div>
<footer class="foot"><span>Last updated: {_escape(now)}</span><a href="https://github.com/hoolulu/deep-research" rel="noopener noreferrer">deep-research</a></footer>
</main><script>
var ROWS=Array.from(document.querySelectorAll('#b tr')),PAGE=1,SIZE=20,DIR={{}};
ROWS.forEach(function(r){{r.dataset.match='1'}});
function filterRows(){{var q=document.getElementById('q').value.toLowerCase(),l=document.getElementById('l').value,m=document.getElementById('m').value,n=0;ROWS.forEach(function(r){{var ok=(!q||r.querySelector('a').textContent.toLowerCase().includes(q))&&(!l||r.dataset.lang===l)&&(!m||r.dataset.mode===m);r.dataset.match=ok?'1':'0';if(ok)n++}});document.getElementById('count').textContent=n+' reports';PAGE=1;renderPage()}}
function fc(button){{document.querySelectorAll('.lc').forEach(function(x){{x.classList.toggle('s',x===button)}});document.getElementById('l').value=button.dataset.lc;filterRows()}}
function sortRows(column){{DIR[column]=DIR[column]===1?-1:1;ROWS.sort(function(a,b){{var x=a.children[column].textContent.trim(),y=b.children[column].textContent.trim();if(column===4){{x=Number(a.dataset.word);y=Number(b.dataset.word)}}else if(column===5){{x=Number(a.dataset.sources);y=Number(b.dataset.sources)}}else if(column===6){{x=a.dataset.date;y=b.dataset.date}}return (typeof x==='number'?x-y:x.localeCompare(y))*DIR[column]}});ROWS.forEach(function(r){{document.getElementById('b').appendChild(r)}});renderPage()}}
function renderPage(){{var matched=ROWS.filter(function(r){{return r.dataset.match==='1'}}),pages=Math.max(1,Math.ceil(matched.length/SIZE));PAGE=Math.max(1,Math.min(PAGE,pages));ROWS.forEach(function(r){{r.classList.add('hidden')}});matched.slice((PAGE-1)*SIZE,PAGE*SIZE).forEach(function(r){{r.classList.remove('hidden')}});document.getElementById('page-info').textContent='Page '+PAGE+' of '+pages}}
function page(delta){{PAGE+=delta;renderPage()}}renderPage();{preview_js}
</script></body></html>'''
    target = pathlib.Path(out_dir) / "index.html"
    temporary = target.with_suffix(".html.tmp")
    temporary.write_text(document, encoding="utf-8", newline="\n")
    os.replace(temporary, target)


def gen_favicon(out_dir):
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
           '<rect width="64" height="64" rx="12" fill="#0969da"/>'
           '<text x="32" y="44" text-anchor="middle" font-size="36" '
           'font-weight="bold" fill="white" font-family="sans-serif">DR</text></svg>')
    (pathlib.Path(out_dir) / "favicon.svg").write_text(svg, encoding="utf-8")


def copy_local_assets(out_dir):
    source_dir = _SKILL_DIR / "reports-browser"
    for name in (
        "marked.min.js", "dompurify.min.js", "html-docx.min.js",
        "html2pdf.bundle.min.js",
    ):
        source = source_dir / name
        target = pathlib.Path(out_dir) / name
        if source.resolve() != target.resolve():
            shutil.copy2(source, target)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local", action="store_true",
                        help="Generate the local lazy-loading report browser")
    parser.add_argument("--fallback", action="store_true",
                        help="Use the GitHub API when a checked-out report is unreadable")
    parser.add_argument("--reports-dir", default=REPORTS_DIR,
                        help="Report tree to scan (default: project reports directory)")
    parser.add_argument("--output-dir", default=None,
                        help="Output directory (default depends on --local)")
    args = parser.parse_args(argv)
    local = args.local
    use_fallback = args.fallback
    reports_dir = pathlib.Path(args.reports_dir).expanduser().resolve()
    reports = []
    for root, _, files in os.walk(reports_dir):
        for filename in sorted(files):
            if not filename.endswith(".md"):
                continue
            path = os.path.join(root, filename)
            try:
                reports.append(parse_content(pathlib.Path(path).read_text(encoding="utf-8-sig"), path))
            except (FileNotFoundError, OSError, UnicodeError):
                if not use_fallback:
                    print(f"  SKIP (unreadable): {filename}")
                    continue
                relative = _relative_report_path(path)
                try:
                    response = _api_get(f"contents/{relative}")
                    content = base64.b64decode(response["content"]).decode("utf-8")
                    reports.append(parse_content(content, relative))
                except Exception as error:
                    print(f"  API fallback failed {filename}: {error}")

    reports.sort(key=lambda report: report["date"], reverse=True)
    out_dir = args.output_dir or (LOCAL_OUTPUT_DIR if local else OUTPUT_DIR)
    pathlib.Path(out_dir).mkdir(parents=True, exist_ok=True)
    reports_path = pathlib.Path(out_dir) / "reports.json"
    temporary = reports_path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(reports, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, reports_path)
    gen_html(reports, local=local, out_dir=out_dir, reports_dir=str(reports_dir))
    gen_favicon(out_dir)
    if local:
        copy_local_assets(out_dir)
    label = "local report browser" if local else "GitHub Pages"
    print(f"Done: {len(reports)} reports -> {out_dir}/ ({label})")


if __name__ == "__main__":
    main()
