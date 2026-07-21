# deep-research Skill

<p align="center"><a href="README.md">中文</a> · <b>English</b></p>

**Deep Research Report Generation Skill — One command, ten minutes, institutional-grade deep research report**

Multi-agent autonomous search, scrape, write, and QA — feed it a topic, get a citable, browsable, exportable research report in Chinese or 19 other languages.

Benchmarked against institutional research structure: conclusions-first, traceable sources, counter-arguments, scenario forecasting. Supports quick / standard / deep tiers, with automatic language detection across 19 languages.

Built for industry research, trend foresight, competitive scanning, policy analysis, technology deep-dives, and investment memos — not a handful of search summaries, but a report you can actually use.

> **Current version:** `5.2.0-codex.1` (Codex adaptation; upstream baseline `5.1.0`). `/research-update` performs a read-only comparison and never overwrites local adaptations.
>
> 📂 **Browse all sample reports →** [H33研报· 深度调研报告集](https://www.h33.top)
> — filter, sort, and browse by language and depth.

---

### ✨ At a Glance

<table width="100%">
<tr><td style="white-space: nowrap; width: 1%;"><b>🎯 One command</b></td><td><code>$deep-research &lt;topic&gt;</code> → automated research; <code>/research</code> remains a compatibility entry point</td></tr>
<tr><td style="white-space: nowrap;"><b>⏱ Report in ~10 min</b></td><td>quick mode ~8–12 min, standard ~10–15 min</td></tr>
<tr><td style="white-space: nowrap;"><b>🌍 19 languages</b></td><td>Auto-detects topic language, generates report in the same language</td></tr>
<tr><td style="white-space: nowrap;"><b>🔧 Not OpenCode-exclusive</b></td><td>Adaptable for Claude Code, Cursor, Codex CLI, Windsurf, Cline and more</td></tr>
<tr><td style="white-space: nowrap;"><b>📁 Local file research</b></td><td>Also supports PDF/DOCX/TXT/MD, no internet needed, auto-parsed</td></tr>
<tr><td style="white-space: nowrap;"><b>🖥️ Local report browser</b></td><td>Auto-refreshed after each run<br><code>reports-browser/index.html</code> — report bodies load on click and sanitized HTML is previewed</td></tr>
<tr><td style="white-space: nowrap;"><b>📄 PDF/DOCX export</b></td><td>Export reports as PDF or DOCX from the preview modal — fully client-side, no server required</td></tr>
</table>

<table width="100%">
<tr><th>Command</th><th>Result</th></tr>
<tr><td style="white-space: nowrap;"><code>/research 中国新能源汽车产业发展现状</code></td><td>中文报告</td></tr>
<tr><td><code>/research Competitive landscape of AI cloud computing</code></td><td>English report</td></tr>
<tr><td><code>/research Анализ рынка нефти и газа в России</code></td><td>Отчёт на русском</td></tr>
<tr><td><code>/research 日本のアニメ産業のグローバル市場戦略</code></td><td>日本語レポート</td></tr>
<tr><td><code>/research 한국 반도체 산업의 글로벌 경쟁력 분석</code></td><td>한국어 보고서</td></tr>
<tr><td><code>local file research, see FAQ for prompts</code></td><td>offline mode, read local files</td></tr>
</table>

> It interacts with you entirely in the language you set and searches for materials in that target language — not a simple translation pipeline.

---

## 1. Why You Need This

If you've ever asked AI to do research, you've likely hit these walls:

- Search + summarize → too shallow, just a few bullet points
- Industry reports at $50–500+ each → too expensive for individuals
- Overseas tools → can't search Chinese sources like Baidu Baike, Zhihu, 199IT, iResearch
- AI fabricates numbers → looks reasonable but has no traceable source

This skill follows a **4-stage pipeline** before delivering a report. Not search-and-dump — it's analyze → search+verify → write → verify.

## 2. Who It's For

**Indie developers**, **independent researchers**, **small teams**.
People who need professional-grade research capabilities without relying on paid databases or research institutions.

## 3. Typical Output (Standard Mode)

| Metric | Data (standard mode example) |
|--------|------------------------------|
| Report length | 500-700 lines / ~12,000-20,000 chars (varies by language) |
| Data tables | 15-25, covering market size, competitive landscape, technical specs |
| Analysis paragraphs | 80-120 (each with conclusion + data + causation + judgment) |
| Unique sources cited | 15-25 (Chinese and international institutions) |
| Opposing viewpoints | 3-8, at least one controversy per chapter |
| Data collection | ~1-3 min |
| Report generation | ~8-15 min |
| Total time | ~10-20 min |

> Above ranges for standard mode. Actual times vary by topic complexity and data availability.

### 📖 Featured Reports

| Report | Tags |
|--------|------|
| <a href="reports/en/Global AI Chip Market Landscape and Competitive Dynamics 2026-20260609-170008.md" target="_blank">Global AI Chip Market Landscape and Competitive Dynamics 2026</a> | AI · Semiconductors |
| <a href="reports/en/The Feasibility of Mars Colonization- Radiation, Water Ice, Terraforming, and Global Mission Plans-20260612-163636.md" target="_blank">The Feasibility of Mars Colonization</a> | Space · Technology |
| <a href="reports/en/Electric Vehicle Battery Supply Chain and Raw Material Geopolitics 2026-20260609-171947.md" target="_blank">Electric Vehicle Battery Supply Chain and Raw Material Geopolitics 2026</a> | Energy · Geopolitics |
| <a href="reports/en/GenAI Enterprise Adoption Trends & ROI Measurement in 2026-20260609-174525.md" target="_blank">GenAI Enterprise Adoption Trends & ROI Measurement in 2026</a> | AI · Enterprise |
| <a href="reports/en/Cross-border E-commerce Logistics Trends in Southeast Asia 2026-20260609-165623.md" target="_blank">Cross-border E-commerce Logistics Trends in Southeast Asia 2026</a> | E-commerce · Logistics |

Click a report title to open and read it in a new window.

## 4. Cost

| Component | Cost |
|-----------|------|
| **LLM (already using)** | **DeepSeek v4 Flash** baseline: quick ~100–150k tokens / < $0.03, standard ~150–300k / < $0.06, deep ~300–500k / < $0.10 |
| **SearXNG search (author-deployed)** | Deployed on VPS, zero cost, unlimited usage |
| **Scrapling fetching** | Runs locally, zero cost |
| **Domestic sources** | Direct connection, zero cost, no proxy needed |
| **OpenCode runtime** | MIT open source, zero cost |

> Estimates based on DeepSeek v4 Flash ($0.14/1M input, $0.28/1M output, source: `https://api-docs.deepseek.com/quick_start/pricing`). Actual costs vary by cache hit rate and topic complexity.

## 5. How It Works

The pipeline runs in 4 automated stages:

```
① Analyze outline — Analyze topic, generate research framework and search plan
         ↓
② Collect data — ╭─ Online: structured SearXNG search → bounded queue → standard fetch → dynamic retry for failures
                  ├─ Mixed: online sources + local PDF/DOCX/TXT/MD
                  ╰─ Offline: local files only
         ↓
③ Parallel writing — All chapters write concurrently when agents are available; facts are embedded and chapter agents call no tools
         ↓
④ Validate & assemble — Batch validate → assemble → confidence/citations → refresh metadata → QA
```


## 6. Search Pipeline & Built-in Resources

Search and fetching use a bounded, resumable pipeline:

```
One main query per question; one counter or site: query for high-priority questions
  ↓ concurrent SearXNG search
one fallback only for insufficient questions + sources.json authority ranking/template fallback + bounded deduplication
  ↓
Scrapling standard fetch (up to 6 concurrent)
  ↓ failed URLs only
Dynamic browser fetch (up to 2 concurrent)
```

Every batch is persisted to `task2-progress.json`. Resumed runs skip successful URLs, and each URL receives at most one standard and one dynamic attempt.

## 7. Report Highlights

| Dimension | Description |
|-----------|-------------|
| **Multilingual native writing** | Auto-detects topic language, writes directly in 19 languages, no translation pipeline |
| **Every number has a source** | `(N)` clickable citations in text, full reference list at end. No source = no number |
| **Pros and cons coexist** | Every chapter presents controversies and opposing views |
| **Confidence grading** | Final summary table (high/medium/low) shows what's reliable vs. disputed |
| **Data anti-pitfall** | Auto-detects common data errors — wrong units, fabricated trends, misattributed sources |
| **Paragraphs over padding** | `profiles.json` defines enforceable paragraph/table minima; whitespace cannot pad a chapter |

## 8. Three Depth Modes

| Command | Purpose | Min chapters | Min paragraphs/chapter | Target chars | Est. time |
|---------|---------|-------------|----------------------|--------------|-----------|
| `$deep-research <topic>` | standard (default) | 8 | ≥ 5 | ≈ 25,000 | ~10–15 min |
| `$deep-research <topic> -quick` | Quick insight | 5 | ≥ 4 | ≈ 15,000 | ~8–12 min |
| `$deep-research <topic> -deep` | Maximum depth | 10 | ≥ 6 | ≈ 45,000 | ~15–25 min |

> Parameters in `profiles.json`, restart to apply. Char count excludes whitespace and Markdown syntax.

## 9. Installation

### 🧠 Method 1: AI Auto-Install (Recommended)

Copy this prompt into OpenCode chat, the AI will do everything automatically:

```text
Please read the https://github.com/hoolulu/deep-research project and follow the documentation to:
1. Install prerequisites (determine method based on Scrapling docs and your OS)
2. Register the Scrapling MCP Server, verify it works after CLI restart
3. Register the /research and /research-update commands
Confirm each step, then read VERSION and summarize the installation status.
```

The AI reads the docs → understands your system → installs step by step → verifies. No manual commands needed.

### 🔧 Method 2: Non-OpenCode Users (Claude Code / Codex CLI / Cursor etc.)

Paste this into your AI coding tool:

```text
Please read the https://github.com/hoolulu/deep-research project, auto-install prerequisites and adapt for the current CLI tool:
1. Install Python and Scrapling (refer to Scrapling docs and your system)
2. Register Scrapling MCP Server, verify after restart
3. Register equivalent entry points for /research and /research-update based on the current tool's capabilities:
   - **Codex CLI** → Register as a skill (the `command/` directory already contains command files; registration activates them)
   - **Claude Code** → Register as a slash command (Hook)
   - **Cursor** → Adapt per platform (custom commands / Agent rules)
   - Other tools: check for skill/command mechanisms first, then pick the best fit
4. Translate the multi-agent chain architecture (outline → data collection → parallel writing → assembly+QA) to the current tool's equivalent
5. If multiple CLI tools are installed, only configure the current tool — do not affect other CLI tools on this machine.

Confirm each step, then read VERSION and summarize.
```

Adaptation notes: Multi-agent orchestration needs to map to each platform's native mechanisms (Claude Code's sub-agent, Codex CLI's agent/skill mode, Cursor's agent mode, etc.). Entry point registration also varies by tool (OpenCode/Codex CLI use skills, Claude Code uses Hooks/commands, Cursor uses custom instructions). Search and scraping logic (python-scrapling + search API) can be reused as-is.

