# pair-crew — 多 Agent 结对班组（agent 无关）

> **pair-crew**（结对班组）：多个 agent 分角色结对开发——有人实现、有人写测试、有人评审。  
> **任何 agent 都能当指挥**：MiMo Desktop、Claude Code、Codex、WorkBuddy、ZCode、用户自定义 agent……只要能读本目录、跑 Python3、发 prompt。

## 谁能用

| 角色 | 用什么 | 说明 |
|---|---|---|
| **指挥 Conductor** | 本 `SKILL.md` | **不限产品**。Claude Code / Codex / MiMo / 自定义 CLI agent 均可 |
| **工位 Worker** | 只收派发 prompt | Qoder / Qoder CN / WorkBuddy / ZCode / Trae / 任意 agent 会话 |
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
3. **单写者**：禁止并发写同一业务区。**有第二个活跃写者时才建 worktree**（见「流程分层」）
4. **高频对齐**：用户需求确认 → 班组圆桌 → 搭档并写（例粒度）→ 评审可批
5. **能力门禁**：UI 布局目检必须多模态；`routing_check` 开工前校验
6. **【硬性】必须找用户确认，禁止 agent 自行拍板**——尤其是需求澄清：
   - Story 目标/边界、不明白的点、任务怎么拆、测试用例怎么写，**必须经用户确认后才能冻结**
   - 外部工具派发：派发对象（默认随机 2 个，见第 8 条）、项目名、绝对路径、新建/续写、**完全访问**
   - 范围变更、P0 裁决、合入 main 等高风险动作
   - 用户已明确授权「按此执行」的同类动作可在授权范围内连续执行；**新开的歧义/需求问题仍要问**
7. **【硬性】派发后核对读回**含真实路径；读不到多半是工作区或权限问题
8. **【硬性】外部 agent 默认随机两个**：pair / review / QA 等需要其他 agent 时，**从当前可用池里随机抽 2 个**即可——不按优先级挑、不铺满；**用户点名了工具或数量，就按用户说的来**（没说到的部分仍按默认：2 个、随机）。同一次派发沿用这组，失败换替补、不加人；抽完仍按第 6 条向用户确认

## 流程分层：哪些恒做、哪些看条件

下面的清单来自 2026-10-28 的一次真实复盘（1022 小程序改版：1 个实现者 + 1 个外部评审 3 轮，25 个文件集中在一个模块）。判据只有一条：

> **看这件事里有没有「第二个会动的实体」**——第二个写者、第二个评审、第二个工作区、第二个会话。有第二个实体，协调成本不付就会变成返工；没有，流程就是自嗨。

| 项 | 结论 | 什么时候破例 |
|---|---|---|
| 五条硬规则：异步必须读回、禁止重复派发、改完即作废、判定词+证据口径、派发前核对项目 | **恒做** | 无 |
| `contracts/<id>/SPEC.md` + `examples.yaml` | **恒做**，一页纸，写在「改吧 / 开工」那一刻 | 无。实现方和评审方不在同一个对话里，SPEC 是唯一的跨对话通道 |
| 评审数量 | **默认 2 个**（用户点名按用户的） | 只有 1 个工具可用时如实说明；不要为了凑 2 个把同一个会话派两遍 |
| `.agents/BOARD.md` | **派发那一刻写** | 无。收尾补记只剩考古价值，挡不住重复派发 |
| 实现 / 测试分角色 | **恒做**：验收和补边界用例明确交给其中一个评审 | 只有一个 agent 时，用「新用例必须在旧实现上跑红」替代 |
| worktree 隔离 | **看条件**：存在第二个活跃写者时才建 | 没有第二个写者时，用「开工记基线 + 提交前分类」代替 |
| `routing_check.py` + `ROUTING.yaml` | **看条件**：工位池异构、或派发是自动化时 | 就两个能力已知的评审时，跑它只是复述已知事实 |
| 契约冻结仪式（大改需重新确认） | **看条件**：需求有争议或跨模块时 | 用户逐条拍过口径、只做一处形状调整时，一页纸清单就够 |

