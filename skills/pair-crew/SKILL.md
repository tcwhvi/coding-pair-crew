# pair-crew — 多 Agent 结对班组（agent 无关）

> **pair-crew**（结对班组）：多个 agent 分角色结对开发——有人实现、有人写测试、有人评审。  
> **任何 agent 都能当指挥**：MiMo Desktop、Claude Code、Codex、WorkBuddy、ZCode、用户自定义 agent……只要能读本目录、跑 Python3、发 prompt。

## 谁能用

| 角色 | 用什么 | 说明 |
|---|---|---|
| **指挥 Conductor** | 本 `SKILL.md` | **不限产品**。Claude Code / Codex / MiMo / 自定义 CLI agent 均可 |
| **工位 Worker** | 只收派发 prompt | Qoder / Qoder CN / WorkBuddy / ZCode / 任意 agent 会话 |
| **脚本 Scripts** | `scripts/*.py` | 纯 Python3 + 标准库（CDP 处复用 `websocket-client`）；与 agent 无关 |
| **契约 Contracts** | `contracts/**` | 人与 agent 共用的事实源 |

### 不同 agent 怎么挂上本 skill

| Agent | 做法 |
|---|---|
| **Claude Code** | 把 `skills/pair-crew/` 拷到 `~/.claude/skills/pair-crew/` 或项目 `.claude/skills/pair-crew/`；或在 CLAUDE.md 写「服从 pair-crew 流程」 |
| **Codex** | 放到项目内并在 AGENTS.md / 项目说明里引用本 SKILL.md |
| **MiMo** | 项目 `skills/pair-crew/` 或引擎 skill 目录 |
| **自定义 / CLI agent** | 设定「工作前先读 `SKILL.md` + `templates/`」；脚本用 `python` 调用即可 |
| **多指挥协作** | 同一仓库只保留一份契约与 BOARD；指挥可换人，**不要复制多份 contracts** |

触发：`/pair-crew`、「pair 开发 / 结对 / 多 agent 车间 / 一人实现一人测试」。

## 核心原则

1. **角色与工具解耦**：实现 / 测试 / 评审是角色；Qoder、WorkBuddy、ZCode、任意 LLM 会话是壳
2. **契约先于代码**：SPEC / API / SCOPE / examples.yaml 先冻结
3. **单写者**：一 task 一 worktree，禁止并发写同一业务区
4. **高频对齐**：用户需求确认 → 班组圆桌 → 搭档并写（例粒度）→ 评审可批
5. **能力门禁**：UI 布局目检必须多模态；`routing_check` 开工前校验
6. **【硬性】必须找用户确认，禁止 agent 自行拍板**——尤其是需求澄清：
   - Story 目标/边界、不明白的点、任务怎么拆、测试用例怎么写，**必须经用户确认后才能冻结**
   - 外部工具派发：目标工具、项目名、绝对路径、新建/续写、**完全访问**
   - 范围变更、P0 裁决、合入 main 等高风险动作
   - 用户已明确授权「按此执行」的同类动作可在授权范围内连续执行；**新开的歧义/需求问题仍要问**
7. **【硬性】派发后核对读回**含真实路径；读不到多半是工作区或权限问题

## 目录约定（与 agent 无关）

```
<repo>/
  docs/multi-agent-pair-plan.md
  skills/pair-crew/                 # 本 skill（可被任意 agent 引用）
  contracts/<task_id>/              # SPEC API SCOPE examples.yaml HANDOFF review/
  .agents/ROUTING.yaml              # 角色 → 运行时/模型/能力
  .agents/BOARD.md                  # 工单板
  worktrees/                        # impl / review / qa 隔离区
```

## 主流程

### 0.【硬门禁】Story 需求确认（未冻结不得派发）

- **不是**假设用户「已经说清楚」；凡进入 pair + 测试流水线的 Story 必须先对齐
- **【硬性】提问必须结合项目现状，禁止空中楼阁**
  - 先扫一眼仓库/目录/文档/库表/接口/截图，再出问题
  - 每条问题要能指向：**哪个文件、哪张表、哪段流程、哪份文档**（例如「Word 里 `paydatetime` 注释是分钟，库里样本像时间戳，以哪个为准？」）
  - 禁止只问「你要什么功能？目标是什么？」这类无锚点空问题
  - 材料里已写明的不要重复问；材料矛盾处问「以哪边为准」
