# -*- coding: utf-8 -*-
"""pair-crew 向 Trae 派发任务（CLI，不是 CDP）。

Trae CN / Trae 自带 `chat` 子命令，能在**当前工作目录**打开 chat 并直接提交 prompt：

  trae-cn chat -m agent --add-file prompt.md "<instruction>"

所以 Trae 这条通道不需要调试端口，也不走 ide_guard：
  - 项目归属 = 进程 cwd（--project-path）；目录不存在直接拒绝
  - 读回 = prompt 里要求把结论写到 --result-file，脚本轮询这个文件
  - Trae 的聊天库（ModularData/ai-agent/database.db）不是明文 SQLite，不能像
    Qoder / ZCode 那样直接读库，所以不要假装能 collect_review

  python send_trae.py --project-path E:\\project_self\\coding_skill ^
    --text-file prompt.md --result-file contracts/T-xxx/review/P1-trae.md --wait

已知问题（2026-10-29 实测，Trae CN 3.4.9 + 内置 cli 1.107.1）：
  CLI 能启动、退出码 0，但两个 Trae 面都不接——IDE 对话面板停在「与 AI 对话」占位、
  Agent 任务列表没有新任务、结果文件不会出现。五种调用结果一致：`-m agent --add-file`、
  `-n -m ask`、先 `cli.js -r <项目>` 再 `chat -r -m agent`、Agent 窗口置前、不带附件的
  最小 `chat -m ask -r`。`chat -r` 还曾把窗口重置成空工作区（需再跑 `cli.js -r <项目>` 找回）。
  所以这个脚本目前只算「已接线、未验证」：超时不要当成「它还在跑」，
  先去 Trae 窗口肉眼确认对话/任务真的出现了；没有就是没派成。
  聊天库是加密的（ModularData/ai-agent/database.db 打不开），没有第二条读回通道。
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")


def _install_from(path: str) -> str | None:
    """把 trae-cn.cmd / Trae CN.exe / 安装目录都归一成安装目录。"""
    p = os.path.normpath(path)
    if os.path.isdir(p):
        return p
    low = p.lower()
    if low.endswith((".cmd", ".bat")):
        return os.path.dirname(os.path.dirname(p))
    if low.endswith(".exe"):
        return os.path.dirname(p)
    return None


def find_cli() -> tuple[str, str] | None:
    """返回 (Trae 可执行文件, cli.js)。找不到返回 None。"""
    cands: list[str] = []
    env_hint = os.environ.get("TRAE_CLI", "").strip()
    if env_hint:
        cands.append(env_hint)
    for name in ("trae-cn", "trae"):
        w = shutil.which(name)
        if w:
            cands.append(w)
    roots = [
        os.environ.get("ProgramFiles", ""),
        os.environ.get("ProgramFiles(x86)", ""),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs")
        if os.environ.get("LOCALAPPDATA") else "",
        r"E:\Programs",
        r"D:\Programs",
    ]
    for root in roots:
        if not root:
            continue
        for app in ("Trae CN", "Trae"):
            cands.append(os.path.join(root, app))

    for c in cands:
        install = _install_from(c)
        if not install:
            continue
        cli_js = os.path.join(install, "resources", "app", "out", "cli.js")
        for exe_name in ("Trae CN.exe", "Trae.exe", "trae-cn.exe", "trae.exe"):
            exe = os.path.join(install, exe_name)
            if os.path.isfile(exe) and os.path.isfile(cli_js):
                return exe, cli_js
    return None


def _result_abs(project_path: str, result_file: str) -> str:
    if not result_file:
        return ""
    if os.path.isabs(result_file):
        return os.path.normpath(result_file)
    return os.path.normpath(os.path.join(project_path, result_file))


def wait_for_result(path: str, started_at: float, timeout: int, interval: int) -> bool:
    """等结果文件出现或更新。已存在的旧文件不算，必须晚于本次派发。"""
    while True:
        if os.path.isfile(path):
            try:
                if os.path.getmtime(path) >= started_at:
                    return True
            except OSError:
                pass
        if time.time() - started_at > timeout:
            return False
        time.sleep(max(1, interval))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-path", required=True, help="目标项目绝对路径（作为 chat 的 cwd）")
    ap.add_argument("--project-name", default="", help="仅用于日志/BOARD 记录")
    ap.add_argument("--text-file", required=True, help="prompt 文件，会作为附件注入")
    ap.add_argument("--result-file", default="",
                    help="要求对方写出的结论文件（相对 --project-path 或绝对路径）")
    ap.add_argument("--mode", default="agent", help="chat 模式：agent | ask | edit（默认 agent）")
    ap.add_argument("--new-window", action="store_true", help="强制新开窗口")
    ap.add_argument("--reuse-window", action="store_true", help="复用最近活动窗口")
    ap.add_argument("--wait", action="store_true", help="阻塞等到 --result-file 落地")
    ap.add_argument("--timeout", type=int, default=1800, help="等结果的上限秒数（默认 1800）")
    ap.add_argument("--interval", type=int, default=15, help="轮询间隔秒数（默认 15）")
    ap.add_argument("--launch-timeout", type=int, default=180, help="CLI 交接超时秒数（默认 180）")
    ap.add_argument("--dry-run", action="store_true", help="只打印将执行的命令，不派发")
    args = ap.parse_args()

    project_path = os.path.abspath(args.project_path)
    if not os.path.isdir(project_path):
        print(f"trae: 项目目录不存在，拒绝派发：{project_path}")
        return 1
    prompt_path = os.path.abspath(args.text_file)
    if not os.path.isfile(prompt_path):
        print(f"trae: prompt 文件不存在：{prompt_path}")
        return 1

    result_path = _result_abs(project_path, args.result_file)
    found = find_cli()
    if not found:
        print("trae: 未找到 trae-cn / Trae CN.exe。请确认已安装 Trae，"
              "或设置环境变量 TRAE_CLI 指向 bin\\trae-cn.cmd")
        return 1
    exe, cli_js = found

    instruction = (
        f"请先完整读取附件 {os.path.basename(prompt_path)}，按其中的任务、约束和验收要求执行。"
        f"项目根目录：{project_path}。"
    )
    if result_path:
        instruction += (
            f"完成后把最终结论写入 {result_path}（绝对路径），"
            "文件第一行给出明确判定（例如：可以开工 / 还不能开工）。"
        )

    cmd = [exe, cli_js, "chat", "-m", args.mode]
    if args.new_window:
        cmd.append("-n")
    if args.reuse_window:
        cmd.append("-r")
    cmd += ["--add-file", prompt_path, instruction]

    print("trae: 项目 =", args.project_name or os.path.basename(project_path), project_path)
    print("trae: 命令 =", subprocess.list2cmdline(cmd))
    if args.dry_run:
        return 0

    env = dict(os.environ)
    env["ELECTRON_RUN_AS_NODE"] = "1"
    env["VSCODE_DEV"] = ""
    started_at = time.time()
    try:
        p = subprocess.run(cmd, cwd=project_path, env=env, capture_output=True,
                           text=True, encoding="utf-8", errors="replace",
                           timeout=max(30, args.launch_timeout))
    except subprocess.TimeoutExpired:
        print(f"trae: CLI {args.launch_timeout}s 未返回；窗口可能仍在校验/启动，"
              "先按已派发处理，下面继续等结果文件")
        p = None
    except OSError as e:
        print(f"trae: 启动 CLI 失败：{e}")
        return 1
    if p is not None:
        out = (p.stdout or "").strip()
        err = (p.stderr or "").strip()
        if out:
            print("trae: stdout =", out[:800])
        if err:
            print("trae: stderr =", err[:800])
        if p.returncode != 0:
            print(f"trae: CLI 退出码 {p.returncode}，判定 FAILED")
            print(json.dumps({"trae": "FAILED", "project_path": project_path}, ensure_ascii=False))
            return 1

    print("trae: SENT（Trae 自己会开 chat 跑；它的聊天库加密，读回只认结果文件）")

    if not result_path:
        print("trae: 未指定 --result-file，无法自动读回；请在 Trae 窗口里看结论，或下一轮带上结果文件")
        print(json.dumps({"trae": "SENT", "project_path": project_path,
                          "result": "NOT_REQUESTED"}, ensure_ascii=False))
        return 0

    if not args.wait:
        print(f"trae: 已要求在 {result_path} 写结论；加 --wait 可阻塞等它落地")
        print(json.dumps({"trae": "SENT", "project_path": project_path,
                          "result_file": result_path, "result": "PENDING"},
                         ensure_ascii=False))
        return 0

    print(f"trae: 等 {result_path}（上限 {args.timeout}s，每 {args.interval}s 查一次）")
    if wait_for_result(result_path, started_at, args.timeout, args.interval):
        try:
            text = open(result_path, "r", encoding="utf-8", errors="replace").read()
        except OSError as e:
            print(f"trae: 结果文件读失败：{e}")
            return 1
        print("trae: 已读回结果文件，前 800 字：")
        print(text[:800])
        print(json.dumps({"trae": "SENT", "project_path": project_path,
                          "result_file": result_path, "result": "READ"},
                         ensure_ascii=False))
        return 0

    print(f"trae: 超时——{result_path} 未出现/未更新。")
    print("trae: 先去 Trae 窗口确认有没有真的开出对话：本机实测 CLI 会以退出码 0 结束、")
    print("trae: 却不在窗口里生成对话（Trae CN 3.4.9 / cli 1.107.1）；窗口里没有对话就是没派成，")
    print("trae: 不要当成「还在跑」。有对话在跑时，过一会再查结果文件即可。")
    print(json.dumps({"trae": "SENT", "project_path": project_path,
                      "result_file": result_path, "result": "TIMEOUT"},
                     ensure_ascii=False))
    return 2


if __name__ == "__main__":
    sys.exit(main())