**「改完即作废」没有例外**：任何一次代码改动都会让上一轮判定失效，必须补一轮（可以只派增量）。

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
- **写 SPEC 的时点是「改吧」那一刻，不是收尾时**：代码写完再补的 SPEC 是实现的转述，不构成契约，评审据此打勾等于自己审自己
- 形式要轻：一页纸——目标 / 不做 / 逐条口径（以用户最新一句话为准）/ 验收例子。重型 PRD 不属于本流程
- 为什么不能省：实现方和评审方不在同一个对话里，评审看不到讨论过程，SPEC 是它唯一能拿到的「什么算对」
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

### 3. 隔离区（看条件）

- **有第二个活跃写者时**（另一个 agent 正在同一仓库改东西）：建 worktree / 分支 `impl/<task_id>`，一 task 一工作区
- **只有一个写者时**：不建 worktree，但必须做两件事，否则提交时会被别人的残留污染
  1. 开工时记基线：`git status --short` + 相关文件的 mtime，存进 HANDOFF
  2. 收尾只提交本次碰过的文件；共享文件（本次和别的批次都改过）用「HEAD + 本次改动」重建 blob 再 `git update-index`，不要整文件 `git add`
- 判断「有没有第二个活跃写者」看证据，不看感觉：`git worktree list`、`git status` 里残留改动的时间戳、最近几小时有没有别人的提交
- 基线要开工时记：如果残留和本次改动是同一天的，mtime 分不出来，收尾再猜就晚了

### 4. 搭档并写

- 实现者：生产码
- 测试者：单测 + 契约测 + UI 布局 / 流程测
- 例粒度同步，写 HANDOFF

### 5. 派发外部工具（每次先与用户确认）

```bash
# 【前置门禁】先按绝对路径确认目标 IDE 里确实有这个项目
python skills/pair-crew/scripts/ide_guard.py --ide zcode --path "D:\projects\xxx"
python skills/pair-crew/scripts/ide_guard.py --ide qoder --path "D:\projects\xxx"
python skills/pair-crew/scripts/ide_guard.py --ide zcode --list      # 看已绑定的目录
python skills/pair-crew/scripts/ide_guard.py --ide qoder --sessions  # 看各会话绑的目录

# Qoder CN / 国际版（指定端口）
python skills/pair-crew/scripts/send_qoder.py --port 9222 \
  --project-name <项目名> --project-path <绝对路径> --text-file prompt.md

# ZCode
python skills/pair-crew/scripts/send_zcode.py --port 9224 \
  --project-name <项目名> --project-path <绝对路径> --text-file prompt.md

# WorkBuddy（CDP，本仓库自带适配器；带 --result-file 读回）
python skills/pair-crew/scripts/send_workbuddy.py --port 9228 \
  --project-path <绝对路径> --text-file prompt.md \
  --result-file contracts/<task_id>/review/P1-workbuddy.md --new-task --wait

# WorkBuddy / 其他（external-review 派发器，若装了那个 skill）
python ~/.agents/skills/external-review/scripts/review_dispatch.py \
  --to workbuddy --project-name <项目名> --project-path <绝对路径> --text-file prompt.md

# Trae（CDP，和 Qoder/ZCode 同一套思路）
python skills/pair-crew/scripts/send_trae.py --port 9226 \
  --project-path <绝对路径> --text-file prompt.md \
  --result-file contracts/<task_id>/review/P1-trae.md --wait
```

> **⚠ Trae 必须带调试端口启动，否则 CDP 连不上**
>
> ```bat
> :: 先清掉 ELECTRON_RUN_AS_NODE：带着它启动，exe 会以 Node 模式运行、直接退出、不起窗口
> set ELECTRON_RUN_AS_NODE=
> "E:\Programs\Trae CN\Trae CN.exe" --remote-debugging-port=9226 "D:\projects\xxx"
> ```
>
> - Trae 的 `chat` 子命令在本机（Trae CN 3.4.9 / cli 1.107.1）实测注不进对话：退出码 0，
>   但面板不出现、消息不落，Agent 任务列表也不新增。所以适配器走 CDP，不走 CLI。
> - `send_trae.py` 会按**窗口标题**核对目标目录，标题里没有项目名就拒发；
>   聊天库是加密的（`ModularData/ai-agent/database.db` 打不开），读回只能靠 `--result-file`。
> - 续写和别的 CDP 通道不同：再发一条消息就是往**同一个对话**里追加，不需要另开任务。
> - 首次使用会弹「是否信任此文件夹中的文件的作者？」，必须用户本人点。

