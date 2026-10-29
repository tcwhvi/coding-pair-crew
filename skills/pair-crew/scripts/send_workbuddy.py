# -*- coding: utf-8 -*-
"""pair-crew 向 WorkBuddy 发送任务（CDP）。

WorkBuddy（V5.9.x）是 Electron 应用，对话面在渲染进程里，可以像 Qoder/ZCode 一样
用 CDP 直接写输入框、点发送。

前置：
  1. WorkBuddy 用调试端口启动：`WorkBuddy.exe --remote-debugging-port=9228`
     （必须先完全退出；单实例下后启动的进程只会把参数转给已有实例）
  2. 它读本地文件需要「允许完全访问」；没有这个权限时任务会跑失败

行为：
  1. 连 CDP
  2. 可选 --new-task：先点侧栏「新建任务」，避免把评审塞进用户正在看的会话
  3. 往输入框注入 prompt → 点「发送」→ 确认输入框已清空
  4. 可选 --result-file --wait：等结果文件落地（WorkBuddy 的会话内容不方便程序化读）

  python send_workbuddy.py --port 9228 --text-file prompt.md \
    --result-file contracts/T/review/P1-workbuddy.md --new-task --wait
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

COMPOSER = '.conversation-input-area [role="textbox"]'
# 点「新建任务」后输入框不再挂在 .conversation-input-area 下，退回通用选择器
COMPOSER_JS = (
    "document.querySelector('.conversation-input-area [role=\"textbox\"]')"
    " || document.querySelector('[role=\"textbox\"]')"
    " || document.querySelector('div[contenteditable=\"true\"]')"
)
SEND_BUTTON = 'button[aria-label="发送"]'


def first_page(port: int):
    for t in list_targets(port):
        if t.get("type") == "page" and t.get("url"):
            return t
    return None


def js_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def state(page: Page) -> dict:
    return page.eval_js(
        "(() => {"
        " const ed = " + COMPOSER_JS + ";"
        " const btn = document.querySelector(" + js_string(SEND_BUTTON) + ");"
        " return { title: document.title, hasEditor: !!ed,"
        "  text: ed ? (ed.innerText || '') : null,"
        "  hasSend: !!btn, sendDisabled: btn ? !!btn.disabled : null }; })()"
    )


def click_center(page: Page, selector: str, wait: float = 1.0) -> bool:
    rect = page.eval_js(
        "(() => { const b = document.querySelector(" + js_string(selector) + ");"
        " if (!b) return null; const r = b.getBoundingClientRect();"
        " if (!r.width) return null; return {x: r.x + r.width/2, y: r.y + r.height/2}; })()"
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


def click_text_button(page: Page, text: str, wait: float = 1.5) -> bool:
    rect = page.eval_js(
        "(() => { const t = " + js_string(text) + ";"
        " const els = Array.from(document.querySelectorAll('button, [role=\"button\"], div, span'));"
        " const hit = els.find(e => (e.innerText || '').trim() === t && (e.offsetWidth || e.offsetHeight));"
        " if (!hit) return null; const r = hit.getBoundingClientRect();"
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


def send_text(page: Page, text: str) -> tuple[bool, str]:
    focused = page.eval_js(
        "(() => { const ed = " + COMPOSER_JS + ";"
        " if (!ed) return false; ed.focus();"
        " const r = document.createRange(); r.selectNodeContents(ed);"
        " const s = window.getSelection(); s.removeAllRanges(); s.addRange(r); return true; })()"
    )
    if not focused:
        return False, "找不到输入框"
    page.cmd("Input.insertText", text=text)
    time.sleep(0.8)
    st = state(page)
    if not ((st or {}).get("text") or "").strip():
        return False, "输入框没写进去"
    clicked = page.eval_js(
        "(() => { const b = document.querySelector(" + js_string(SEND_BUTTON) + ");"
        " if (!b) return 'missing'; if (b.disabled) return 'disabled'; b.click(); return 'clicked'; })()"
    )
    if clicked != "clicked":
        return False, f"点发送失败：{clicked}"
    # 新任务视图里输入框不会清空（草稿还在），所以再加一条：气泡里能看到这段文字也算发出去了
    marker = " ".join(text.split())[:40]
    for _ in range(24):
        time.sleep(0.5)
        st = state(page)
        if st and not ((st.get("text") or "").strip()):
            return True, "sent"
        if marker and page.eval_js("document.body.innerText.replace(/\\s+/g, ' ').includes(" + js_string(marker) + ")"):
            return True, "sent (消息已出现在会话里)"
    return False, "点了发送但既没清空输入框、会话里也没出现这段文字"


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
    ap.add_argument("--port", type=int, default=9228)
    ap.add_argument("--project-path", default="", help="仅用于把项目根写进 prompt")
    ap.add_argument("--text-file", required=True)
    ap.add_argument("--result-file", default="")
    ap.add_argument("--new-task", action="store_true", help="先点侧栏「新建任务」，别塞进用户正开着的会话")
    ap.add_argument("--wait", action="store_true")
    ap.add_argument("--timeout", type=int, default=1800)
    ap.add_argument("--interval", type=int, default=15)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not os.path.isfile(args.text_file):
        print(f"workbuddy: prompt 文件不存在：{args.text_file}")
        return 1
    prompt = open(args.text_file, "r", encoding="utf-8").read()

    result_path = ""
    if args.result_file:
        result_path = args.result_file
        if args.project_path and not os.path.isabs(result_path):
            result_path = os.path.normpath(os.path.join(os.path.abspath(args.project_path), result_path))
        prompt += (
            f"\n\n---\n完成后把最终结论写入 {result_path}（绝对路径），"
            "文件第一行只写判定：可以开工 / 改完 P0 再开工 / 换方案 / 还不能开工。"
        )
    if args.project_path:
        prompt = f"项目根：{os.path.abspath(args.project_path)}\n\n{prompt}"

    target = first_page(args.port)
    if not target:
        print(f"workbuddy: {args.port} 端口上没有页面。请用 "
              f"`WorkBuddy.exe --remote-debugging-port={args.port}` 启动，并确认已完全退出旧实例")
        return 1

    page = Page(args.port, target)
    started_at = time.time()
    try:
        st = state(page)
        print(f"workbuddy: 窗口 = {(st or {}).get('title')}")
        if args.dry_run:
            print("workbuddy: dry-run，不实际发送")
            return 0
        if args.new_task:
            if click_text_button(page, "新建任务", wait=1.5):
                print("workbuddy: 已点「新建任务」")
            else:
                print("workbuddy: 没找到「新建任务」按钮，继续在当前会话发送")
        if not (state(page) or {}).get("hasEditor"):
            print("workbuddy: 找不到对话输入框")
            return 1
        ok, detail = send_text(page, prompt)
        if not ok:
            print(f"workbuddy: 发送失败——{detail}")
            return 1
        print(f"workbuddy: SENT（{len(prompt)} 字，已确认输入框清空）")

        if not result_path:
            print("workbuddy: 未指定 --result-file，无法自动读回")
            print(json.dumps({"workbuddy": "SENT", "result": "NOT_REQUESTED"}, ensure_ascii=False))
            return 0
        if not args.wait:
            print(f"workbuddy: 已要求在 {result_path} 写结论；加 --wait 可阻塞等它落地")
            print(json.dumps({"workbuddy": "SENT", "result_file": result_path,
                              "result": "PENDING"}, ensure_ascii=False))
            return 0

        print(f"workbuddy: 等 {result_path}（上限 {args.timeout}s，每 {args.interval}s 查一次）")
        if wait_for_result(result_path, started_at, args.timeout, args.interval):
            text = open(result_path, "r", encoding="utf-8", errors="replace").read()
            print("workbuddy: 已读回结果文件，前 800 字：")
            print(text[:800])
            print(json.dumps({"workbuddy": "SENT", "result_file": result_path,
                              "result": "READ"}, ensure_ascii=False))
            return 0
        print(f"workbuddy: 超时——{result_path} 未出现/未更新。去 WorkBuddy 窗口看任务是否还在跑")
        print(json.dumps({"workbuddy": "SENT", "result_file": result_path,
                          "result": "TIMEOUT"}, ensure_ascii=False))
        return 2
    finally:
        page.close()


if __name__ == "__main__":
    sys.exit(main())
