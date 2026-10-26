# .agents/BOARD.md — pair-crew 车间工单板

| ID | 标题 | 状态 | 实现 | 测试 | 评审 | 优先级 | 备注 |
|---|---|---|---|---|---|---|---|
| T-smoke-001 | 通道冒烟：读契约并回报 | done | qoder | — | — | P0 | Qoder CN 绑定正确；完全访问由用户手点 |
| T-smoke-002 | 通道冒烟：WorkBuddy | done | workbuddy | — | — | P0 | 会话在 e-project_self-coding_skill；templates 含 DISPATCH_CHECKLIST |
| T-smoke-003 | 通道冒烟：ZCode | done | zcode | — | — | P0 | 项目由用户创建；完全访问开；shell 初目录为 .mimocode |
| T-smoke-004 | 通道冒烟：Qoder 国际版 | done | qoder-intl | — | — | P0 | 9225；模型 DeepSeek-Flash；「谁能用」概括正确 |

## 状态图例

`draft → ready_for_impl → in_impl → ready_for_review → in_review → ready_for_qa → in_qa → done | blocked`