> **⚠ 归属门禁（真实事故）**：`send_zcode.py` / `send_qoder.py` 的旧逻辑只检查
> 「侧栏文本里含不含这个项目名」，含就发到**当前打开的会话**。
> 结果：目标目录在 ZCode 里根本不存在时，任务被静默发进当时开着的
> `coding_skill` 会话（`directory = E:\project_self\coding_skill\.mimocode`），
> 与用户要的项目毫无关系，而脚本一路打印 "SENT"。
> 现在两个脚本都内置 `ide_guard.require()`，**按绝对路径核对，不存在直接拒绝并列出可用目录**。
>
> **被拒绝时不要想办法绕过** —— 那是「需要用户亲自操作」的环节：
> 告诉用户「请在 `<IDE>` 里新建项目 / 打开文件夹，选 `<绝对路径>`」，
> 等他做完再重跑。系统原生文件夹对话框 CDP 碰不到，别硬试。

确认项：派发对象（默认随机 2 个）、项目名、路径、新建/续写、完全访问。

#### 【硬性】派发对象：默认随机两个

- **候选池**：`routing_check.py` 通过、且当前能派发的工具（qoder / qoder_cn / workbuddy / zcode / mimo / claude-code / codex…）加上可用的本地 actor；每次现算，不用旧名单
- **默认随机抽 2 个**（用 `random.sample`，不要按列表顺序固定挑）；不足 2 个就有几个派几个，并在回复里说明
- **用户点名优先**：用户点名了工具或数量，就按用户说的来；没说到的部分仍按默认（2 个、随机）
- **不因「多派一个更稳」加到 3 个以上**；要扩人由用户点名
- 实现与评审尽量不同源；只有一个可选时同源也能用，回复里标注一句风险
- 某个 agent 不可用（IDE 掉线 / 派发失败）→ 从池里再抽一个**替补**，保持 2 个，不是加第三个
- 抽中的两个写进 `.agents/BOARD.md`；同一次派发 / 评审的后续轮次沿用，换人先说明原因
- **判定冲突取严**：一票「可以开工」、一票挑出 P1，按 P1 处理
- **改一次动，两票一起作废**，都要补一轮（可只派增量）
- **停止条件**：两票都只剩 P3 → 停，不再加轮次；不要拿「轮次 ≤5」当唯一上限
- 两份 prompt 可以分工（一份盯资损/状态机/并发，一份盯验收口径/异常态），避免两票重复劳动；不分工时默认同一份

### 6. 读回

```bash
python ~/.agents/skills/external-review/scripts/read_review_replies.py \
  --only qoder --tail 8000 --project-path <绝对路径>
# 或直接读 Worker UI / 其输出目录
```

### 6.5 同一会话续写 / 催收尾

`send_qoder.py` / `send_zcode.py` 只做「新建任务」。要在**已跑起来的会话**里补指令
（补上下文、纠正方向、催它出结论），用 `send_followup.py`：

```bash
# 推荐写法：带 --ide，按 chat id 查数据库核对会话身份
python skills/pair-crew/scripts/send_followup.py --port 9222 --ide qoder \
  --switch-to "生产导入脚本评审" --expect "生产导入脚本评审" --text-file note.md

python skills/pair-crew/scripts/send_followup.py --port 9224 --ide zcode \
  --switch-to "评审" --expect "评审" --text-file note.md
```

