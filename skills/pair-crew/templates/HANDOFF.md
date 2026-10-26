# HANDOFF — 任务交接包

```yaml
task_id: T-demo-001
title: "示例任务标题"
from: architect
to: implementer
status: draft
# draft | ready_for_impl | in_impl | ready_for_review | in_review
# | ready_for_qa | in_qa | done | blocked

summary: |
  一段话说清要做什么、为什么。

contracts:
  - contracts/T-demo-001/SPEC.md
  - contracts/T-demo-001/API.md
  - contracts/T-demo-001/SCOPE.md
  - contracts/T-demo-001/examples.yaml

acceptance:
  - "例子表 examples.yaml 全部通过"
  - "主 Journey 绿 + 1 条异常 Journey 绿（若含 UI）"
  - "SCOPE 无越界 diff"

constraints:
  - "禁止改依赖版本"
  - "禁止改 SCOPE 禁区"

deliverables:
  branch: "impl/T-demo-001"
  worktree: "worktrees/impl-T-demo-001"
  self_test: "命令写这里"

open_questions: []
priority: P1
created_at: "YYYY-MM-DDTHH:MM:SSZ"
updated_at: "YYYY-MM-DDTHH:MM:SSZ"
```

## 变更日志

- [ ] 初始创建
