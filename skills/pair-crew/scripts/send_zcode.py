# -*- coding: utf-8 -*-
"""pair-crew 向 ZCode 发送任务（CDP）。

  python send_zcode.py --port 9224 --project-name coding_skill \
    --project-path E:\\project_self\\coding_skill --text-file prompt.md

行为：
  1. 若侧栏无 <project>，尝试点「新项目/选择项目」（原生对话框则失败退出，请用户手动选一次）
  2. 点「完全访问」切换按钮（已在完全访问则跳过）
  3. 写入 contenteditable 输入框并点「发送」
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


def first_page(port: int):
    for t in list_targets(port):
        if t.get("type") == "page" and t.get("url"):
            return t
    return None


def click_center(q: Page, sel_js: str, wait: float = 1.2) -> bool:
    rect = q.eval_js(
        "(() => { const b = " + sel_js + ";"
        " if (!b) return null;"
        " const r = b.getBoundingClientRect();"
        " if (!r.width) return null;"
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
    ap.add_argument("--port", type=int, default=9224)
    ap.add_argument("--project-name", required=True)
    ap.add_argument("--project-path", required=True)
    ap.add_argument("--text-file", required=True)
    ap.add_argument("--skip-access", action="store_true")
    args = ap.parse_args()

    prompt = open(args.text_file, "r", encoding="utf-8").read()
    # 顶部注入绝对路径，降低工作区漂移
    prompt = f"项目根：{args.project_path}\n\n{prompt}"

    t = first_page(args.port)
    if not t:
        print("zcode: 无可用页面")
        return 1
    q = Page(args.port, target=t)

    # 1) 是否已有该项目
    has = q.eval_js(
        "(() => { const t=document.body.innerText||'';"
        " return t.includes(" + json.dumps(args.project_name) + "); })()"
    )
    print("zcode: 侧栏含项目名？", bool(has))
    if not has:
        # 尝试点「新项目」
        ok = click_center(
            q,
            '[...document.querySelectorAll("button")].find(b => (b.getAttribute("aria-label")||"")=="新项目")',
            wait=2.0,
        )
        print("zcode: 已点新项目？", ok, "——若弹出系统选择框，请手动选", args.project_path)
        # 继续尝试发送；用户应先绑好

    # 2) 完全访问
    if not args.skip_access:
        acc_text = q.eval_js(
            "(() => { const b=[...document.querySelectorAll('button')].find(x =>"
            " (x.getAttribute('aria-label')||'')=='切换模式' || (x.textContent||'').includes('完全访问'));"
            " return b ? (b.textContent||'').trim() : ''; })()"
        )
        print("zcode: 访问按钮文案:", acc_text)
        # 若不是「完全访问」则点一下切过去
        if acc_text and "完全访问" not in acc_text:
            click_center(
                q,
                '[...document.querySelectorAll("button")].find(b => (b.getAttribute("aria-label")||"")=="切换模式" || (b.textContent||"").includes("受限") || (b.textContent||"").includes("只读"))',
                wait=1.5,
            )
            print("zcode: 尝试切换访问模式")

    # 3) 写入输入框
    js_fill = (
        "(() => {"
        " const ed=[...document.querySelectorAll('[contenteditable=true],[contenteditable=\"true\"]')].find(e => e.offsetHeight>0);"
        " if(!ed) return 'NO_INPUT';"
        " ed.focus();"
        " const sel=window.getSelection(); const r=document.createRange();"
        " r.selectNodeContents(ed); r.collapse(false); sel.removeAllRanges(); sel.addRange(r);"
        " document.execCommand('insertText', false, " + json.dumps(prompt, ensure_ascii=False) + ");"
        " return 'OK';"
        " })()"
    )
    filled = q.eval_js(js_fill)
    print("zcode: fill =", filled)
    if filled != "OK":
        q.close()
        return 1
    time.sleep(1)

    # 4) 发送
    ok = click_center(
        q,
        '[...document.querySelectorAll("button")].find(b => (b.getAttribute("aria-label")||"")=="发送")',
        wait=3.0,
    )
    print("zcode: 发送按钮", "OK" if ok else "FAIL")
    print(json.dumps({"zcode": "SENT" if ok else "FAILED",
                      "project_name": args.project_name,
                      "project_path": args.project_path}, ensure_ascii=False))
    q.close()
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
