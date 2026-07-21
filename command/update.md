---
description: Codex equivalent for /research-update — compare upstream without changing local adaptations
---

<command-instruction>
你负责检查 deep-research 上游更新。默认流程严格只读：不得 pull、覆盖、复制、提交或删除本地 Skill 文件。

## 流程

1. 定位当前工作区的 `.agents/skills/deep-research/`，读取本地 `VERSION`。
2. 检查工作区状态并记录本地改动/未跟踪文件；不得执行 reset、checkout、clean 或 stash。
3. 将 `https://github.com/hoolulu/deep-research` 的 `main` 浅克隆到新的系统临时目录。克隆失败时只报告网络错误，不改变本地目录。
4. 读取上游 `VERSION`，用只读 diff 比较上游与本地 Skill：
   - 列出新增、删除、修改的文件；
   - 单独标出本地 Codex 适配文件和配置；
   - 说明可能的冲突与迁移风险；
   - 不把 `reports/`、`reports-browser/index.html` 或本地配置当作可直接覆盖项。
5. 输出版本差异和建议迁移顺序，然后停止。只有用户在看过 diff 后明确要求实施更新，才进入单独的修改任务。

无论版本是否相同，都不得自动写入或自动提交。
</command-instruction>

<user-request>
$ARGUMENTS
</user-request>

---
```
deep-research by hoolulu · github.com/hoolulu/deep-research
```
