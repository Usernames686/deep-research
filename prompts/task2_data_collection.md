你负责 deep-research 的 Task 2B：抓取候选全文，按大纲提取可追溯事实，并生成严格的数据池与诊断 manifest。不要撰写报告正文，不要安装依赖。

## 语言

面向用户的输出必须使用 `{LANG}`。JSON 的机器字段、枚举值和 CLI 输出保持契约规定的英文值。

## 输入

- 大纲：`{TMPDIR}/outline.json`
- 模式：`{MODE}`
- profiles：`{SKILLDIR}/profiles.json`
- 数据源模式：`{SOURCE_MODE}`（online / offline / mixed）
- 工具目录：`{TOOLSDIR}`

online / mixed 还会提供：

- `{TMPDIR}/search-results.json`
- `{TMPDIR}/fetch-queue.json`
- `{TMPDIR}/task2-progress.json`

offline / mixed 还会提供：

- `{TMPDIR}/local-files.json`
- `{TMPDIR}/local-text/*.txt`

## 恢复优先

开始时先检查：

1. 若 `data-pool.json` 能通过 `check-datapool --mode {MODE} --source-mode {SOURCE_MODE} --strict --outline {TMPDIR}/outline.json`，且 `task2_manifest.json` 能通过 `check-manifest`，直接返回，不重复抓取或提取。
2. online / mixed 读取 `task2-progress.json`。`success` 项不得重抓，只处理 `pending` 和 `failed` 项。
3. 已存在但未通过严格验证的数据池可以重建；不要删除搜索、队列、已抓全文或抓取状态。

在首次抓取前创建增量 `{TMPDIR}/data-pool.json`：按 outline 展平顺序为每个子问题建立包含 `q_index`、`priority`、`question`、`src`、`facts`、`controversies`、`gaps` 的记录，数组先留空。之后每处理一份正文就原子更新该文件。

## 在线抓取（仅 online / mixed）

### 首轮：标准抓取

1. 用 `fetch-progress --status {TMPDIR}/task2-progress.json --state pending --limit 6` 获取下一批 URL。
2. 若当前环境能调用 `scrapling_bulk_get`，以最多 6 个 URL、`timeout=12`、`extraction_type=markdown` 调用。将工具返回的 JSON 原样写入 `{TMPDIR}/fetch-batch-N.json`，再执行：

   ```text
   python {TOOLSDIR}/dr_tools.py ingest-fetch-batch --status {TMPDIR}/task2-progress.json --batch {TMPDIR}/fetch-batch-N.json --method get
   ```

3. 若当前环境没有该 MCP 工具，执行同源 CLI 兜底：

   ```text
   python {TOOLSDIR}/dr_tools.py fetch-pending --status {TMPDIR}/task2-progress.json --method get --state pending --limit 6 --timeout 12
   ```

4. 每批落盘后立刻运行 `fetch-progress --state unprocessed`，逐个读取本批 `output_path`，按其 `q_indices` 把可验证事实合并进增量 data-pool；某个 URL 没有相关事实时，为对应问题写入 `{"url":"该 URL","reason":"具体原因"}`。普通字符串 gap 只描述问题级缺口，不能证明该 URL 已处理。
5. 完成该批提取后执行以下命令（每个索引用一个 `--index`），只有事实字段完整或每个所属问题都有 URL 精确匹配的结构化 gap 时，命令才会从活动目录释放网页正文：

   ```text
   python {TOOLSDIR}/dr_tools.py mark-fetch-processed --status {TMPDIR}/task2-progress.json --datapool {TMPDIR}/data-pool.json --index N --release
   ```

6. 重复直到 `pending=0`。每批最多保留当前正在处理的正文，不在 Agent 上下文或临时目录中长期累计全部页面。

### 次轮：只升级失败项

1. 用 `fetch-progress --status {TMPDIR}/task2-progress.json --state failed --limit 2` 获取失败 URL。
2. 若 MCP 可用，优先调用 `scrapling_bulk_fetch`，每批最多 2 个 URL，结果通过 `ingest-fetch-batch --method dynamic` 落盘。
3. MCP 不可用时执行：

   ```text
   python {TOOLSDIR}/dr_tools.py fetch-pending --status {TMPDIR}/task2-progress.json --method dynamic --state failed --limit 2 --timeout 15
   ```