> **⚠ 坑 0：`send_followup.py` 的发送回执不可信（实测两次误报）**
> 脚本会打印「点完 chat id 没变，切换没生效」并最终报「三种发送方式都没能让数据库新增消息 ——
> 这条发不出去」，但查 IDE 数据库，消息**已经进了目标会话**（user 消息 + 对方已开始回复）。
> 原因是它的会话切换在侧栏点不到、于是退回按页面文本判断，判断失败就当没发。
> **不要据此重发**。判定是否发出去只看两件事：目标会话数据库里出现这条 user 消息；
> 或 `collect_review.py --session <id>` 能看到新结论。确认没进去再考虑重发。

> **⚠ 坑 1：会话身份不能看页面文本**
> `document.body.innerText` 包含整个侧栏，按文本匹配会把侧栏里**别的会话名**当成当前会话。
> 实测：评审指令被发进「查找TTFT插件」，因为那一页的侧栏里恰好有「评审」二字。
> `--ide` + `--expect` 现在是**按 chat id 查 IDE 数据库里的真实标题**比对；
> 查不到就拒发，并列出最近会话供选。

> **⚠ 坑 2：插话按钮不叫「立即」**
> agent 正在生成时消息只进队列，气泡上多一个按钮，必须点它才插队。
> ZCode 叫 `立即`，**Qoder CN 叫 `插话`**。只匹配「立即」的脚本在 Qoder 上
> 一个也点不到，消息永远排队，看起来像「发了没反应」。
> `send_followup.py` 覆盖 `立即 / 插话 / 立即发送 / 立即执行 / 打断 / 现在就发`，
> 并取**最靠下**（最新）那个，避免误点历史残留按钮。

> **⚠ 坑 3：侧栏项可能滚出视口**
> 实测侧栏项的 `getBoundingClientRect().y` 会是负数（-86），点击坐标落在视口外，
> 事件被丢弃但脚本不报错，表现为「切了但没切过去」。
> 现在点击前先 `scrollIntoView({block:'center'})`，并回读 `visible` 标志。

> **⚠ 读回结果的更好办法：直接读 IDE 数据库**
> CDP 只能读**当前活动视图**，用户一切走你就读到别人的会话。要拿某个会话的完整输出，
> 直接读库更可靠、也不占用用户界面：
> - Qoder：`main.sqlite` 的 `chat_session_messages`（`payload_json.parts`）
> - ZCode：`~/.zcode/cli/db/db.sqlite` 的 `message` / `part` 表

### 7. 评审收口

- P0–P3；轮次 ≤5；连续 2 轮无新 P0/P1 → QA
- 默认 **2 个独立评审**（按 §5 随机抽取；用户点名则按用户）；不要一上来铺三个以上

#### 【硬性】未收口不得收工

这是最容易犯、代价最大的错：**派发是异步的，agent 的会话是同步的**。
外部 IDE 一跑就是半小时到一小时，一波指令发出去，agent 这边一轮答完就要结束，
于是「派发了」被当成了「评审完了」，结论永远没人读，用户那边还在跑、这边已经收工。

规矩：

1. **派发后立刻登记**：在 `.agents/BOARD.md` 写一行
   `task_id | 工具 | 会话标题 | session_id | 派发时间 | 状态=in_review`

   > 实测最常见的是「收尾补记」：时间回填、状态全填 done，看着完整，但它挡不住任何一次重复派发。
   > **派发那一刻就写**；写不出 `session_id` 就说明还没真派成。
2. **收工前必须做收口检查**，三问：
   - 我这次派出去几个评审？各自的 `session_id` 是什么？
   - **每一个**都拿到明确判定（`可以开工` / `还不能开工` / 换方案）了吗？
   - 没拿到的，有没有在 HANDOFF 里写清「怎么读回」？
3. **禁止**在还有 `in_review` 未读回时，宣称任务完成或说「评审已通过」
4. 拿不到结论就**明说**：「X 还在跑，我下次用 `collect_review.py --session <id>` 读回」，
   并把命令写进回复里，不要含糊过去

#### 【硬性】续写之前先读回，禁止重复派发

同一件事发两遍，会让对方重做一遍、白烧一轮额度和时间，还污染评审记录。

**派发前必做**：

```bash
python skills/pair-crew/scripts/collect_review.py --session <session_id>
```