### Prerequisites

| Component | Online mode | Offline mode | How to get |
|-----------|:-----------:|:------------:|------------|
| **LLM runtime** (OpenCode / Claude Code / Codex CLI / Cursor etc.) | ✅ Required | ✅ Required | Pick your preferred tool |
| **Scrapling** | ✅ Required | ❌ Not needed | For web scraping; offline mode doesn't need it |
| **SearXNG** (author-deployed, 70+ engines) | ✅ Used | ❌ Not needed | Built-in endpoint, ready out of the box |

> **Platform note**: OpenCode has native multi-agent orchestration (Task 1-4 architecture) — no additional plugins needed. Other tools (Claude Code, Cursor, Codex CLI) have their own native multi-agent frameworks and can adapt this skill's workflow directly. Offline mode only needs the LLM's file-reading capability — no search/scraping components required.

## 10. Usage

After installation and restart, type in the chat:

| Command | Description | Est. time |
|---------|-------------|-----------|
| `$deep-research <topic>` | standard mode (online search) | ~10-15 min |
| `$deep-research <topic> -quick` | quick mode (online search) | ~8-12 min |
| `$deep-research <topic> -deep` | deep mode (online search) | ~15-25 min |
| `local file research` | offline mode (local files) | depends on file size |
| `/research-update` | Check for updates | — |

