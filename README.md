# pair-crew — Multi-Agent Pair Crew

> **中文**：让多个 AI agent **分角色结对干活**——一人写实现、一人写测试、有人评审。不绑死某个产品：Claude Code / Codex / 任意自定义 agent 都能当「指挥」；Qoder、WorkBuddy、ZCode 等当「工位」。
>
> **English**: Multiple AI agents work **as a pair crew** — one implements, one writes tests, one reviews. Agent-agnostic: Claude Code / Codex / any custom agent can be the conductor; Qoder / WorkBuddy / ZCode etc. can be workers.

[English](#english) · [中文](#中文)

---

## English

### What problem does this solve?

| Pain: one human + one AI | pair-crew |
|---|---|
| Start coding before the need is clear | **Story hard gate**: goals, open questions, task split, test examples — freeze after you confirm |
| Nobody reviews carefully | Role-based review with P0–P3 and bounded rounds |
| UI “looks fine” but unproven | Separate **UI layout** vs **user journey** tests |
| Multiple AIs trample one repo | **One task, one worktree**, single writer |
| Locked to one vendor | Shared contracts + portable scripts; swap the shell |

### 30 seconds

```text
You describe a need
   ↓
[Confirm]  goals / questions / tasks / test examples  → you approve → freeze
   ↓
[Crew]  implementer ── writes code ──┐
        test partner ── writes tests ─┤  tight sync (per example)
                                      ↓
[Review]  no open P0/P1  →  [QA] examples + UI journeys  →  merge
```

### Anyone can conduct

| Role | What they use |
|---|---|
| Conductor | This `SKILL.md`; any agent that can run Python |
| Worker | Receives prompts: Qoder / WorkBuddy / ZCode… |
| Scripts | `scripts/*.py` — no vendor lock-in |

### Quick start

1. Read [`skills/pair-crew/SKILL.md`](skills/pair-crew/SKILL.md)
2. Copy `skills/pair-crew/templates/` → `.agents/` and edit `ROUTING.yaml`
3. Tell your agent: “Use pair-crew for this story”

### Layout

```
skills/pair-crew/     # skill + scripts
docs/                 # design notes & profile drafts
contracts/            # SPEC / examples / handoffs
.agents/              # routing & board
```

### Principles

1. Accurate requirements before speed  
2. Contracts before code  
3. Roles decoupled from tools  
4. UI tests are first-class (layout needs multimodal; journeys can be scripted)  
5. Confirm workspace & permissions before every external dispatch  

### License

MIT

---

## 中文

### 解决什么问题？

| 一个人 + 一个 AI 的痛点 | pair-crew |
|---|---|
| 需求没对齐就开工 | **Story 硬门禁**：目标、疑问、任务拆分、测试例子——你确认后再冻结 |
| 实现写完没人认真看 | 角色化评审，P0–P3 分级，轮次可收敛 |
| UI「看起来还行」但没法证明 | **UI 布局** 与 **用户点得通** 两类测试分开 |
| 多个 AI 抢同一仓库改乱 | **一任务一 worktree**，单写者 |
| 只能用某一家工具 | 契约与脚本通用，工具壳可换 |

### 30 秒看懂

```text
你提需求
   ↓
[需求确认]  目标 / 疑问 / 任务拆分 / 测试例子  → 你确认后冻结
   ↓
[班组]  实现者 ── 写实现 ──┐
        测试者 ── 写测试 ──┤  高频对齐（按例子同步）
                          ↓
[评审]  无未处理 P0/P1  →  [QA] 例子表 + UI 流程  →  合入
```

### 谁都能当指挥

| 角色 | 用什么 |
|---|---|
| 指挥 Conductor | 本 `SKILL.md`，任意能跑 Python 的 agent |
| 工位 Worker | 只收 prompt：Qoder / WorkBuddy / ZCode… |
| 脚本 | `scripts/*.py`，与 agent 无关 |

### 快速开始

1. 读 [`skills/pair-crew/SKILL.md`](skills/pair-crew/SKILL.md)
2. 复制 `skills/pair-crew/templates/` → `.agents/` 并改 `ROUTING.yaml`
3. 对指挥 agent 说：「用 pair-crew 做这个 story」

### 目录

```
skills/pair-crew/     # 技能定义与脚本
docs/                 # 设计说明与介绍文案
contracts/            # 任务契约（SPEC / 例子 / 交接包）
.agents/              # 路由与工单板
```

### 设计原则

1. 需求准确优先于开工速度  
2. 契约先于代码  
3. 角色与工具解耦  
4. UI 测试是一等公民（布局目检要多模态；点击流程可脚本化）  
5. 每次派发外部工具前确认工作区与权限  

### License

MIT
