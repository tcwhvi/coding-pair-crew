# -*- coding: utf-8 -*-
"""pair-crew 开工前能力门禁：校验 ROUTING 绑定是否可用。

  python routing_check.py --routing path/to/ROUTING.yaml
  python routing_check.py --routing ROUTING.yaml --json

检查项：
  1. roles[].requires 是否被 model_groups/模型 modalities 覆盖（vision 等）
  2. 外部 IDE（qoder/mimo/workbuddy）是否在 CDP 端口上可发现
  3. CLI 工位（trae）是否装好；Trae 不走 CDP，走 `trae-cn chat`
  4. model_groups 非空字段是否已填

退出码：0 全过；1 有阻断项；2 配置/依赖错误。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from send_trae import find_cli as _find_trae
except Exception:  # vendored 单文件场景：没有 send_trae 就当 CLI 检测不可用
    _find_trae = None

PORT_RANGE = range(9222, 9236)
UA_KEYS = {
    "qoder_cn": "QoderCN",
    "qoder": "Qoder/",
    "mimo": "XiaomiMiMo",
    "workbuddy": "WorkBuddy",
    "zcode": "ZCode",
}
# 能力 → 声明位置：role.requires 或 model_groups 键名
CAP_VISION = {"vision", "image_read", "image"}
# CLI 工位：不走 CDP，按可执行文件 / 子命令探测
CLI_KEYS = {
    "trae": "trae-cn / Trae CN.exe（chat 子命令）",
}


def load_routing(path: str) -> dict:
    try:
        import yaml  # type: ignore
    except Exception:
        # 极简 fallback：只够读本仓库模板里的键值（不引第三方时的兜底）
        return _load_yaml_lite(path)
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _load_yaml_lite(path: str) -> dict:
    """仅供无 PyYAML 时读取本 skill 模板；不支持复杂 YAML。"""
    data: dict = {"model_groups": {}, "roles": {}}
    section = None
    role = None
    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.split("#", 1)[0].rstrip()
            if not line.strip():
                continue
            if not line.startswith(" ") and line.strip().endswith(":"):
                key = line.strip()[:-1]
                if key in ("model_groups", "roles"):
                    section = key
                    role = None
                else:
                    section = key
                    role = None
                continue
            if section == "model_groups" and ":" in line:
                k, v = line.split(":", 1)
                data["model_groups"][k.strip()] = v.strip().strip('"').strip("'")
            elif section == "roles":
                if line.startswith("  ") and not line.startswith("    ") and line.strip().endswith(":"):
                    role = line.strip()[:-1]
                    data["roles"][role] = {}
                elif role and ":" in line:
                    k, v = line.split(":", 1)
                    val = v.strip().strip('"').strip("'")
                    if val.startswith("[") and val.endswith("]"):
                        inner = val[1:-1].strip()
                        data["roles"][role][k.strip()] = (
                            [x.strip().strip('"').strip("'") for x in inner.split(",") if x.strip()]
                            if inner else []
                        )
                    else:
                        data["roles"][role][k.strip()] = val
    return data


def discover_ide() -> dict:
    found = {}
    for port in PORT_RANGE:
        try:
            with urllib.request.urlopen(
                f"http://127.0.0.1:{port}/json/version", timeout=1.2
            ) as r:
                ua = json.loads(r.read().decode("utf-8")).get("User-Agent", "")
        except Exception:
            continue
        for name, key in UA_KEYS.items():
            if key in ua:
                found[name] = {"port": port, "ua": ua[:80]}
    return found


def discover_cli() -> dict:
    found = {}
    for name in CLI_KEYS:
        if name == "trae":
            try:
                found[name] = bool(_find_trae and _find_trae())
            except Exception:
                found[name] = False
    return found


def check(routing: dict) -> tuple[list[dict], dict, dict]:
    issues = []
    groups = routing.get("model_groups") or {}
    roles = routing.get("roles") or {}
    ide = discover_ide()
    cli = discover_cli()

    for gname, gval in groups.items():
        if gval in ("", None):
            issues.append({
                "level": "warn",
                "code": "MODEL_GROUP_EMPTY",
                "msg": f"model_groups.{gname} 未填写",
            })

    for rname, rcfg in roles.items():
        if not isinstance(rcfg, dict):
            continue
        reqs = rcfg.get("requires") or []
        model = rcfg.get("model") or ""
        runtime = rcfg.get("runtime") or ""
        tool = rcfg.get("tool") or ""

        # vision 能力门禁
        need_vision = bool(CAP_VISION.intersection(set(reqs)))
        model_is_vision = (model == "vision") or (model in str(groups.get("vision") or ""))
        if need_vision and not model_is_vision:
            issues.append({
                "level": "error",
                "code": "VISION_REQUIRED",
                "msg": f"角色 {rname} 需要 vision/image_read，但 model={model!r} 不是 vision 绑定",
            })

        # CLI 工位在线（trae：不走 CDP，走 chat 子命令）
        if tool in CLI_KEYS or runtime == "cli":
            t = tool or "trae"
            if t not in CLI_KEYS:
                issues.append({
                    "level": "warn",
                    "code": "TOOL_UNKNOWN",
                    "msg": f"角色 {rname} 的 CLI tool={t!r} 不在已知集合 {list(CLI_KEYS)}",
                })
            elif not cli.get(t):
                issues.append({
                    "level": "error",
                    "code": "TOOL_OFFLINE",
                    "msg": f"角色 {rname} 依赖 {t}，但未找到 {CLI_KEYS[t]}；"
                           "装 Trae 或设 TRAE_CLI 指向 bin\\trae-cn.cmd",
                })

        # 外部 IDE 在线
        elif runtime == "external-ide" or tool in UA_KEYS:
            t = tool or ""
            if t in UA_KEYS and t not in ide:
                issues.append({
                    "level": "error",
                    "code": "IDE_OFFLINE",
                    "msg": f"角色 {rname} 依赖 {t}，但 CDP 未发现（端口 9222-9235）",
                })
            elif t and t not in UA_KEYS:
                issues.append({
                    "level": "warn",
                    "code": "TOOL_UNKNOWN",
                    "msg": f"角色 {rname} 的 tool={t!r} 不在已知集合 {list(UA_KEYS)}",
                })

        # 思考档粗检
        reasoning = rcfg.get("reasoning")
        if reasoning and reasoning not in (
            "low", "medium", "high", "xhigh", "max", ""
        ):
            issues.append({
                "level": "warn",
                "code": "REASONING_UNUSUAL",
                "msg": f"角色 {rname} reasoning={reasoning!r} 不在常见档位集合",
            })

    if not ide and not any(cli.values()):
        issues.append({
            "level": "warn",
            "code": "NO_IDE",
            "msg": "未发现任何外部 IDE（Qoder/MiMo/WorkBuddy）或 CLI 工位（Trae）；可退回 actor/会话",
        })
    return issues, ide, cli


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--routing", required=True, help="ROUTING.yaml 路径")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if not os.path.isfile(args.routing):
        print(f"routing_check: 文件不存在 {args.routing}")
        return 2

    try:
        routing = load_routing(args.routing)
    except Exception as e:
        print(f"routing_check: 解析失败 {e}")
        return 2

    issues, ide, cli = check(routing)
    errors = [i for i in issues if i["level"] == "error"]
    warns = [i for i in issues if i["level"] == "warn"]

    if args.json:
        print(json.dumps({
            "ok": not errors,
            "ide": ide,
            "cli": cli,
            "errors": errors,
            "warns": warns,
        }, ensure_ascii=False, indent=2))
    else:
        print("== routing_check ==")
        print("IDE:", json.dumps(ide, ensure_ascii=False))
        print("CLI:", json.dumps(cli, ensure_ascii=False))
        for i in errors:
            print(f"[ERROR] {i['code']}: {i['msg']}")
        for i in warns:
            print(f"[WARN]  {i['code']}: {i['msg']}")
        print(f"结果: {'PASS' if not errors else 'FAIL'} ({len(errors)} err / {len(warns)} warn)")

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