> Local file research: see FAQ §2 "How to use local materials for report generation?" for exact prompts.

### What Happens After You Send It

The entire pipeline runs automatically — you don't need to do anything:

```
① Analyze outline — Analyze topic, generate framework and search plan
② Collect data — Structured SearXNG search → bounded fetch queue → standard/dynamic Scrapling fetch → resumable data pool → strict checks
③ Parallel writing — All chapters simultaneously, facts embedded in prompts
④ Validate & assemble — Batch validate → assemble → citations → QA
```

> Total ~10-20 minutes. Complex topics may take longer, simple ones may be faster.

### Output Files

Reports are saved as Markdown files in the skill's `reports/` directory, with date-timestamped filenames:

```
{workspace}/.agents/skills/deep-research/reports/
```

Open with any Markdown reader (Typora / Obsidian / VS Code etc.).

You can also specify a custom output path — ask AI to configure it.

**Local report browser page**: Each run refreshes `reports-browser/index.html` and `reports-browser/data/`. It works over `file://`; report bodies load only when clicked and are sanitized with DOMPurify before preview.

## 11. FAQ

**1. Search quotas? How to ensure uninterrupted searching?**

The system uses **SearXNG + authority ranking + resumable Scrapling fetching**:

- `search-outline` creates main, counter, and `site:` queries from the outline and sends them concurrently to `SEARXNG_URL`.
- `sources.json` ranks authoritative domains; it is not scraped as a set of search result pages.
- `profiles.json` bounds candidates and fetches per question. Search outages are recorded explicitly rather than described as impossible.
- Only failed standard fetches move to a dynamic browser. If MCP has not loaded, the CLI fallback uses the same Scrapling implementation; restarting Codex restores direct MCP tools.

