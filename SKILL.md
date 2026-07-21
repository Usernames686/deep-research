---
name: deep-research
description: "Professional deep research report generation for Codex — use when the user asks for deep research, /research-style reports, industry or policy analysis, competitor scans, trend research, literature-informed reports, multilingual research reports, quick/standard/deep research modes, or updates to this deep-research skill. Runs an outline → data collection → parallel chapter writing → assembly and QA workflow with latest-data targeting and built-in checks."
---


# deep-research

生成对标券商/第三方研究机构标准的深度调研报告。

- **架构**：Codex 主 agent 调度 4 个阶段（大纲/数据/并行章节/装配 QA）。如当前 Codex 环境提供子 agent/后台任务能力，Task 1、Task 2 和 Task 3 章节撰写使用子 agent；否则由主 agent 按同一文件契约顺序执行。中间数据走临时文件
- **数据源**：在线模式 → 结构化 SearXNG 搜索（含建议源定向查询、sources.json 权威域名排序与覆盖不足时的一次有界兜底）→ 有界 Scrapling 批量抓取 → 失败 URL 单独升级为浏览器抓取；离线模式 → 用户指定的本地文件（md/txt/pdf/docx）
- **安装**：见下方「安装与配置」
- **Codex 入口**：仓库级 Skill 安装在 `.agents/skills/deep-research` 后自动被 Codex 发现。等价用法是 `$deep-research <主题>`，或直接要求“使用 deep-research 调研 <主题>”。`command/research.md` 和 `command/update.md` 保留为兼容命令说明，不配置其他 CLI
- **中间产物**：每次运行使用带安全标记的独立 `$TMPDIR`；搜索、抓取和章节状态均可恢复
- **最终报告**：保存到 skill 目录下的 `reports/`
- **参考文件**：`RULES.md`（硬约束/反模式）、`TYPES.md`（分类标准/编号规范）、**`profiles.json`（三档模式参数，修改后重启软件即全局生效）**
- **容错原则**：调研不因单个来源或 MCP 未重载而阻塞。命令失败先读取具体错误，再按既定兜底路径重试一次；仍失败则保留运行目录并向用户报告，不做无界重试或临时实现。

---

## 0. 支付级质量标准（所有 Task 共用，缺任何一项即降级）

| # | 标准 | 说明 |
|---|------|------|
| 1 | **结论先行** | 每章以 `> 引用格式` 核心判断开头 |
| 2 | **来源可追溯** | 每个数字使用预分配的 `[N]` 引用，装配后转为可点击编号 |
| 3 | **反方视角** | 至少 1 处呈现争议或反对观点 |
| 4 | **三层深度** | 事实层 → 因果层 → 判断层 |
| 5 | **零套话** | 无"近年来""值得注意的是"等填充词 |
| 6 | **标题含判断** | "格局：高度集中"✅ \| "行业概况"❌ |
| 7 | **可自包含** | 首章必须定义核心概念 |
| 8 | **无内部编号** | 正文无任何流程编号，标题自解释 |
| 9 | **时间戳正确** | 文件名和报告尾时间必须 `date` 命令获取 |
| 10 | **目录源自大纲** | 目录从 outline.json 的第一级章节生成，不从正文提取 |
| 11 | **强制目录** | 报告正文前必须包含当前语言对应的目录标题及自动目录（TOC），列出所有章节标题 |
| 12 | **元数据完整** | 报告头部必须包含 总字数、阅读时间、数据截至日期（精确到月）、报告生成具体时间（精确到秒）、调研模式、Skill版本 六个字段，用 ` · ` 隔开。另起一行 `> **参考来源**：{主要来源} 等 · 共引用 N 个来源`。报告末尾须附 `## 参考来源`（列出所有引用机构及链接）和 `## 免责声明`。版本号从本 skill 的 VERSION 文件读取。 |
| 13 | **篇幅达标** | 见项目根目录 [`profiles.json`](profiles.json)。所有模式限制以 `profiles.json` 为准，修改后重启软件即全局生效。 |
| 14 | **四段式结构** | 顺序固定为：报告标题 → 元数据块（含六字段 + 参考来源行） → `## 目录` → 正文各章 → 尾部（参考来源 + 免责声明） |
| 15 | **编码洁净** | 所有中间文件（outline.json / data-pool.json / chapter-*.md）必须使用 **UTF-8 无 BOM** 编码写入，不得出现替换字符（\ufffd）或 GBK→UTF-8 Mojibake。子 agent 在写入前必须自行验证编码洁净，不得将编码问题遗留到主 agent |
| 16 | **纯文本公式** | 报告中不得使用 LaTeX/math 公式语法（`$...$`、`$$...$$`、`\[...\]` 等）。公式必须用纯文本或 Unicode 符号表达，确保复制到任何编辑器都不产生渲染问题 |