- 一次性呈报（见 `templates/STORY_KICKOFF.md`）：
  1. 我读到的项目现状（证据路径 + 一句摘要）
  2. 我理解的目标（一句话 + 做/不做）
  3. 基于项目的疑问（绑文件/表/字段/流程；可附我的倾向）
  4. 任务拆分草案（谁实现谁测试、依赖）
  5. 测试用例草案（happy / boundary / error / **ui_layout** / **ui_journey**，能落到真实数据/页面）
  6. 风险与验收
- 用户确认后写入 `contracts/<id>/SPEC.md` + `examples.yaml` → **冻结**
- 冻结后大改 = 重新确认；禁止静默扩 scope

### 1. 能力检查

```bash
python skills/pair-crew/scripts/routing_check.py --routing .agents/ROUTING.yaml
```

- ERROR（VISION_REQUIRED / IDE_OFFLINE）先处理或改路由

### 2. 班组圆桌

- 把**用户已确认**的 SPEC 落进契约
- 实现 / 测试确认 `examples.yaml`
- 班组分歧升级主持；**用户确认过的例子不得静默改写**

### 3. 隔离区

- worktree / 分支 `impl/<task_id>`

### 4. 搭档并写

- 实现者：生产码
- 测试者：单测 + 契约测 + UI 布局 / 流程测
- 例粒度同步，写 HANDOFF

### 5. 派发外部工具（每次先与用户确认）

```bash
# Qoder CN / 国际版（指定端口）
python skills/pair-crew/scripts/send_qoder.py --port 9222 \
  --project-name <项目名> --project-path <绝对路径> --text-file prompt.md

# ZCode
python skills/pair-crew/scripts/send_zcode.py --port 9224 \
  --project-name <项目名> --project-path <绝对路径> --text-file prompt.md

# WorkBuddy / 其他（external-review 派发器）
python ~/.agents/skills/external-review/scripts/review_dispatch.py \
  --to workbuddy --project-name <项目名> --project-path <绝对路径> --text-file prompt.md
```

确认项：工具、项目名、路径、新建/续写、完全访问。

### 6. 读回

```bash
python ~/.agents/skills/external-review/scripts/read_review_replies.py \
  --only qoder --tail 8000 --project-path <绝对路径>
# 或直接读 Worker UI / 其输出目录
```

### 7. 评审收口

- P0–P3；轮次 ≤5；连续 2 轮无新 P0/P1 → QA

### 8. QA

- 例子表 + Layout 清单 + 主/异常 Journey

### 9. 集成

- SCOPE 门禁后合入

## 测试分层（UI 一等公民）

| 类 | 谁写/谁跑 | 要点 |
|---|---|---|
| 单测 | 测试者 / 自测 | 逻辑边界 |
| 契约/验收 | 测试者 / QA | examples.yaml 逐条 |
| 集成/接口 | QA | API 不破 |
| **UI 布局** | **多模态模型** | 截图目检：溢出/遮挡/断点/空错载入态 |
| **UI 流程** | 测试者（可文本模型） | Playwright 真点主路径 + 异常路径 |
| SCOPE | 脚本 + 评审 | 不越界 |
| 评审门禁 | 评审 | 无未处理 P0/P1 |

## 模型 / 运行时

- 见 `.agents/ROUTING.yaml` 与 `docs/multi-agent-pair-plan.md` §6
- **模型、思考档、上下文注入**由「指挥 agent 自己的机制」决定；本 skill 只规定：
  - 能力声明（`requires: [vision, image_read]` 等）
  - 上下文风格（`context_style: files`：契约路径 + 例子表，不灌全历史）
  - 开工前 `routing_check` 能过

## 状态机

`draft → ready_for_impl → in_impl → ready_for_review → in_review ⇄ ready_for_impl → ready_for_qa → in_qa → done`，`blocked` 可回。

## 人工介入

- Story 需求确认 / 变更
- 每次外部工具派发（工作区与权限）
- 评审超轮次或双方结论对立
- 合入 main、对外高风险
- 派发失败（选不到工作空间、任务占用、选择器失效）

## 脚本索引

| 脚本 | 用途 |
|---|---|
| `scripts/routing_check.py` | 能力与 IDE 门禁 |
| `scripts/send_qoder.py` | Qoder CN / 国际版派发（指定 CDP 端口） |
| `scripts/send_zcode.py` | ZCode 派发 |
| `templates/*` | HANDOFF / ROUTING / STORY_KICKOFF / DISPATCH_CHECKLIST / contracts |