**2. How to use local materials for report generation?**

The skill supports offline and mixed modes with **MD / TXT / PDF / DOCX**. `pypdf` and `python-docx` are pinned in `requirements.lock`; no dependency is installed during a research run.

Choose your scenario:

**Scenario 1: Local materials + online supplement** (recommended for most complete research)
```
Use the deep-research skill with my local files in D:\notes\projectA to generate a research report on XX (quick mode). Prioritize local content, search online for anything missing.
```

**Scenario 2: Local materials only, no internet** (when you have sufficient data and don't want online distractions)
```
Use the deep-research skill with my local files in D:\notes\projectA to generate a research report on XX (quick mode). Use only local materials, do not search online.
```
The system skips the search/scraping pipeline and reads local files directly. Task 3 (chapter writing) and Task 4 (assembly/QA) run normally. The final output includes metadata, `[N]` citations, and TOC.

**Scenario 3: Pure local, no skill** (lightweight, no professional format needed)
```
Help me organize the materials in D:\notes\projectA into a structured research report with table of contents and chapter headings.
```

> **Scenario guide**: Incomplete materials → Scenario 1 (online supplement); Sufficient materials + need professional format → Scenario 2 (offline mode); Quick summary only → Scenario 3 (lightweight).

**3. How to update to the latest version?**

This local version contains Codex, MCP, security, and resume adaptations and must not be replaced with a blind `git pull`. `/research-update` shallow-clones upstream into a temporary directory and reports version/file differences. Upstream changes are migrated only in a separate task after the user reviews the diff and explicitly approves the update.

**4. Can non-OpenCode users check upstream changes?**

Yes. Ask the AI for a read-only comparison first:

```text
Compare the latest https://github.com/hoolulu/deep-research with your local version,
identify new features, fixes, and conflicts,
then stop before changing files.
Preserve platform-specific changes in any later migration.
If multiple CLI tools are installed, only configure the current tool — do not affect other CLI tools on this machine.
```

**5. Is my data safe?**

Offline document extraction, report generation, and browser preview run locally. Online and mixed modes send search queries to the configured SearXNG service and request candidate websites; local files are not uploaded to either. Whether model context is sent to a hosted LLM depends on the user's Codex/model deployment.

**6. How do I view my generated reports?**

After each research run, the AI outputs both the report file path and the local report browser page path.

- **Report file**: `{SKILLDIR}/reports/{LANG}/xxx.md` — open with any Markdown reader
- **Local report browser page**: `{SKILLDIR}/reports-browser/index.html` — works with `file://`; lazy report payloads live under `reports-browser/data/`

You can also manually refresh the browser page anytime by running `python tools/generate_pages.py --local` in the skill directory.

## 12. Screenshot

<img width="1532" height="836" alt="Screenshot 2026-06-09 at 11-28-17" src="https://github.com/user-attachments/assets/736b0113-f054-4dba-b018-e656a51a9fb4" />

<img width="1532" height="932" alt="Screenshot 2026-06-09 at 11-30-13" src="https://github.com/user-attachments/assets/a88cbf27-7b6c-4ea3-8b51-424f48bf9906" />

<img width="1524" height="846" alt="Screenshot 2026-06-09 at 11-30-55" src="https://github.com/user-attachments/assets/ef10865d-3a72-4658-ac9c-28b2221e77f5" />

<img width="1528" height="840" alt="Screenshot 2026-06-09 at 11-32-13" src="https://github.com/user-attachments/assets/506e91eb-1d5d-4312-aceb-9280d357e264" />

<img width="1438" height="842" alt="Screenshot 2026-06-09 at 11-35-03" src="https://github.com/user-attachments/assets/75acd450-9349-4024-923d-f9b14ea601dd" />

## License

MIT

This project uses MIT instead of GPL/CC because its core value is a portable methodology and pipeline design, not a copyrighted product. MIT maximizes reuse and adaptation across different platforms and toolchains, consistent with the "not platform-exclusive" positioning.

---

**Created by [hoolulu](https://github.com/hoolulu)** · Repo: [github.com/hoolulu/deep-research](https://github.com/hoolulu/deep-research)

> Community discussion: [LINUX DO](https://linux.do/t/topic/2312664)