### 时间锚定规则

所有主题默认以 `{CURRENT_YEAR}` 为目标搜索最新数据。时间锚定模式在 Task 1 中由大纲 agent 按以下规则判定：

| 模式 | 符号 | 判定条件 | target_year | 验收 |
|:----|:-----|:---------|:-----------|:-----|
| `latest`（默认） | ⏳ | **所有主题的默认值**，除非符合 relaxed 或 user_specified | `{CURRENT_YEAR}` | 严格：≥50% 数据来自当年/前一年 |
| `relaxed`（放宽） | 🔓 | 指南/教程/概念类主题，或用户问历史/原理（"草书发展""起源""背景"） | `{CURRENT_YEAR}` | 宽松：标记旧数据但不过滤 |
| `user_specified` | 📌 | 用户提问显式指定了年份/月份（"2025年""2026Q1""2020年至今"） | **用户的指定年份** | 硬约束：>50% 匹配用户指定时间 |

> `{CURRENT_YEAR}` 是动态变量，运行时通过 `date +%Y` 解析，无需手动修改。

---

## 1. 主 agent 调度流程

**⚠️ CRITICAL — DO NOT SPEAK BEFORE LANGUAGE DETECTION**
> Your VERY FIRST action (before anything else) must be: detect language → set `$LANG`.
> Output NOTHING to the user until `$LANG` is set — no thinking aloud, no status messages.
> After language is detected, ALL output must be in `$LANG`. Period.
>
> **IMPORTANT: Clean the topic before detection** — the user input may contain framework wrapper text (e.g. "请使用... skill 执行...用户输入如下："). Strip all wrapper text and pass ONLY the clean research topic. For example from "请使用...用户输入如下：Quantum computing market outlook -quick" extract only "Quantum computing market outlook".

