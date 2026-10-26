# -*- coding: utf-8 -*-
"""向 Qoder（CN 或国际版）发送任务；跳过空白 page target，避免 websocket 超时。

  python send_qoder.py --port 9225 --project-name coding_skill \
    --project-path E:\\project_self\\coding_skill --text-file prompt.md
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
# 可选：本机 external-review 派发器（无则仅用内置 CDP）
for _p in (
    os.path.expanduser(r"~\.agents\skills\external-review\scripts"),
    os.path.join(os.path.dirname(__file__), "vendor", "external-review"),
):
    if os.path.isdir(_p) and _p not in sys.path:
        sys.path.insert(0, _p)
from cdp import Page, list_targets  # noqa: E402


def pick_page(port: int):
    for t in list_targets(port):
        if t.get("type") == "page" and t.get("url") and t.get("webSocketDebuggerUrl"):
            return t
    return None


def click_center(q: Page, sel_js: str, wait: float = 1.5) -> bool:
    rect = q.eval_js(
        "(() => { const b = " + sel_js + ";"
        " if (!b || !b.getBoundingClientRect().width) return null;"
        " const r = b.getBoundingClientRect();"
        " return {x: r.x + r.width/2, y: r.y + r.height/2}; })()"
    )
    if not rect:
        return False
    q.cmd("Input.dispatchMouseEvent", type="mouseMoved", x=rect["x"], y=rect["y"])
    q.cmd("Input.dispatchMouseEvent", type="mousePressed", x=rect["x"], y=rect["y"],
          button="left", clickCount=1)
    q.cmd("Input.dispatchMouseEvent", type="mouseReleased", x=rect["x"], y=rect["y"],
          button="left", clickCount=1)
    time.sleep(wait)
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--project-name", required=True)
    ap.add_argument("--project-path", required=True)
    ap.add_argument("--text-file", required=True)
    args = ap.parse_args()

    prompt = open(args.text_file, "r", encoding="utf-8").read()
    prompt = f"项目根：{args.project_path}\n\n{prompt}"

    # 【硬门禁】按**绝对路径**核对 Qoder 工作区是否绑定该目录。
    # 只靠项目名不可靠：Qoder 里可能存在多个同名工作区（实测「捷安泊数据分析」
    # 就登记了两次），无法用名字区分指向哪个路径。
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from ide_guard import require as require_project
        require_project("qoder", args.project_path)
    except ImportError:
        print("!! 未找到 ide_guard.py，跳过工作区归属校验")

    target = pick_page(args.port)
    if not target:
        print("qoder: 无可用 page target")
        return 1
    q = Page(args.port, target=target)
    print("qoder: window =", (target.get("title") or "")[:50])

    btn = (
        '[...document.querySelectorAll("button")].find(b =>'
        ' (b.getAttribute("title")||"").includes(' + json.dumps(args.project_name) + ') &&'
        ' (b.getAttribute("title")||"").includes("新建任务"))'
    )
    ok = click_center(q, btn, wait=3.0)
    if not ok:
        # 兼容 aria-label 形式
        btn2 = (
            '[...document.querySelectorAll("button,[aria-label]")].find(b =>'
            ' ((b.getAttribute("aria-label")||"").includes(' + json.dumps("在 " + args.project_name) + ') &&'
            ' (b.getAttribute("aria-label")||"").includes("新建任务")))'
        )
        ok = click_center(q, btn2, wait=3.0)
    print("qoder: clicked new-task", ok)
    if not ok:
        titles = q.eval_js(
            "(() => [...document.querySelectorAll('[title]')].map(e => e.getAttribute('title'))"
            ".filter(t => t && t.includes('新建任务')))()"
        )
        print("qoder: available", titles)
        q.close()
        return 1

    # 空编辑器则注入
    state = q.eval_js(
        "(() => ({ msgs: document.querySelectorAll('.markdown-presentation').length,"
        " ed: document.querySelector('.loop-rich-editor')?.textContent?.trim()?.length || 0 }))()"
    )
    print("qoder: editor state", state)
    if state and state.get("msgs", 0) == 0 and state.get("ed", 0) <= 1:
        q.eval_js(
            "(() => { const ed = document.querySelector('.loop-rich-editor');"
            " if(!ed) return 'NO_ED'; ed.focus();"
            " const sel = window.getSelection(); const r = document.createRange();"
            " r.selectNodeContents(ed); r.collapse(false); sel.removeAllRanges(); sel.addRange(r);"
            " return 'OK'; })()"
        )
        q.eval_js(
            "document.execCommand('insertText', false, " + json.dumps(prompt, ensure_ascii=False) + ")"
        )
        time.sleep(1)
        q.cmd("Input.dispatchKeyEvent", type="rawKeyDown", key="Enter", code="Enter",
              windowsVirtualKeyCode=13)
        q.cmd("Input.dispatchKeyEvent", type="keyUp", key="Enter", code="Enter",
              windowsVirtualKeyCode=13)
        time.sleep(2)
        print("qoder: SENT")
    else:
        print("qoder: editor not empty, skip insert")

    print(json.dumps({
        "port": args.port,
        "project_name": args.project_name,
        "project_path": args.project_path,
        "sent": True,
    }, ensure_ascii=False))
    q.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
