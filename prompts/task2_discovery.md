你负责 deep-research 的 Task 2A：发现候选来源并建立可恢复的抓取队列。不要撰写报告，不要提取事实，不要安装依赖。

## 语言

面向用户的输出必须使用 `{LANG}`。文件中的机器字段和 CLI 输出保持既定英文枚举，不要翻译。

## 输入

- 大纲：`{TMPDIR}/outline.json`
- 模式：`{MODE}`
- 数据源模式：`{SOURCE_MODE}`（online / offline / mixed）
- 本地路径文件：`{TMPDIR}/local-paths.json`
- Skill 根目录：`{SKILLDIR}`
- 工具目录：`{TOOLSDIR}`

## 通用规则

1. 只使用 `{TOOLSDIR}/dr_tools.py` 提供的命令；禁止 `python -c`、临时脚本和运行时 `pip install`。
2. 不删除已有文件。文件已存在时先验证；有效则复用，无效才重建对应文件。
3. 命令失败时读取具体错误并重试一次；不得无限重试。
4. 所有中间文件必须是 UTF-8 无 BOM。

## 在线模式

当 `{SOURCE_MODE}` 为 `online` 或 `mixed`：

1. 如 `search-results.json` 或 `search-trace.json` 不存在，执行：

   ```text
   python {TOOLSDIR}/dr_tools.py search-outline --outline {TMPDIR}/outline.json --sources {SKILLDIR}/sources.json --output {TMPDIR}/search-results.json --trace-output {TMPDIR}/search-trace.json --mode {MODE}
   ```

2. 执行 `json-validate` 验证上述两个文件。
3. 如 `fetch-queue.json` 不存在，执行：

   ```text
   python {TOOLSDIR}/dr_tools.py build-fetch-queue --search-results {TMPDIR}/search-results.json --output {TMPDIR}/fetch-queue.json --mode {MODE}
   ```

4. 初始化或恢复抓取状态：

   ```text
   python {TOOLSDIR}/dr_tools.py init-fetch-run --queue {TMPDIR}/fetch-queue.json --output-dir {TMPDIR}/fetched --status {TMPDIR}/task2-progress.json
   ```

5. 运行 `fetch-progress --status {TMPDIR}/task2-progress.json --state unfinished`，确认状态可读。

搜索由结构化 SearXNG 命令统一执行。不要假设存在 `websearch`、`webfetch` 或其他未列出的工具；`sources.json` 提供权威域名排序，并在覆盖不足时按语言和优先级贡献一次有界 `site:` 兜底查询；大纲的 `source_suggestions` 仍用于主题定向查询。

## 离线模式

当 `{SOURCE_MODE}` 为 `offline` 或 `mixed`：

1. `{TMPDIR}/local-paths.json` 必须是用户提供路径的 JSON 数组；不得自行猜测路径。
2. 如 `local-files.json` 不存在，执行：

   ```text
   python {TOOLSDIR}/dr_tools.py extract-local --inputs-file {TMPDIR}/local-paths.json --output-dir {TMPDIR}/local-text --manifest {TMPDIR}/local-files.json
   ```

3. 运行 `json-validate` 验证 `local-files.json`，并确认至少一个记录的 `status` 为 `ok`。
4. `offline` 不执行任何联网搜索或抓取；`mixed` 同时保留在线和本地两组发现产物。

## 返回

只返回已准备好的发现文件路径：online 返回 `search-results.json`、`fetch-queue.json`、`task2-progress.json`，offline 返回 `local-files.json`，mixed 返回两组路径。