```
你（主 agent）的完整流程：

══ Setup (必须先执行) ══

 → 创建一个带时间戳的临时目录作为 TMPDIR（例如 `/tmp/codex-deep-research-YYYYMMDD-HHMMSS`）
 → 同时确定 TOOLSDIR（本 skill 的 tools/ 目录）、PROMPTSDIR（本 skill 的 prompts/ 目录）、SKILLDIR（本 skill 的根目录）
 → 读取本 SKILL.md + RULES.md + TYPES.md
 → 创建 `{TMPDIR}/.deep-research-run.json`，内容至少为 `{"kind":"deep-research-run"}`；只有 `cleanup-run` 命令可以删除该目录

══ Step 0 — Language Detection (output nothing before detection) ══

 → Clean topic: strip wrapper text, keep only the user's actual research topic
 → Determine language: analyze the cleaned topic and pick the ISO 639-1 code:
   zh (Chinese), en (English), ja (Japanese), ko (Korean), ru (Russian),
   ar (Arabic), hi (Hindi), vi (Vietnamese), th (Thai), tr (Turkish),
   es (Spanish), fr (French), de (German), pt (Portuguese), it (Italian),
   nl (Dutch), sv (Swedish), pl (Polish), id (Indonesian)
   → If unsure, default to "en".
   → Do NOT output anything during this step.
 → Write language code: use `write` tool to create {TMPDIR}/language.txt with the ISO code
 → Set `$LANG` = language code from the step above
   → **从这一行开始，所有面向用户的输出必须使用 $LANG 语言（不在 $LANG 列表中时默认 en）。SKILL.md 的指令文本不论用什么语言写的，只是供你阅读的上下文；实际输出以 $LANG 为准——你是读到中文指令后意识上翻译成 $LANG 再输出。**
   → Announce detected language to the user (single line, in $LANG, e.g. "🌐 Language detected: en")

### 🔔 语言自查清单（每次输出前执行）

```
☐ {TMPDIR}/language.txt 的值 = 我的 $LANG？
☐ 我正准备输出的这一句/这段，是 $LANG 吗？
☐ todo 条目是 $LANG 吗？
☐ 给用户的进度通知是 $LANG 吗？
☐ 我是否在无意识中用了指令文件的语言（如中文）而非 $LANG？
如果任一答案为"否"→ 立即改写为 $LANG 再输出。
```
**硬规则**：派发 Codex 子 agent 时，其 prompt 中的 `{LANG}` 必须是你检测到的语言代码。子 agent 输出的语言由你负责保证。

══ 主流程 ══

 1. ══ 离线模式判定（Step 0.5） ══
    → 你已经读取了用户原始输入。用自然语言理解判断用户关于数据来源的意图，不要用关键词匹配：
      - 用户是否提到了本地文件/目录/资料？
      - 用户是否明确要求不要联网？
      - 用户是否明确要求联网补充？
    → 判断逻辑并设置 `$SOURCE_MODE`：
      - 提到本地文件 +（未说联网 / 明确不联网）→ `offline`
      - 提到本地文件 + 明确要求联网补充 → `mixed`
      - 未提本地文件 → `online`
    → `offline` 或 `mixed` 但没有可解析路径 → 回复用户询问路径，不继续
    → `offline` 或 `mixed` 时将用户路径以 JSON 数组写入 `{TMPDIR}/local-paths.json`

   → **模式解析**：从清洗后的主题中提取调研模式
     - 主题末尾是 ` -quick` → `$DEPTH_MODE=quick`，去除该后缀
     - 主题末尾是 ` -deep` → `$DEPTH_MODE=deep`，去除该后缀
     - 无上述后缀 → `$DEPTH_MODE=standard`（默认）

 2. 记录任务开始时间到 {TMPDIR}/start_time.txt
 3. 使用 Codex 计划工具创建进度条目（使用 $LANG 语言）；如当前环境没有计划工具，用简短进度消息代替
  4. ══ Task 1 — 分析主题 + 生成大纲 ══
     → 读取 {PROMPTSDIR}/task1_outline.md，替换 {TMPDIR} {TOOLSDIR} {SKILLDIR} {LANG} {CURRENT_YEAR} {MODE}，注入 prompt
     → **只做变量替换，不添加语言、格式、报告结构等额外指令。语言已由 Step 0 判定为 $LANG 并在 prompt 中替换 {LANG}。**
     → 优先派发一个 Codex 子 agent 执行，等待完成；如当前环境没有子 agent 工具，主 agent 直接执行
     → 用 `read` 确认 {TMPDIR}/outline.json 存在
     → 执行 `python {TOOLSDIR}/dr_tools.py check-outline {TMPDIR}/outline.json --mode {DEPTH_MODE}`；失败时把具体问题反馈给大纲 agent 并只重试一次
     → 从 outline.json 读取 title + chapter_count + depth_mode
    → 标记计划项完成
    → 向用户报告进度（使用 $LANG 语言）
  6. ══ Task 2 — 数据发现、抓取与结构化数据池 ══
     → **Task 2A（发现）**：读取 `{PROMPTSDIR}/task2_discovery.md`，替换 `{TMPDIR}` `{TOOLSDIR}` `{SKILLDIR}` `{LANG}` `{MODE}` `{SOURCE_MODE}` 后执行
     → Task 2A 在线输出 `search-results.json`、`fetch-queue.json`、`task2-progress.json`；离线输出 `local-files.json`
     → **Task 2B（收集）**：读取 `{PROMPTSDIR}/task2_data_collection.md`，替换同一组变量后执行；抓取状态每批落盘，中断时从 `task2-progress.json` 继续
     → 两个子阶段分别只允许自动重试 1 次；重试时复用已经通过验证的文件，不得整阶段重跑
     → 主 agent 执行严格 data-pool 检查和 `check-manifest` 双重验收；第二次仍失败才向用户报告，并保留 TMPDIR 供诊断
     → 读取 {TMPDIR}/task2_manifest.json，提取 source_count + fact_count + search_engine + fetch_method + engines + free_fallback + english_fallback + unique_domains
    → 标记计划项完成
    → 向用户报告进度（使用 $LANG 语言）
     7. ══ Task 3 — 派发章节撰写 ══
     → 读取 {TMPDIR}/outline.json 获取 chapters 数组；读取 {TMPDIR}/data-pool.json
     → **读取 `profiles.json` 获取当前模式的 `max_chars`**，计算 `per_chapter_chars = max_chars ÷ chapters.length`
     → 执行 `generate-citation-map --datapool {TMPDIR}/data-pool.json --output {TMPDIR}/citation_map.json`；引用身份优先使用 URL/本地路径，无 URL 时使用 `(src, yr, title)`
     → 读取 `{PROMPTSDIR}/task3_chapter_agent.md` 模板
     → 替换模板中的章节标题、编号、sections、`{LANG}`、`{per_chapter_chars}`、`{min_paragraphs}`、`{min_tables}`、`{TMPDIR}` 等变量
      → **撰写模式**：所有平台统一使用并行模式撰写章节
        - **章节 agent 不做任何工具调用**（不跑 prepare-chapter、validate、manifest、word-count），只写文件

      → **并行派发章节**：
       - 初始化空列表 task_ids = []
       - For N = 1 to chapters.length:
         - 读取 outline.chapters[N] 的 title、sections
         - 从 data-pool.json 中筛选该章 sub_questions 对应的事实条目
         - **将事实直接嵌入 prompt**：每条事实前标注预分配的 `[N]` 编号
         - 优先调用 Codex 子 agent 并行派出每章；如没有子 agent/后台任务能力，则在主 agent 中按章节顺序执行同一 prompt
         - 从子 agent 返回元数据中提取 agent/task id，追加到 task_ids；顺序兜底时记录章节编号
         - 标记该章 in_progress
       - 将 task_ids 写入 {TMPDIR}/task3_bg_ids.json（持久化，防止主 agent 中断后丢失状态；顺序兜底时写章节编号数组）
       - 向用户报告："已并行派出 {N} 章，等待全部完成..."（使用 $LANG 语言）
       - 若使用后台子 agent，等待全部完成后继续 Round 2；中间的单章完成通知只记录状态，不提前装配。
       - 然后进入 Round 2：

       **Round 2 — 收集结果 + 失败重写**：
       - 读取 {TMPDIR}/task3_bg_ids.json 获取所有 agent/task id 或顺序兜底章节编号
       - For 每个 bg_task_id in task_ids:
         - 调用当前 Codex 环境的子 agent 结果收集工具，或读取顺序兜底已写出的章节文件
       - 用 `read` 逐一确认 {TMPDIR}/chapters/chapter-{N}.md 是否存在且非空
       - 如果有章节缺失或内容为空：
         - 记录失败章节编号列表
         - **串行重写**：对每个失败章节逐一重新派发子 agent 或由主 agent 同步重写
         - 再次用 `read` 确认
       - 标记每章 completed
       - 向用户报告最终章节完成情况（使用 $LANG 语言）
     8. ══ Task 4 — 验证 + 装配 + QA（**主 agent 直接执行**） ══
     → **Step 0 — 准备输出**：创建 {SKILLDIR}/reports/$LANG/ 子目录（如果不存在）；不扫描或删除历史报告
     → **Step 1 — 批量验证**：`python {TOOLSDIR}/dr_tools.py validate-all-chapters --chapters-dir {TMPDIR}/chapters/ --outline {TMPDIR}/outline.json --mode {depth_mode} --lang $LANG`，内部 ThreadPoolExecutor 并行验证所有章节。从输出 JSON 的 `failed_chapters` 中找到失败章节，逐个重新生成（重新派发章节 agent → 重新验证该章）。
     → **Step 1b — 章节深度均衡检查**：`python {TOOLSDIR}/dr_tools.py depth-balance --chapters-dir {TMPDIR}/chapters/ --chapters {chapter_count}`。如果某章行数 < 平均值的 50%，标记告警（not blocking，仅提示）。
     → Step 1 失败时只重写失败章节；Step 2 失败时保留全部中间文件并修复具体问题，不做目录级删除
     → **Step 2 — 装配**：`python {TOOLSDIR}/dr_tools.py assemble-report --outline {TMPDIR}/outline.json --chapters-dir {TMPDIR}/chapters/ --datapool {TMPDIR}/data-pool.json --mode {depth_mode} --target-year {target_year} --output {SKILLDIR}/reports/$LANG/ --lang $LANG`
    → **$REPORT 提取**：从装配输出中提取 `Report assembled: ...` 行中冒号后的第一个路径，设为 `$REPORT` 变量
     → **Step 2b — 可信评估(数据层)**：`python {TOOLSDIR}/dr_tools.py generate-confidence-section --datapool {TMPDIR}/data-pool.json --manifest {TMPDIR}/task2_manifest.json --report "$REPORT" --lang $LANG`
       从输出中解析 `CONFIDENCE:` 行获取 `conf_coverage`、`conf_total_facts`、`conf_high_pct`、`conf_medium_pct`、`conf_low_pct`、`conf_actual_pct`、`conf_est_pct`、`conf_fct_pct`、`conf_auth_pct`、`conf_data_limited`、`conf_controversies`、`conf_adequate_subq`、`conf_total_subq`、`conf_score` 共 14 个变量。
     → **Step 2c — 可信评估(LLM判断)**：使用上一步的 14 个统计变量 + 报告标题（从 outline.json 读取）在 LLM 上下文内直接生成定性评估意见。
        - 输出必须使用 $LANG 语言，2-4 句，纯定性判断，不重复逐项明细中的具体数字
        - **语气校准（重要）**：本工具是开源信息综合项目，非付费研究报告。评估意见应遵循以下原则：
          - **总分决定基调**：score≥75 → 正面肯定为主；50-74 → 中性平衡；<50 → 温和提醒
          - **不说"缺陷""不足""未能"等负面措辞** → 改为"可进一步关注的方面""仍有补充空间"
          - **不说"无法获取""受限于"** → 改为"部分高频量化指标因商业敏感性未纳入公开讨论范围"
          - **不自我贬低**：不出现"门槛高""可信度大打折扣"等损害报告公信力的表述
          - **正面收尾**：最后一句必须是肯定整体参考价值的结论
          - **定位准确**：强调"综合公开信息形成的参考判断"而非"严谨学术研究"
        - 写出到 `{TMPDIR}/llm_assessment.txt`
        - 用 `edit` 工具将评估意见插入到报告可信评估区的 `**{综合评级标签}**` 行之后（追加 "**{评估意见标签}**：\n\n{文本}"），然后用 `read` 确认插入正确
        - `{综合评级标签}` 和 `{评估意见标签}` 使用语言映射表中的翻译
     → **Step 3 — 数据受限处理**：读取 {TMPDIR}/task2_manifest.json 的 `data_limited` 字段。如果为 true，在报告标题后插入数据说明声明，**使用 $LANG 语言**。
    → **Step 4 — 引用处理**：`python {TOOLSDIR}/dr_tools.py convert-citations --datapool {TMPDIR}/data-pool.json "$REPORT" --lang $LANG`（从 data-pool 构建参考章节，验证正文 `[N]` 引用均有对应条目）
    → **Step 4b — 货币符号转义**：`python {TOOLSDIR}/dr_tools.py escape-currency "$REPORT"`（将 `$` 转义为 `\$`，避免被知乎/Obsidian/Typora 等渲染器错误解析为 LaTeX math mode）
    → **Step 4c — 元数据收敛**：`python {TOOLSDIR}/dr_tools.py refresh-metadata "$REPORT" --datapool {TMPDIR}/data-pool.json --lang $LANG`
      → **Step 5 — QA**：`python {TOOLSDIR}/dr_tools.py qa-report "$REPORT" --mode {depth_mode} --target-year {target_year} --time-anchor {time_anchor.mode} --lang $LANG`，解析 JSON 输出，从 `checks.word_count.count` 取字数，从 `checks.word_count.limit` 取上限
     → **Step 6 — 更新本地报告列表页**：`python {TOOLSDIR}/generate_pages.py --local`（刷新 `reports-browser/index.html` 与按报告拆分的懒加载数据文件）——需在 `{SKILLDIR}` 目录下执行
     → QA 与浏览器索引刷新均成功后执行 `python {TOOLSDIR}/dr_tools.py cleanup-run --tmpdir {TMPDIR}`；任一步失败则保留 TMPDIR 供恢复
     → 标记计划项完成
    → ⏱ **强制计算总耗时**（读取 start_time.txt + 当前时间算差值）
    → 从 outline.json + task2_manifest.json + qa-report 中提取数据，使用 $LANG 语言汇报最终结果。

      **语言自适应标签映射表**（以下所有 <词> 根据 $LANG 替换）：

      | 中文 | en | ja | ko | fr | de | es | 其余语言 |
      |------|----|----|----|----|----|----|---------|
      | 执行总结 | Execution Summary | 実行サマリー | 실행 요약 | Résumé exécutif | Zusammenfassung | Resumen ejecutivo | Execution Summary |
      | 阶段 | Stage | 段階 | 단계 | Phase | Phase | Fase | Stage |
      | 详情 | Detail | 詳細 | 세부 | Détail | Detail | Detalle | Detail |
      | 大纲/Plan | Plan | 概要 | 개요 | Plan | Plan | Plan | Plan |
      | 观点速览/Insight | Insight | 洞察 | 인사이트 | Aperçu | Einblick | Perspectiva | Insight |
      | 数据/Data | Data | データ | 데이터 | Données | Daten | Datos | Data |
      | 报告/Report | Report | レポート | 보고서 | Rapport | Bericht | Informe | Report |
      | 章 | ch | 章 | 장 | chap. | Kap. | cap. | ch |
      | 来源 | sources | ソース | 출처 | sources | Quellen | fuentes | sources |
      | 事实 | facts | 事実 | 사실 | faits | Fakten | datos | facts |
      | 独立域名 | domains | ドメイン | 도메인 | domaines | Domains | dominios | domains |
| 行 | lines | 行 | 줄 | lignes | Zeilen | líneas | lines |
| 字 | chars | 語 | 단어 | mots | Wörter | palabras | chars |
      | 分钟 | min | 分 | 분 | min | Min. | min | min |
      | 生成时间 | Generated | 生成時刻 | 생성 시간 | Généré le | Erzeugt | Generado | Generated |
      | 搜索 | Search | 検索 | 검색 | Recherche | Suche | Búsqueda | Search |
| 数据充足 | Adequate | 十分 | 충분 | Suffisantes | Ausreichend | Adecuado | Adequate |
| 数据受限 ⚠ | Limited ⚠ | 制限 ⚠ | 제한 ⚠ | Limitées ⚠ | Eingeschränkt ⚠ | Limitado ⚠ | Limited ⚠ |
| 可信评估 | Confidence | 信頼性評価 | 신뢰도 평가 | Évaluation de confiance | Vertrauensbewertung | Evaluación de confianza | Confidence |
| 覆盖充足/部分覆盖/覆盖不足 | Full/Partial/Limited coverage | 完全/部分/不足カバー | 충분/부분/부족 | Couverture complète/partielle/limitée | Vollständige/Teilweise/Eingeschränkte Abdeckung | Cobertura completa/parcial/limitada | Adequate/Partial/Limited |
| 统计 | Stats | 統計 | 통계 | Statistiques | Statistiken | Estadísticas | Stats |
| 综合评级 | Rating | 総合評価 | 종합 평가 | Note globale | Gesamtbewertung | Calificación general | Rating |
| 评估意见 | Assessment | 評価意見 | 평가 의견 | Avis d'évaluation | Bewertung | Opinión de evaluación | Assessment |
| 耗时 | Duration | 所要時間 | 소요 시간 | Durée | Dauer | Duración | Duration |
      | 免费源补强 | free fallback | 無料補強 | 무료 보강 | sources gratuites | kostenlose Quellen | fuentes gratuitas | free fallback |
      | 本地文件 | local files | ローカル | 로컬 파일 | fichiers locaux | lokale Dateien | archivos locales | local files |

      **搜索策略描述拼接规则**（使用映射表中的翻译）：

      ```
      IF SOURCE_MODE=offline:
        <搜索词>：{offline_$LANG}
      ELSE IF SOURCE_MODE=mixed:
        desc = engines_names + " + " + <本地文件词>
      ELSE:
        engines_names = engines 数组元素大写（["searxng"] → "SearXNG"）
        desc = engines_names
        IF free_fallback=true: desc += " (+{free_fallback_$LANG})"
        IF english_fallback=true: desc += " (+EN)"
        <搜索词>：{desc}
      ```

      **数据质量徽标规则**：

      ```
      IF data_limited=true: <质量词> = {limited_$LANG}
      ELSE: <质量词> = {adequate_$LANG}
      ```

      严格按以下结构输出：

      ```
      📊 **<执行总结词>**

      | <阶段词> | <详情词> |
      |:----|:------|
      | 📋 <Plan词> | {outline.title} · {outline.chapter_count} <章词> · {outline.depth_mode} |
      | 🎯 <Insight词> | {outline.chapters[0].description} |
       | 📡 <Data词> | {task2_manifest.source_count} <来源词> · {task2_manifest.unique_domains} <独立域名词> · {task2_manifest.fact_count} <事实词> · <搜索词>：{search_desc} · {task2_manifest.fetch_method} |
       | 📄 <Report词> | {REPORT} |
       | 🌐 <浏览器词/Report List> | {SKILLDIR}/reports-browser/index.html |
       | ✅ <可信评估词> | <覆盖_{coverage_summary}> · 高置信{conf_high_pct}% · 已公布{conf_actual_pct}% · {conf_score}/100 · {data_quality_badge} → {llm_verdict} |
       | 📊 <统计词> | {qa_report.line_count} <行词> · {qa_report.word_count} <字词> · <耗时词>⏱ {totalMin} <分钟词> · <生成时间词>：{gen_time} |
      ```

      其中：
      - `{outline.chapters[0].description}` = 从 outline.json 读取第 1 章（核心观点）的 description 字段，作为观点速览摘要
      - `{gen_time}` = 读取 {TMPDIR}/start_time.txt 中的任务开始时间，格式化为 `YYYY-MM-DD HH:mm:ss`
       - `{REPORT}` 仅输出最终报告路径（`{SKILLDIR}/reports/{LANG}/xxx.md`），不包含任何 TMPDIR 中间路径
      - `{search_desc}` = 按搜索策略拼接规则生成，所有中文词根据 $LANG 翻译
       - `{data_quality_badge}` = 按数据质量徽标规则生成
       - `<覆盖_{coverage_summary}>` = 从 `task2_manifest.coverage_summary` 读取（adequate/partial/insufficient），用语言映射表中"覆盖充足/部分覆盖/覆盖不足"行对应翻译替换
       - `{conf_high_pct}`、`{conf_actual_pct}`、`{conf_score}` = 从 Step 2b 的 `CONFIDENCE:` 行解析对应的字段
       - `{llm_verdict}` = 读取 Step 2c 写入的 `{TMPDIR}/llm_assessment.txt` 完整内容
    → 标记全部完成

**禁止**：主 agent 不得在 Task 调度之间自行执行搜索引擎调用或数据处理。搜索/抓取归 Task 2，大纲生成归 Task 1，章节撰写归 Task 3，装配验证归 Task 4。Task 间的 handoff 文件读取（outline.json、task2_manifest.json 等）不受此限。

---

## 2. 输出文件管理

### 路径优先级

最终报告保存路径按以下优先级判定：

1. **用户自定义路径** — 如果用户显式指定了输出目录（如 `D:\Reports\`），使用指定路径
2. **Skill 默认路径** — `{SKILLDIR}/reports/`（skill 根目录下的 reports/）

装配阶段（Step 3）根据实际使用的路径写入，文件名格式不变：`<主题>-YYYYMMDD-HHmmss.md`。

### QA 路径核验

Step 4 QA 必须确认报告文件的保存路径为上述两者之一，如果路径不属于默认目录且非用户指定目录，标记"路径异常"不通过。

### 日期锚定

文件名中的日期用当前年月日。

### 清理机制

```
Task 4 装配 + QA 通过后，内部已完成清理：
1. 使用 `dr_tools.py cleanup-run --tmpdir {TMPDIR}` 清理已标记的运行目录
2. 确认 tool-output/ 无残留
```

---

## 3. 工具依赖速查

| 工具 | 用途 | 免费？ | 国内源？ |
|:----|:-----|:-----:|:--------:|
| `search-outline` | 结构化 SearXNG 搜索、定向查询、排序与去重 | ✅ | ✅ 由 SearXNG 后端决定 |
| `scrapling_bulk_get/stealthy/fetch` | 全文抓取（Codex MCP，依赖 `.codex/config.toml` 注册并重启 Codex） | ✅ | **✅ 推荐，国内源主力** |
| `fetch-pending` | MCP 尚未加载时复用同一 Scrapling 实现的 CLI 兜底 | ✅ | ✅ |
| `bash` | date 时间戳 / 文件操作 | ✅ | — |
| 文件读写工具 | 创建/读取中间文件和报告 | ✅ | — |

搜索端点由 `SEARXNG_URL` 配置，默认使用项目内置端点。抓取队列和每批结果都会持久化，因此失败升级或任务恢复不会重抓成功 URL。

**搜索链路**：
```
大纲主查询 + high 优先级反方查询 + 建议源 site: 定向查询
         ↓ SearXNG 并发搜索