看「最后一条 assistant 消息」的 **时间** 和 **正文**：

- 时间**晚于**我上次派发 → 它已经处理过了，**不要再发**
- 时间早于上次派发、且结论对不上我这次要说的内容 → 才需要发

> **⚠ 判断「它回没回我」不能看消息条数。**
> 实测 Qoder 在**同一条 assistant 消息**上原地更新：条数一直是 6，
> 但内容已经从「第一轮结论」换成「第三轮复核」。只看条数会得出「没回我」，
> 然后重复派发 —— 我当时就这样把第三轮发了两遍（seq=7 成功、seq=9 多余）。


#### 读回：查 IDE 数据库，不要抓页面

```bash
# 一眼看出哪些评审还没收口（最近 12 小时有活动、含明确判定）
python skills/pair-crew/scripts/collect_review.py
python skills/pair-crew/scripts/collect_review.py --title 评审 --full
python skills/pair-crew/scripts/collect_review.py --session <session_id> --full
```

> **⚠ 判读陷阱：消息条数不变 ≠ 没有新结论。**
> 实测 Qoder 会在**同一条 assistant 消息**上原地更新内容：条数一直是 6，
> 但里面已经从「第一轮结论」换成了「第三轮复核」。
> 只看条数就会得出「它没回我」的错误结论，然后重复派发、白等。
> 正确做法是看**最后一条 assistant 消息的 `updated_at` 和正文**，
> `collect_review.py` 输出的就是这个。

> **⚠ 不要靠抓页面判断「还在不在跑」。**
> `document.body.innerText` 只反映当前活动视图，用户一切走你就看到别人的会话；
> 页面上任何「生成中」字样都可能来自别的任务。以数据库里的消息时间为准。

#### 【硬性】「盯着」= 阻塞轮询，不是跑一次

**跑一次没看到判定，不等于它没回。** 外部 agent 常常还要几分钟才写完结论。
真实踩过：19:52 查一次没有判定，19:54 人家就出了「可以开工」，
我却上报「它没回应」，被告知「明明已经执行完了」。

要等就用 `--wait`，它会轮询到出现判定词才返回：

```bash
python skills/pair-crew/scripts/collect_review.py --wait --session <session_id> \
  --timeout 1800 --interval 15
```

- 退出码 `0` = 拿到判定；`2` = 超时。**超时不等于失败** —— 它可能还在跑，
  过一会再 `--wait` 一次，不要据此断言「它没回我」
- 轮询比的是**正文内容哈希**，不是消息条数（Qoder 会原地更新同一条消息，条数不变）
- 判定词优先取正文开头 300 字（结论都在第一行，正文表格里可能引用别的轮次的词）

> **⚠ 读 IDE 数据库绝对不能加 `immutable=1`。**
> 那是「这个库保证不会变」的承诺，SQLite 会跳过 WAL，只返回打开那一刻的快照。
> IDE 的新消息全在新写入的 `-wal` 里，于是条数永远不变、结论永远读不到。
> 用 `mode=ro` + `PRAGMA query_only=1`：正常读 WAL，且仍然只读。



### 8. QA

- 例子表 + Layout 清单 + 主/异常 Journey
- **明确一个评审承担验收角色**：按 `examples.yaml` 逐条打勾 + 补边界用例；不要两票都只做「代码通读」

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

### 【硬性】需要用户亲自操作的环节

下面这些**agent 做不了**，必须明确要求用户动手，**禁止**假装自动化成功、
也**禁止**用「发进当前会话凑合」这类变通绕过。凡是走到这些环节，先停下来，
把「要你做什么」一句话说清楚。