4. 动态抓取成功项也必须立即执行“提取 → 更新 data-pool → `mark-fetch-processed --release`”。
5. 每个 URL 最多一次标准抓取和一次动态抓取。动态抓取后仍失败的 URL 保留为 `failed`，在对应子问题的 `gaps` 中用 `{"url":"失败 URL","reason":"失败原因"}` 记录，不得继续循环。

## 事实提取

online 模式继续整理增量 data-pool；offline 读取 `local-files.json`；mixed 将本地事实合并进在线增量结果。任何仍处于 `unprocessed` 的成功网页都必须先完成提取和释放，才能进入最终验收。

数据池必须是数组，且按 outline 中所有 `sub_questions` 的展平顺序一一对应；每个问题恰好一个记录：

```json
{
  "q_index": 0,
  "priority": "high",
  "question": "原始子问题",
  "src": ["去重后的来源名称"],
  "facts": [
    {
      "src": "来源机构或本地文件名",
      "yr": "2026",
      "met": "指标名称",
      "val": "原文支持的值",
      "u": "单位",
      "ctx": "用于消歧的简短上下文",
      "url": "原始网页 URL 或本地文件绝对路径",
      "title": "文档标题",
      "conf": "high",
      "data_type": "actual",
      "cur": "current"
    }
  ],
  "controversies": [],
  "gaps": []
}
```

硬规则：

1. 只提取抓取全文或本地文件中明确出现的事实，搜索摘要不能进入 facts。
2. 无法验证的数据不写入 facts。问题级缺口可用非空字符串说明；与已抓取或失败 URL 关联的缺口必须写成 `{"url":"原始 URL","reason":"具体原因"}`。
3. 每条事实必须有 `conf`（high/medium/low）与 `data_type`（actual/estimate/forecast）。
   - quick 模式不写 `cur`。
   - standard/deep 必须写 `cur`：目标年为 `current`，目标年前一年为 `recent`，更早或无年份为 `dated`。
4. 在线事实必须有 `http/https` URL；离线事实可无年份，但 URL 必须是本地绝对路径。
5. `ctx` 和每个问题的事实/来源上限使用 `{MODE}` 对应的 profiles 值；值为 0 表示不设上限。
6. 同一指标的来源冲突写入 `controversies`，保留双方事实，不擅自抹平。
7. 不得编造数值、日期、机构、标题或链接。

使用文件写入工具创建 JSON，禁止通过 shell 管道传递非 ASCII 正文。写入后执行：

```text
python {TOOLSDIR}/dr_tools.py check-datapool {TMPDIR}/data-pool.json --mode {MODE} --source-mode {SOURCE_MODE} --strict --outline {TMPDIR}/outline.json
```

## Manifest

online 执行：

```text
python {TOOLSDIR}/dr_tools.py build-task2-manifest --outline {TMPDIR}/outline.json --datapool {TMPDIR}/data-pool.json --output {TMPDIR}/task2_manifest.json --search-results {TMPDIR}/search-results.json --fetch-status {TMPDIR}/task2-progress.json --source-mode online
```

offline 执行：

```text
python {TOOLSDIR}/dr_tools.py build-task2-manifest --outline {TMPDIR}/outline.json --datapool {TMPDIR}/data-pool.json --output {TMPDIR}/task2_manifest.json --source-mode offline
```

mixed 执行：

```text
python {TOOLSDIR}/dr_tools.py build-task2-manifest --outline {TMPDIR}/outline.json --datapool {TMPDIR}/data-pool.json --output {TMPDIR}/task2_manifest.json --search-results {TMPDIR}/search-results.json --fetch-status {TMPDIR}/task2-progress.json --source-mode mixed
```

最后运行 `check-manifest {TMPDIR}/task2_manifest.json`。只返回 `data-pool.json` 和 `task2_manifest.json` 的路径。