按建议源、机构属性、sources.json 优先级和时效排序，逐问题去重/限额
         ↓
Scrapling 标准批量抓取（6 并发）
    ├─ 成功 → 立即落盘并标记 success
    └─ 失败 → 仅失败 URL 使用动态浏览器抓取（最多 2 并发）
         ↓
严格 data-pool + manifest 验收
```

---

## 4. 安装与配置

### 前置条件

- Python 3.10+
- Scrapling（安装方式由 AI 根据官方文档和当前系统自动适配）
- Playwright（可选，用于 JS 渲染和反检测抓取）

### 注册 Scrapling MCP Server

Scrapling 通过 MCP（Model Context Protocol）与 Codex 通信，需注册到当前仓库的 `.codex/config.toml` 后才能被 agent 调用。

**当前 Codex 适配方式**：本工作区使用 Skill 私有 `.venv` 安装 Python 3.12、Scrapling 和 MCP SDK，并在 `.codex/config.toml` 注册 `scrapling` stdio server。注册后需要重启 Codex/CLI 才会加载到新会话。

**参考实现**：本项目提供了 `scrapling-mcp-server.py`（与本文件同目录），覆盖标准抓取、反检测抓取、JS 渲染抓取三种模式。该 Codex 版本限制 URL scheme、localhost/私网 IP、批量数量、超时和单条内容长度；如企业内网调研确需访问私网，显式设置 `SCRAPLING_MCP_ALLOW_PRIVATE=1`。

启用严格 DNS 时，如果本机代理将公网域名映射到专用 Fake-IP 网段，可通过 `SCRAPLING_MCP_ALLOWED_RESOLVED_CIDRS` 显式允许该解析网段（逗号分隔 CIDR）。此例外只应用于域名的 DNS 结果，直接请求保留/私网 IP 仍会被拒绝；不要填写真实内网网段。

**Codex 项目级注册格式**（`.codex/config.toml`）：
  ```toml
  [mcp_servers.scrapling]
  command = "<skill-dir>/.venv/bin/python"
  args = ["<skill-dir>/scrapling-mcp-server.py"]
  cwd = "<skill-dir>"
  enabled = true
  ```
  > 注意：这是 Codex 配置，不写入 OpenCode、Claude Code、Cursor 或其他 CLI 的配置文件。

### 重启 Codex

MCP Server 在 Codex 启动时加载，注册后**必须重启**当前 Codex CLI/桌面任务/IDE 扩展的新会话才会生效。

### 验证是否生效

运行 `$deep-research <主题>` 时，如果 Task 2 直接调用 `scrapling_bulk_get`，说明 MCP 已加载；如果使用 `fetch-pending`，说明源码和依赖可用，但当前 Codex 会话尚未加载 MCP 配置，重启后可恢复工具直连。

### 抓取回退说明

标准抓取失败的 URL 会单独升级到动态浏览器抓取，不影响已成功项目。MCP 完全不可用时，`fetch-pending` 从 CLI 调用同一套 Scrapling 和 SSRF/超时/内容上限策略；调研不会因 MCP 未重载而阻塞。

---

## 5. 跨平台编码规范（Windows/macOS/Linux）

### 硬性规则（所有 agent 必须遵守）

| # | 规则 | 正确做法 | 错误做法 |
|---|------|---------|---------|
| 1 | **非 ASCII 文本不进 shell argv/pipe** | 用 `write` 工具写文件 → Python `--file` 读取 | Python 脚本 argv 传非 ASCII 文本 ❌ |
| 2 | **所有文件读写用 UTF-8** | Python 统一 `encoding='utf-8-sig'`（BOM 容错） | 依赖 shell 编码 |
| 3 | **写文件只用 `write` 工具** | `write` 工具 → UTF-8 无 BOM | PowerShell `Set-Content -Encoding UTF8` ❌（会加 BOM） |
| 4 | **Python stdout 显式设 UTF-8** | `sys.stdout.reconfigure(encoding='utf-8')` | 依赖系统默认编码 |
| 5 | **Python 子进程输出用 `--output` 文件** | `python script.py --input file --output result` | shell 重定向 `> result.txt` ❌（可能受控制台编码影响） |

所有工具读取使用 `utf-8-sig` 容错，写入使用 UTF-8 无 BOM 与原子替换；最终仍由 `check-encoding` 验收。

---

**Created by [hoolulu](https://github.com/hoolulu)** · [github.com/hoolulu/deep-research](https://github.com/hoolulu/deep-research)
