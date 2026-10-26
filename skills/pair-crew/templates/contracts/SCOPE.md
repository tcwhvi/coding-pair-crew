# SCOPE — 允许改 / 禁止改

## 允许修改

- `src/**`
- `tests/**`

## 禁止修改（越界即门禁失败）

- `**/pom.xml`、`**/package-lock.json`（依赖）
- 无关模块路径

## 检查方式

- `git diff --name-only` 必须全部落在「允许」内
- 脚本：`pair_scope_check`
