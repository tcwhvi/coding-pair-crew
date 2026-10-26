# pair-crew — Multi-Agent Pair Crew

[中文](README.zh-CN.md)

Let multiple AI agents work **as a pair crew** — one implements, one writes tests, one reviews. Agent-agnostic: Claude Code / Codex / any custom agent can be the conductor; Qoder / WorkBuddy / ZCode etc. can be workers.

## What problem does this solve?

| Pain: one human + one AI | pair-crew |
|---|---|
| Start coding before the need is clear | **Story hard gate**: goals, open questions, task split, test examples — freeze after you confirm |
| Nobody reviews carefully | Role-based review with P0–P3 and bounded rounds |
| UI “looks fine” but unproven | Separate **UI layout** vs **user journey** tests |
| Multiple AIs trample one repo | **One task, one worktree**, single writer |
| Locked to one vendor | Shared contracts + portable scripts; swap the shell |

## 30 seconds

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

## Anyone can conduct

| Role | What they use |
|---|---|
| Conductor | This `SKILL.md`; any agent that can run Python |
| Worker | Receives prompts: Qoder / WorkBuddy / ZCode… |
| Scripts | `scripts/*.py` — no vendor lock-in |

## Quick start

1. Read [`skills/pair-crew/SKILL.md`](skills/pair-crew/SKILL.md)
2. Copy `skills/pair-crew/templates/` → `.agents/` and edit `ROUTING.yaml`
3. Tell your agent: “Use pair-crew for this story”

## Layout

```
skills/pair-crew/     # skill + scripts
docs/                 # design notes
contracts/            # SPEC / examples / handoffs
.agents/              # routing & board
```

## Principles

1. Accurate requirements before speed  
2. Contracts before code  
3. Roles decoupled from tools  
4. UI tests are first-class (layout needs multimodal; journeys can be scripted)  
5. Confirm workspace & permissions before every external dispatch  

## License

MIT
