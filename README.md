# deep-research Skill

<p align="center"><b>中文</b> · <a href="README_EN.md">English</a></p>

**深度调研报告生成 Skill — 一条命令，十分钟出券商级深度调研报告**

多 Agent 自动搜索、抓取、撰写、质检——输入主题，输出可引用、可浏览、可导出的中文/多语言调研报告。

对标券商/第三方研究机构结构：结论先行、来源可追溯、反方视角、情景预测。支持 quick / standard / deep 三档模式，19 种语言随主题自动切换。

适合行业研究、趋势前瞻、竞品扫描、政策解读、技术专题、投研备忘——不是搜几条摘要，是交付一份能拿去用的报告。

> **当前版本：** `5.2.0-codex.1`（Codex 适配版；上游基线 `5.1.0`）。`/research-update` 只做只读差异检查，不自动覆盖本地适配。
>
> 📂 **浏览所有示例报告 →** [H33研报· 深度调研报告集](https://www.h33.top)
> 可筛选、排序、按语言和类型浏览所有示例报告。

---

### ✨ 一分钟看懂


<table width="100%">
<tr><td style="white-space: nowrap; width: 1%;"><b>🎯 一个命令</b></td><td><code>$deep-research 你的主题</code> → 全自动调研；<code>/research</code> 为兼容入口</td></tr>
<tr><td style="white-space: nowrap;"><b>⏱ 十分钟出报告</b></td><td>quick 模式约 8–12 分钟，standard 约 10–15 分钟</td></tr>
<tr><td style="white-space: nowrap;"><b>🌍 19 种语言</b></td><td>主题用什么语言写，报告就用什么语言出，自动检测</td></tr>
<tr><td style="white-space: nowrap;"><b>🔧 非 OpenCode 独占</b></td><td>Claude Code、Cursor、Codex CLI、Windsurf、Cline 等均可适配</td></tr>
<tr><td style="white-space: nowrap;"><b>📁 本地文件调研</b></td><td>也可支持本地 PDF/DOCX/TXT/MD，不联网，AI 自动解析</td></tr>
<tr><td style="white-space: nowrap;"><b>🖥️ 本地报告浏览页</b></td><td>每次报告生成后自动刷新<br><code>reports-browser/index.html</code>，正文按点击加载并经过 HTML 清洗</td></tr>
<tr><td style="white-space: nowrap;"><b>📄 PDF/DOCX 导出</b></td><td>本地浏览页弹窗中可导出 PDF、DOCX 格式，浏览器端直接转换下载</td></tr>
</table>



<table width="100%">
<tr><th>命令</th><th>说明</th></tr>
<tr><td style="white-space: nowrap;"><code>/research 中国新能源汽车产业发展现状</code></td><td>中文报告</td></tr>
<tr><td><code>/research Competitive landscape of AI cloud computing</code></td><td>English report</td></tr>
<tr><td><code>/research Анализ рынка нефти и газа в России</code></td><td>Отчёт на русском</td></tr>
<tr><td><code>/research 日本のアニメ産業のグローバル市場戦略</code></td><td>日本語レポート</td></tr>
<tr><td><code>/research 한국 반도체 산업의 글로벌 경쟁력 분석</code></td><td>한국어 보고서</td></tr>
<tr><td><code>本地资料调研，详细命令见 FAQ</code></td><td>离线模式，读本地文件</td></tr>
</table>

> 是全程以设定语言与你交互，并搜索目标语言的资料，不是简单的翻译输出。

---

## 一、为什么你需要这个

让 AI 帮你做调研，你大概率碰过这些坑：

- 搜索 + 总结 → 太浅，出来几条摘要，没有纵深
- 行业报告按份收费 $50–500+ → 太贵，个人用不起
- 海外工具 → 搜不到国内资源如：百度百科、知乎、199IT、艾瑞
- AI 编数字 → 看起来合理，但找不到来源

这个 skill 走完 **4 层流程**才交报告。不是搜完就出，是析→搜验→写→验。

## 二、谁适合用

**独立开发者**、**独立研究者**、**小团队**。
需要专业级调研能力，但不想依赖付费数据库或研究机构的人。

## 三、一次标准模式调研的输出


| 指标      | 数据（standard 模式示例）                           |
| ------- | ------------------------------------------- |
| 报告长度    | 500-700 行 / 约 12,000-20,000 字（视语言浮动）     |
| 数据表     | 15-25 张，覆盖市场规模、竞争格局、技术参数等多个维度               |
| 分析段落    | 80-120 段（每段含结论 + 数据 + 因果 + 判断）              |
| 引用的独立机构 | 15-25 家（中国信通院、艾瑞咨询、国家统计局、百度百科、知乎、36氪、澎湃新闻等） |
| 反方观点    | 3-8 处，每章至少呈现一个争议或反对角度                       |
| 数据收集    | ~1-3 分钟                                     |
| 报告生成    | ~8-15 分钟                                    |
| 总耗时     | ~10-20 分钟                                   |


> 以上为 standard 模式典型范围，实际因主题复杂度、数据可获取性、搜索引擎响应等因素有所浮动。|

### 📖 精选报告展示

| 报告主题 | 话题标签 |
|---------|---------|
| <a href="reports/zh/长江三角洲与珠江三角洲：中国两大经济引擎的地理比较-20260615-112009.md" target="_blank">长江三角洲与珠江三角洲：中国两大经济引擎的地理比较</a> | 地理 · 经济 |
| <a href="reports/zh/郑和下西洋：为什么中国在 15 世纪放弃了海洋？-20260611-154808.md" target="_blank">郑和下西洋：为什么中国在 15 世纪放弃了海洋？</a> | 历史 · 航海 |
| <a href="reports/zh/玛雅文明崩溃之谜：干旱、战争还是生态超载？-20260612-105436.md" target="_blank">玛雅文明崩溃之谜：干旱、战争还是生态超载？</a> | 历史 · 文明 |
| <a href="reports/zh/2026年中国新能源汽车行业展望-20260606-223210.md" target="_blank">2026年中国新能源汽车行业展望</a> | 汽车 · 产业 |
| <a href="reports/zh/火星移民的工程现实：从 SpaceX 到 ISRU 到辐射防护-20260611-164652.md" target="_blank">火星移民的工程现实：从 SpaceX 到 ISRU 到辐射防护</a> | 航天 · 科技 |

点击报告标题可在新窗口打开阅读。

## 四、成本


| 组件                                              | 费用                                                                                                              |
| ----------------------------------------------- | --------------------------------------------------------------------------------------------------------------- |
| **LLM（你已经在用的）**                                 | **DeepSeek v4 Flash** 基准：quick 约 10–15 万 token / < 0.2 元，standard 约 15–30 万 / < 0.4 元，deep 约 30–50 万 / < 0.7 元 |
| **SearXNG 搜索（作者部署）**                            | 已部署在 VPS，零费用，无限畅用                                                                                               |
| **Scrapling 抓取**                                | 纯本地运行，零费用                                                                                                       |
| **国内源（百度百科/维基百科/知乎/36氪/澎湃/199IT/艾瑞/东方财富/国统局等）** | 直连零费用，不要代理                                                                                                      |
| **OpenCode 运行时**                                | MIT 开源，零费用                                                                                                      |


> 以上估算基于 DeepSeek v4 Flash（$0.14/百万输入、$0.28/百万输出，来源：`https://api-docs.deepseek.com/quick_start/pricing`）。实际因缓存命中率与主题复杂度浮动。

## 五、工作逻辑

整个流程分 4 个阶段，按顺序自动执行：

```
① 分析大纲 — 分析主题，生成调研框架和搜索计划
         ↓
② 采集数据 — ╭─ 在线：结构化 SearXNG 搜索 → 有界队列 → Scrapling 标准抓取 → 失败项动态抓取
               ├─ 混合：在线来源 + 本地 PDF/DOCX/TXT/MD
               ╰─ 离线：只读取本地文件
         ↓
③ 并行撰写 — 所有章节同时撰写，事实直接嵌入 prompt，不做工具调用
          ↓
④ 验收装配 — 批量 validate → assemble → confidence/citations → refresh-metadata → qa-report
```


## 六、搜索链路与内置资源

搜索与抓取采用可恢复的有界流程：

```
每个问题 1 条主查询；high 优先级额外 1 条反方或 site: 定向查询
  ↓ SearXNG 并发搜索
仅覆盖不足问题补搜 1 次 + sources.json 权威域名排序 + 逐问题去重/限额
  ↓
Scrapling 标准抓取（最多 6 并发）
  ↓ 仅失败项
动态浏览器抓取（最多 2 并发）
```

每批抓取后立即写入 `task2-progress.json`。中断后只继续未完成 URL；每个 URL 最多标准和动态两次尝试。候选数、抓取数和正文长度均有限额，避免慢任务无限扩张。

`sources.json` 覆盖学术、数据、新闻和中文专业来源，用于权威域名排序与兜底模板；运行时不再逐个全量 health check。

## 七、报告独特亮点


| 维度          | 说明                                      |
| ----------- | --------------------------------------- |
| **多语言专业行文** | 自动检测主题语言，以 19 种语言直接撰写报告，非翻译模式           |
| **每个数字有来源** | 正文标注 `(N)` 可点击引用，文末附参考来源列表。找不到来源的数字不写   |
| **正反观点并存**  | 每章呈现争议和反对观点，不回避矛盾                       |
| **置信度分级**   | 末章汇总表（高/中/低），什么可靠什么有争议一目了然              |
| **数据防坑机制**  | 自动识别常见数据错误——单位搞混、数据造假、张冠李戴，不让有问题的数据混进报告 |
| **段落重于行数**  | 段落和表格下限由 `profiles.json` 验收，空行不能充当内容       |


## 八、三种深度


| 命令                    | 用途          | 最少章数 | 最少段落/章 | 参考字数（字符） | 参考耗时       |
| --------------------- | ----------- | ---- | ------ | -------- | ---------- |
| `$deep-research 主题`        | standard 默认 | 8    | ≥ 5    | ≈ 25,000 | ~10–15 min |
| `$deep-research 主题 -quick` | 快速洞察        | 5    | ≥ 4    | ≈ 15,000 | ~8–12 min  |
| `$deep-research 主题 -deep`  | 极致深度        | 10   | ≥ 6    | ≈ 45,000 | ~15–25 min |


> 参数见 `profiles.json`，修改后重启生效。字数为去空格和 Markdown 语法的纯字符数。

## 九、安装

### 🧠 方式一：AI 傻瓜安装（推荐）

把下面这段提示词复制到 OpenCode 聊天框发送，AI 会自动完成一切：

```text
请调研 https://github.com/hoolulu/deep-research 项目，按照文档要求依次完成：

1. 安装前置依赖（根据 Scrapling 官方文档和你的操作系统确定安装方式）
2. 注册 Scrapling MCP Server，确保重启 CLI 后正常使用
3. 注册 /research 和 /research-update 命令

每完成一步都确认结果，完成后读取 VERSION 确认版本号，并总结安装状态。
```

AI 会读取项目文档→理解系统类型→逐项安装→验证可用性。不需要手动执行任何命令。

### 🔧 方式二：非 OpenCode 用户（Claude Code / Codex CLI / Cursor 等）

把这段提示词粘贴到你的 AI 编码工具中：

```text
请调研 https://github.com/hoolulu/deep-research 项目，自动安装前置依赖并改造适配当前 CLI 工具：

1. 安装 Python 和 Scrapling（参考 Scrapling 官方文档和系统确定方式）
2. 注册 Scrapling MCP Server，重启后生效
3. 根据当前工具的能力注册 /research 和 /research-update 的等价入口：
   - **Codex CLI** → 注册为 skill（skill 目录 `command/` 已含命令文件，注册后自动生效）
   - **Claude Code** → 注册为 slash command（Hook）
   - **Cursor** → 按平台机制适配（自定义命令 / Agent rules）
   - 其他工具先判断有无 skill/命令机制，再选最合适的方式
4. 将多 agent 链式架构（大纲 → 数据采集 → 并行撰写 → 装配QA）翻译为当前工具的等价实现
5. 若本机有多个 CLI 工具，只配置当前工具，不影响本机其他 CLI 工具。

每完成一步确认结果，完成后读取 VERSION 确认版本号并总结状态。
```

不同工具的适配点：多 agent 编排需映射到各自的原生机制（Claude Code 的 sub-agent、Codex CLI 的 agent/skill 模式、Cursor 的 agent 模式等），命令入口注册方式也不同（OpenCode/Codex CLI 使用 skill，Claude Code 使用 Hook/命令，Cursor 使用自定义指令）。搜索和抓取逻辑（python-scrapling + 搜索 API）可原样复用。

### 前置依赖


| 组件 | 在线模式 | 离线模式 | 获取方式 |
|:----|:--------|:--------|:--------|
| **LLM 运行时**（OpenCode / Claude Code / Codex CLI / Cursor 等） | ✅ 必须 | ✅ 必须 | 选择你习惯的工具即可 |
| **Scrapling** | ✅ 必须 | ❌ 不需要 | 网页抓取用，离线模式不涉及 |
| **SearXNG**（作者部署，70+ 引擎） | ✅ 使用 | ❌ 不需要 | 内置默认端点，开箱即用 |

> **平台说明**：OpenCode 原生支持多 agent 编排（Task 1-4 的多 agent 架构），无需额外插件。其他编程工具（Claude Code、Cursor、Codex CLI 等）有自己的原生多 agent 框架，可以直接适配本 skill 的工作流。离线模式下仅依赖 LLM 的文件读取能力，无需搜索/抓取组件。

## 十、使用方法

安装并重启 OpenCode 后，在聊天框输入：


| 命令                                                         | 说明          | 参考耗时       |
| ---------------------------------------------------------- | ----------- | ---------- |
| `$deep-research 你的主题`                                           | standard 模式（在线搜索） | ~10-15 min |
| `$deep-research 你的主题 -quick`                                    | quick 模式（在线搜索）   | ~8-12 min  |
| `$deep-research 你的主题 -deep`                                     | deep 模式（在线搜索）    | ~15-25 min |
| `本地资料调研`                                              | 离线模式（读本地文件）     | 取决于文件大小   |
| `/research-update`                                         | 检查更新        | —          |

> 本地资料调研：具体指令词见 FAQ 第 2 节《如何使用本地资料生成报告？》。

### 发送后会发生什么

整个流程自动运行，你不需要做任何操作：

```
① 分析大纲 — 分析主题，生成调研框架和搜索计划（含 source_suggestions 定向源推荐）
② 采集数据 — 结构化 SearXNG 搜索 → 有界抓取队列 → Scrapling 标准/动态抓取 → 可恢复数据池 → 严格质检
③ 并行撰写 — 所有章节同时撰写，事实直接嵌入 prompt，不做额外工具调用
④ 装配验收 — 批量 validate → assemble-report → convert-citations → escape-currency → qa-report
```

> 以上累计 ~10-20 分钟。复杂主题可能延长，简单主题可能缩短。

### 输出文件

报告以 Markdown 格式保存到 skill 目录下的 `reports/` 文件夹，文件名包含日期时间戳：

```
{workspace}/.agents/skills/deep-research/reports/
```

可以用任何 Markdown 阅读器（Typora / Obsidian / VS Code 等）打开。

你也可以指定报告的存放路径，让 AI 帮你修改。

**本地报告列表页**：每次调研完成后刷新 `reports-browser/index.html` 和 `reports-browser/data/`。直接用浏览器打开（支持 file://），报告正文只在点击时加载，并经 DOMPurify 清洗后预览。

## 十一、FAQ

**1. 搜索额度？怎么保证搜索不中断？**

系统使用 **SearXNG + 权威域名排序 + 可恢复 Scrapling 抓取**：

- `search-outline` 根据大纲生成主查询、反方查询和 `site:` 定向查询，并发请求 `SEARXNG_URL`。
- `sources.json` 用于来源优先级排序，不直接抓搜索结果页。
- `profiles.json` 控制每个问题的候选和抓取上限；搜索服务失败会被明确记录，不宣称“永远可用”。
- 标准抓取失败的 URL 才升级动态浏览器抓取；MCP 未加载时使用同源 CLI 兜底，重启 Codex 后恢复 MCP 直连。

**2. 如何使用本地资料生成报告？**

Skill 内置 offline 和 mixed 模式。支持 **MD / TXT / PDF / DOCX**；`pypdf` 与 `python-docx` 已锁定在 `requirements.lock`，运行时不会临时安装依赖。

根据你的需要选择以下场景：

**场景 1：本地资料 + 联网补充**（推荐，调研最完整）
```
请使用 deep-research 这个 skill，根据 D:\我的笔记\项目A 的本地资料，生成一份关于 XX 的研究报告（quick 模式）。本地资料里的内容优先作为素材，不够的你在网上搜索补充。
```

**场景 2：只用本地资料，不联网**（适合资料足够、担心联网干扰主题的情况）
```
请使用 deep-research 这个 skill，根据 D:\我的笔记\项目A 的本地资料，生成一份关于 XX 的研究报告（quick 模式）。只看本地资料，不要联网搜索。
```
系统会跳过搜索/抓取流程，直接从指定文件提取数据，后续的章节撰写和装配 QA 正常执行。最终输出带有元数据、`[N]` 引用、目录的标准报告。

**场景 3：纯本地，不用 skill**（最轻量，适合不需要专业报告格式的快速总结）
```
根据 D:\我的笔记\项目A 的资料，帮我整理成一份结构化的研究报告，要有目录和章节标题。
```

> **场景选择建议**：资料不够全 → 场景 1（联网补充）；资料足够且需要专业报告格式 → 场景 2（离线模式）；只需快速总结 → 场景 3（最轻量）。

**3. 如何更新到最新版本？**

本地版本包含 Codex、MCP、安全和恢复逻辑适配，不应直接 `git pull` 覆盖。输入 `/research-update` 时只会把上游克隆到临时目录，输出版本和文件差异；看过 diff 并明确确认后，才在单独任务中迁移上游改动。

**4. 非 OpenCode 用户如何检查上游更新？**

先让 AI 做只读版本对比，不要自动应用：

```text
请对比 https://github.com/hoolulu/deep-research 最新版与本地版本的差异，
找出上游新增功能和修复，
列出与本地适配的冲突，
然后停止，不修改文件。
后续迁移必须保留平台特定改动。
若本机有多个 CLI 工具，只配置当前工具，不影响本机其他 CLI 工具。
```

**5. 数据安全吗？**

离线模式的文档解析、写作和浏览器预览在本机完成。online / mixed 模式会把搜索词发送到配置的 SearXNG，并向候选网站发起抓取请求；不会把本地文件上传到 SearXNG 或目标网站。是否还会把上下文发送给所用 LLM 服务，取决于你的 Codex/模型部署方式。

## 十二、运行截图

<img width="1532" height="836" alt="Screenshot 2026-06-09 at 11-28-17" src="https://github.com/user-attachments/assets/736b0113-f054-4dba-b018-e656a51a9fb4" />

<img width="1532" height="932" alt="Screenshot 2026-06-09 at 11-30-13" src="https://github.com/user-attachments/assets/a88cbf27-7b6c-4ea3-8b51-424f48bf9906" />

<img width="1524" height="846" alt="Screenshot 2026-06-09 at 11-30-55" src="https://github.com/user-attachments/assets/ef10865d-3a72-4658-ac9c-28b2221e77f5" />

<img width="1528" height="840" alt="Screenshot 2026-06-09 at 11-32-13" src="https://github.com/user-attachments/assets/506e91eb-1d5d-4312-aceb-9280d357e264" />

<img width="1438" height="842" alt="Screenshot 2026-06-09 at 11-35-03" src="https://github.com/user-attachments/assets/75acd450-9349-4024-923d-f9b14ea601dd" />

## License

MIT

本项目采用 MIT 协议。选择 MIT 而非 GPL/CC 等更严格的协议，是因为本项目的核心是一套可移植的方法论和管道设计，而非需要保护版权的成品库。MIT 能让它在不同平台和工具链中被最大化地复用和改造，与"非 OpenCode 独占"的定位一致。

---

## Star History

<a href="https://www.star-history.com/?repos=hoolulu%2Fdeep-research">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/chart?repos=hoolulu/deep-research&type=date&theme=dark&legend=top-left" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/chart?repos=hoolulu/deep-research&type=date&legend=top-left" />
   <img alt="Star History Chart" src="https://api.star-history.com/chart?repos=hoolulu/deep-research&type=date&legend=top-left" />
 </picture>
</a>

---

**Created by [hoolulu](https://github.com/hoolulu)** · 项目地址：[github.com/hoolulu/deep-research](https://github.com/hoolulu/deep-research)

> 社区讨论：[LINUX DO](https://linux.do/t/topic/2312664)
