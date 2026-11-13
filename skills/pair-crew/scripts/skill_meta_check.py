# -*- coding: utf-8 -*-
"""pair-crew 自动触发自检：检查 SKILL.md 的 frontmatter 会不会被宿主识别。

  python skill_meta_check.py
  python skill_meta_check.py --skill path/to/SKILL.md
  python skill_meta_check.py --json

检查项：
  1. 文件以 YAML frontmatter 开头，name / description 非空
  2. description 覆盖「写新代码 / 改现有代码」这类意图，而不是只写产品名和命令
  3. 没有禁用「模型自动调用」的开关（disable-model-invocation / user_invocable_only 等）

退出码：0 全过；1 有阻断项；2 文件 / 解析错误。
只能检查元数据，不能证明宿主真的加载了它 —— 实际验证要新开会话提一句不点名的改码需求。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

# 用户真实会说的动作词；描述里至少要覆盖到，宿主才有东西可匹配
INTENT_WORDS = (
    "写代码", "改代码", "加功能", "新需求", "修改", "现有代码", "修 bug", "修bug",
    "重构", "补测试", "接口", "UI", "implement", "add", "fix", "refactor", "modify",
)
# 宿主侧把 skill 设成「只能用户点名」的开关；历史字段名一并覆盖
DISABLE_KEYS = re.compile(
    r"(disable[-_]model[-_]invocation|user[-_]invocable[-_]only|"
    r"user[-_]invocable|model[-_]invocation|invocation)",
    re.I,
)


def read_frontmatter(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        lines = f.read().splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("文件开头没有 '---'，宿主不会把它当作 skill 元数据")
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        raise ValueError("frontmatter 没有结束的 '---'")

    data: dict = {}
    key = None
    for raw in lines[1:end]:
        if raw.strip().startswith("#") or not raw.strip():
            continue
        m = re.match(r"^([A-Za-z0-9_.-]+)\s*:\s*(.*)$", raw)
        if m:
            key, val = m.group(1), m.group(2).strip()
            data[key] = "" if val in ("|", ">") else val.strip('"').strip("'")
        elif key and raw.startswith((" ", "\t")) and data.get(key) == "":
            data[key] = raw.strip()
        elif key and raw.startswith((" ", "\t")):
            data[key] += " " + raw.strip()
    return data


def main() -> int:
    ap = argparse.ArgumentParser(description="检查 pair-crew 的自动触发元数据")
    default = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "SKILL.md")
    ap.add_argument("--skill", default=default, help="SKILL.md 路径")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args()

    path = os.path.abspath(args.skill)
    try:
        meta = read_frontmatter(path)
    except (OSError, ValueError) as e:
        print("ERROR: %s" % e)
        return 2

    checks = []

    def add(name: str, ok: bool, detail: str) -> None:
        checks.append({"check": name, "ok": bool(ok), "detail": detail})

    name = meta.get("name", "").strip()
    desc = meta.get("description", "").strip()
    add("frontmatter name", bool(name), name or "缺 name")
    add("frontmatter description", bool(desc), desc or "缺 description")

    hits = sorted({w for w in INTENT_WORDS if w.lower() in desc.lower()})
    add("写码意图覆盖", len(hits) >= 3,
        "命中 %d 个：%s（至少 3 个）" % (len(hits), "、".join(hits) or "无"))

    disabled = []
    for k, v in meta.items():
        if DISABLE_KEYS.search(k) and str(v).strip().lower() in ("true", "on", "off", "false", "1"):
            disabled.append("%s=%s" % (k, v))
    add("未被设为仅用户可调用", not disabled,
        "发现开关：%s" % ", ".join(disabled) if disabled else "无禁用自动调用的开关")

    ok = all(c["ok"] for c in checks)
    if args.json:
        print(json.dumps({"skill": path, "ok": ok, "description": desc,
                          "checks": checks}, ensure_ascii=False, indent=2))
    else:
        print("skill: %s" % path)
        print("宿主注入的 description:\n  %s" % (desc[:400] + ("…" if len(desc) > 400 else "")))
        for c in checks:
            print("[%s] %s — %s" % ("OK" if c["ok"] else "FAIL", c["check"], c["detail"]))
        print("结论：%s" % ("元数据可被自动发现（仍需新开会话实测）" if ok else "自动触发会被挡住，按 FAIL 项修"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
