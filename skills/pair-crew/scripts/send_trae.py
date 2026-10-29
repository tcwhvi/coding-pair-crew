# -*- coding: utf-8 -*-
"""pair-crew 向 Trae 发送任务（CDP）。

Trae 的 `chat` 子命令在本机（Trae CN 3.4.9 / cli 1.107.1）实测注不进对话，
所以这里走 CDP：和 Qoder / ZCode 一样，直接操作渲染进程里的对话面板。

前置（必须）：
  1. Trae 用调试端口启动：`Trae CN.exe --remote-debugging-port=9226 <项目路径>`
  2. 从脚本/自动化里启动时，务必先清掉 `ELECTRON_RUN_AS_NODE`
     （带着它启动，exe 会以 Node 模式跑，直接退出、不起窗口）
  3. 目标项目已经在该窗口打开（脚本会按窗口标题核对，不匹配就拒发）

行为：
  1. 连 CDP，核对窗口标题里含项目目录名
  2. 找不到对话输入框时，点侧栏聊天入口把它打开
  3. 把 prompt 注入 Lexical 输入框 → 点发送 → 确认输入框已清空
  4. 可选：等 --result-file 落地。Trae 的聊天库是加密的，只能靠结果文件读回

  python send_trae.py --port 9226 --project-path D:\\projects\\xxx ^
    --text-file prompt.md --result-file contracts/T-xxx/review/P1-trae.md --wait
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
for _p in (
    os.path.expanduser(r"~\.agents\skills\external-review\scripts"),
    os.path.join(os.path.dirname(__file__), "vendor", "external-review"),
):
    if os.path.isdir(_p) and _p not in sys.path:
        sys.path.insert(0, _p)
from cdp import Page, list_targets  # noqa: E402

COMPOSER = '.chat-input-v2-input-box-editable'
SEND_BUTTON = 'button.chat-input-v2-send-button'
CHAT_ROOT = '.ai-chat-v2-ide-root'
LAUNCHER = '.icube-side-chat-launcher-component'


def first_page(port: int):
    for t in list_targets(port):
        if t.get("type") == "page" and t.get("url"):
            return t
    return None


def js_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def click_center(page: Page, selector: str, wait: float = 0.8) -> bool:
    rect = page.eval_js(
        "(() => { const b = document.querySelector(" + js_string(selector) + ");"
        " if (!b) return null;"
        " const r = b.getBoundingClientRect();"
        " if (!r.width) return null;"
        " return {x: r.x + r.width/2, y: r.y + r.height/2}; })()"
    )
    if not rect:
        return False
    page.cmd("Input.dispatchMouseEvent", type="mouseMoved", x=rect["x"], y=rect["y"])
    page.cmd("Input.dispatchMouseEvent", type="mousePressed", x=rect["x"], y=rect["y"],
             button="left", clickCount=1)
    page.cmd("Input.dispatchMouseEvent", type="mouseReleased", x=rect["x"], y=rect["y"],
             button="left", clickCount=1)
    time.sleep(wait)
    return True


def composer_state(page: Page) -> dict:
    return page.eval_js(
        "(() => {"
        " const ed = document.querySelector(" + js_string(COMPOSER) + ");"
        " const btn = document.querySelector(" + js_string(SEND_BUTTON) + ");"
        " const root = document.querySelector(" + js_string(CHAT_ROOT) + ");"
        " return {"
        "  title: document.title,"
        "  hasEditor: !!ed,"
        "  text: ed ? (ed.innerText || '') : null,"
        "  hasSend: !!btn,"
        "  sendDisabled: btn ? btn.className.includes('disabled') : null,"
        "  hasChatRoot: !!root"
        " }; })()"
    )


def ensure_chat_open(page: Page) -> bool:
    state = composer_state(page)
    if state and state.get("hasEditor"):
        return True
    click_center(page, LAUNCHER, wait=1.5)
    state = composer_state(page)
    return bool(state and state.get("hasEditor"))


def focus_and_clear(page: Page) -> bool:
    return bool(page.eval_js(
        "(() => {"
        " const ed = document.querySelector(" + js_string(COMPOSER) + ");"
        " if (!ed) return false;"
        " ed.focus();"
        " const r = document.createRange();"
        " r.selectNodeContents(ed);"
        " const s = window.getSelection();"
        " s.removeAllRanges(); s.addRange(r);"
        " return true; })()"
    ))


def send_prompt(page: Page, text: str) -> tuple[bool, str]:
    if not focus_and_clear(page):
        return False, "找不到对话输入框"
    page.cmd("Input.insertText", text=text)
    time.sleep(0.6)
    state = composer_state(page)
    typed = (state or {}).get("text") or ""
    if not typed.strip():
        return False, "输入框里没写进去（Lexical 没接住 insertText）"
    if state.get("sendDisabled"):
        return False, "发送按钮仍是禁用态"
    clicked = page.eval_js(
        "(() => { const b = document.querySelector(" + js_string(SEND_BUTTON) + ");"
        " if (!b) return 'missing';"
        " if (b.className.includes('disabled')) return 'disabled';"
        " b.click(); return 'clicked'; })()"
    )
    if clicked != "clicked":
        return False, f"点发送失败：{clicked}"
    for _ in range(10):
        time.sleep(0.5)
        after = composer_state(page)
        if after and not ((after.get("text") or "").strip()):
            return True, "sent"
    return False, "点了发送但输入框没清空，消息可能没发出去"


def wait_for_result(path: str, started_at: float, timeout: int, interval: int) -> bool:
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
    ap.add_argument("--port", type=int, default=9226)
    ap.add_argument("--project-name", default="", help="仅用于日志/BOARD 记录")
    ap.add_argument("--project-path", required=True, help="Trae 窗口里必须已经打开这个目录")
    ap.add_argument("--text-file", required=True)
    ap.add_argument("--result-file", default="", help="约定对方写出的结论文件（相对 --project-path 或绝对路径）")
    ap.add_argument("--wait", action="store_true", help="阻塞等 --result-file 落地")
    ap.add_argument("--timeout", type=int, default=1800)
    ap.add_argument("--interval", type=int, default=15)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    project_path = os.path.abspath(args.project_path)
    if not os.path.isdir(project_path):
        print(f"trae: 项目目录不存在，拒绝派发：{project_path}")
        return 1
    if not os.path.isfile(args.text_file):
        print(f"trae: prompt 文件不存在：{args.text_file}")
        return 1
    prompt = open(args.text_file, "r", encoding="utf-8").read()

    result_path = ""
    if args.result_file:
        result_path = args.result_file if os.path.isabs(args.result_file) \
            else os.path.join(project_path, args.result_file)
        result_path = os.path.normpath(result_path)
        prompt += (
            f"\n\n---\n完成后把最终结论写入 {result_path}（绝对路径），"
            "文件第一行只写判定：可以开工 / 改完 P0 再开工 / 换方案 / 还不能开工。"
        )
    prompt = f"项目根：{project_path}\n\n{prompt}"

    target = first_page(args.port)
    if not target:
        print(f"trae: {args.port} 端口上没有可用的页面。请用 "
              f"`Trae CN.exe --remote-debugging-port={args.port} <项目路径>` 启动 Trae，"
              "并确认脚本环境里没有 ELECTRON_RUN_AS_NODE")
        return 1

    page = Page(args.port, target)
    started_at = time.time()
    try:
        state = composer_state(page)
        title = (state or {}).get("title") or ""
        folder = os.path.basename(project_path.rstrip("\\/"))
        if folder not in title:
            print(f"trae: 窗口标题是「{title}」，里面没有「{folder}」——拒绝派发。")
            print("trae: 请在 Trae 里打开该目录，或用带路径参数的方式启动 Trae。")
            return 1
        print(f"trae: 项目 = {args.project_name or folder} | 窗口 = {title}")

        if args.dry_run:
            print("trae: dry-run，不实际发送")
            return 0

        if not ensure_chat_open(page):
            print("trae: 打不开对话面板（找不到输入框，侧栏入口也没反应）")
            return 1

        ok, detail = send_prompt(page, prompt)
        if not ok:
            print(f"trae: 发送失败——{detail}")
            return 1
        print(f"trae: SENT（{len(prompt)} 字，已确认输入框清空）")

        if not result_path:
            print("trae: 未指定 --result-file，无法自动读回")
            print(json.dumps({"trae": "SENT", "result": "NOT_REQUESTED"}, ensure_ascii=False))
            return 0
        if not args.wait:
            print(f"trae: 已要求在 {result_path} 写结论；加 --wait 可阻塞等它落地")
            print(json.dumps({"trae": "SENT", "result_file": result_path,
                              "result": "PENDING"}, ensure_ascii=False))
            return 0

        print(f"trae: 等 {result_path}（上限 {args.timeout}s，每 {args.interval}s 查一次）")
        if wait_for_result(result_path, started_at, args.timeout, args.interval):
            text = open(result_path, "r", encoding="utf-8", errors="replace").read()
            print("trae: 已读回结果文件，前 800 字：")
            print(text[:800])
            print(json.dumps({"trae": "SENT", "result_file": result_path,
                              "result": "READ"}, ensure_ascii=False))
            return 0
        print(f"trae: 超时——{result_path} 未出现/未更新。去 Trae 窗口看对话是否还在跑；"
              "还在跑就过一会再查，没反应就重派")
        print(json.dumps({"trae": "SENT", "result_file": result_path,
                          "result": "TIMEOUT"}, ensure_ascii=False))
        return 2
    finally:
        page.close()


if __name__ == "__main__":
    sys.exit(main())