| 环节 | 为什么 agent 做不了 | agent 能推进到哪 | 该怎么跟用户说 |
|---|---|---|---|
| **在 IDE 里新建项目 / 打开文件夹** | ZCode「新项目」、Qoder「打开文件夹」都弹**原生文件夹对话框**，CDP 只能操作渲染进程内的 DOM，碰不到系统对话框 | `ide_guard.py --ide <x> --path <路径>` 判断有没有绑定，没有就列出现有目录 | 「请在 ZCode 侧栏点『新项目』→ 选 `D:\...`，这一步是系统对话框我点不到；建好我马上重派」 |
| **授予「完全访问」** | 权限弹窗由安全机制拦截，模拟点击等于绕过用户授权 | 能检测当前是不是「完全访问」 | 「请在那个任务里点『完全访问』，否则它读不到目标目录」 |
| **点排队消息的「插话 / 立即」** | 只有在 agent 生成中才出现，文案还因 IDE 而异 | `send_followup.py` 会自己找并点（ZCode=`立即`，Qoder=`插话`） | 脚本点完仍失败才需要用户：「消息卡在队列里，请手动点气泡上的『插话』」 |
| **Trae 首次信任文件夹 / 登录** | 信任弹窗在 Trae 窗口里，CDP 只能点渲染进程内的 DOM，碰它等于绕过用户授权 | `send_trae.py` 能检测到输入框、发不出就是被挡住 | 「请在 Trae 窗口里点『信任文件夹并继续』并确认已登录，然后我重派」 |
| **Story 需求确认与冻结** | 需求边界、任务拆分、测试用例必须由人拍板 | 只能拿证据出问题清单 + 倾向性建议 | 一次性呈报（读到的现状 / 目标 / 有锚点的问题 / 拆分草案 / 用例草案 / 风险） |
| **每次外部工具派发前的确认** | 花的是用户的额度、占的是用户的 IDE | 能准备好 prompt 和参数 | 「我要派给 Qoder CN（端口 9222），项目 `X`，路径 `Y`，新建任务，只读评审 —— 确认？」 |
| **评审超轮次 / 双方结论对立** | 属于裁决，不是技术问题 | 能并列两份结论和分歧点 | 「两轮下来 P0 还在，冲突点是 X，你来定」 |
| **合入 main / 对外发布** | 高风险且不可撤销 | 能准备 diff 和自检结果 | 「改动 N 个文件，自检通过，要不要合入 main」 |
| **改被审对象后重新派发** | 需要用户知道「上一轮作废」 | 能识别文件哈希变了 | 「我在评审期间改了文件，上一轮结论作废，要重派一轮」 |

**判断口诀**：凡是**系统级对话框、权限授予、花钱、不可撤销**的动作，都是人的。

### 其他需要人的场景（agent 可自愈的先自愈）

- 派发失败：`IDE_OFFLINE`（端口没起）、选不到工作空间、任务占用、选择器失效
  → 先用 `routing_check.py` / `ide_guard.py --list` 定位，定位不了再叫人
- CDP 只能读**当前活动视图**：读回内容和预期不符时，先怀疑「界面被切走了」，
  而不是「它在偷懒」

## 脚本索引

| 脚本 | 用途 |
|---|---|
| `scripts/routing_check.py` | 能力与 IDE 门禁 |
| `scripts/ide_guard.py` | **按绝对路径**核对 IDE 里的项目绑定（派发前必跑） |
| `scripts/send_qoder.py` | Qoder CN / 国际版派发（指定 CDP 端口，**新建任务**） |
| `scripts/send_zcode.py` | ZCode 派发（**新建任务**） |
| `scripts/send_trae.py` | Trae 派发（**CDP**，需带 `--remote-debugging-port` 启动；`--result-file` 读回） |
| `scripts/launch_trae_cdp.cmd` | 带调试端口启动 Trae（会先清 `ELECTRON_RUN_AS_NODE`；Trae 必须先完全退出） |
| `scripts/send_workbuddy.py` | WorkBuddy 派发（**CDP**；`--new-task` 另起任务，`--result-file` 读回） |
| `scripts/send_followup.py` | **同一会话续写**；会话归属校验 + 自动点「插话/立即」把排队消息插队 |
| `scripts/collect_review.py` | 从 IDE 数据库读回判定；`--wait` 阻塞到判定出现（**收工前必跑**） |
| `templates/*` | HANDOFF / ROUTING / STORY_KICKOFF / DISPATCH_CHECKLIST / contracts |
