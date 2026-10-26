# SPEC — T-smoke-001 通道冒烟

## Story Card

| 项 | 内容 |
|---|---|
| 角色 | 外部实现者（Qoder） |
| 目标 | 验证工作区绑定 + 读契约 + 简短回报 |
| 价值 | 打通 pair-crew 派发通道 |
| 优先级 | P0 |

## 范围

- 做：读 `skills/pair-crew/templates/` 与 `docs/multi-agent-pair-plan.md` 标题结构
- 不做：改任何文件、装依赖、跑构建

## 验收标准

1. 回报中包含本项目绝对路径（证明绑定正确）
2. 列出 templates 下文件名
3. 用 ≤10 行概括 pair-crew 计划的「角色 + 测试分层」
