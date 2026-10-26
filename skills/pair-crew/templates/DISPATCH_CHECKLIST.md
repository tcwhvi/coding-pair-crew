# pair-crew 派发前检查清单（每次派发前过一遍）

## 必须与用户确认

- [ ] 目标工具（qoder / qoder-cn / workbuddy / zcode / mimo）
- [ ] `--project-name` 与 IDE 工作区名一致
- [ ] `--project-path` 绝对路径正确
- [ ] 新建任务还是续写
- [ ] 任务内容与 SCOPE（是否只读）
- [ ] **文件完全访问是否已授予 / 需要点掉弹窗**

## 脚本/环境自检

- [ ] `routing_check.py` 无 ERROR（含 VISION_REQUIRED / IDE_OFFLINE）
- [ ] CDP 端口可发现该 IDE（9222–9235）
- [ ] 该工作区在 IDE 侧已存在（否则先注册，如 Qoder `workspaces` 表）
- [ ] 目标 IDE 无进行中任务（避免抢占）

## 派发后

- [ ] 读回是否包含**真实绝对路径**（否则多半是工作区或权限问题）
- [ ] 核对只读约束是否被遵守（未改文件）
- [ ] 写进 BOARD / HANDOFF

## 权限说明

| IDE | 完全访问 | 自动化现状 |
|---|---|---|
| WorkBuddy | 「允许完全访问」按钮 | `review_dispatch` 可点；失败则人工；新工作区需重启后可搜 |
| Qoder CN / 国际版 | 任务内文件访问确认 | **当前多靠人工点**；工作区可写 `main.sqlite` workspaces 表后 reload UI |
| ZCode | 「完全访问」开关 + 信任文件夹 | 项目创建含原生文件夹框，建议**人工建一次项目**；发消息可用 `send_zcode.py` |
| MiMo IDE | 项目已加入则较顺 | 待实践 |
