# -*- coding: utf-8 -*-
"""向**已在运行**的 agent 会话补发消息（不新建任务）。

## 两个必须防住的坑（都真实踩过）

**坑 1：任务归属**
CDP 操作的是「当前活动视图」。如果派发后界面被切到别的会话，`insertText + Enter`
就会把消息送进**那个**会话，而你以为发给了评审任务。
→ v3 强制先 `current_chat_id()` + `--expect` 标题校验；可用 `--switch-to` 先按
侧栏标题点过去；发送前后比对 chat id，变了就报错。

**坑 2：插话按钮的文案不是固定的**
Agent 正在生成时，消息进排队队列，气泡上会出现一个按钮要点掉才会插队执行。
- ZCode 叫「立即」
- **Qoder CN 叫「插话」**
只认「立即」的脚本在 Qoder 上永远点不到，消息就一直排在队尾，表现为「发了没反应」。
→ v3 的 `QUEUE_WORDS` 覆盖多种文案，并且发送前后都扫一遍。

  python send_followup.py --port 9222 --expect "生产导入脚本评审" --text-file note.md
  python send_followup.py --port 9224 --expect "评审" --switch-to 评审 --text-file note.md
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"C:\Users\Administrator\.agents\skills\external-review\scripts")
from cdp import Page, list_targets  # noqa: E402

QUEUE_WORDS = ["立即", "插话", "立即发送", "立即执行", "打断", "现在就发", "插入"]

JS_CHAT_ID = "(() => location.href)()"

JS_TITLE_HIT = """(() => {
  const want = %s;
  const txt = document.body.innerText || '';
  // 只看顶部区域（会话标题一般在最上），避免正文里出现同名词造成误判
  const head = [...document.querySelectorAll('h1,h2,[class*=title],[class*=header]')]
      .map(e => (e.innerText || '').trim())
      .filter(t => t && t.length < 80)
      .join('\\n');
  return JSON.stringify({body_has: txt.includes(want), head_has: head.includes(want)});
})()"""

JS_FIND_QUEUE = """(() => {
  const WORDS = %s;
  const hits = [];
  for (const e of document.querySelectorAll('button,div,span,a')) {
    const r = e.getBoundingClientRect();
    if (r.width === 0 || r.height === 0) continue;
    const t = (e.innerText || '').trim();
    if (WORDS.includes(t)) {
      hits.push({word: t, x: Math.round(r.x + r.width / 2), y: Math.round(r.y + r.height / 2)});
    }
  }
  // 去重（同一按钮会被父子节点重复命中）
  const out = [];
  for (const h of hits) {
    if (!out.some(o => Math.abs(o.x - h.x) < 4 && Math.abs(o.y - h.y) < 4)) out.push(h);
  }
  return JSON.stringify(out);
})()"""

JS_CLICK_TITLE = """(() => {
  const want = %s;
  const els = [...document.querySelectorAll('div,span,a,li,button')].filter(e => {
    const r = e.getBoundingClientRect();
    if (r.width === 0 || r.height === 0) return false;
    const t = (e.innerText || '').trim();
    return t === want || (t.includes(want) && t.length < want.length + 12);
  });
  if (!els.length) return 'NOT_FOUND';
  const e = els[els.length - 1];
  const r = e.getBoundingClientRect();
  return JSON.stringify({x: Math.round(r.x + r.width / 2), y: Math.round(r.y + r.height / 2), n: els.length});
})()"""


def first_page(port):
    for t in list_targets(port):
        if t.get("type") == "page" and t.get("url"):
            return t
    return None


def click(q: Page, x, y):
    q.cmd("Input.dispatchMouseEvent", type="mouseMoved", x=x, y=y)
    q.cmd("Input.dispatchMouseEvent", type="mousePressed", x=x, y=y, button="left", clickCount=1)
    q.cmd("Input.dispatchMouseEvent", type="mouseReleased", x=x, y=y, button="left", clickCount=1)


def chat_id(q: Page) -> str:
    url = q.eval_js(JS_CHAT_ID) or ""
    m = re.search(r"#/chat/([0-9a-fA-F-]{8,})", url)
    return m.group(1) if m else url


def queue_buttons(q: Page) -> list:
    raw = q.eval_js(JS_FIND_QUEUE % json.dumps(QUEUE_WORDS, ensure_ascii=False))
    try:
        return json.loads(raw)
    except Exception:
        return []


def flush_queue(q: Page, tries=12, gap=1.2) -> bool:
    """点掉排队消息的插话按钮。

    注意取 **y 最大**（最靠下 = 最新的一条）那个：历史消息里躺着的旧「插话/立即」
    按钮点是没意义的，还可能把旧消息重新触发。
    """
    for i in range(tries):
        btns = queue_buttons(q)
        if not btns:
            return True
        b = max(btns, key=lambda x: x["y"])
        click(q, b["x"], b["y"])
        print(f"  点「{b['word']}」第 {i + 1} 次（y={b['y']}，共 {len(btns)} 个候选）")
        time.sleep(gap)
    return not queue_buttons(q)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--text-file", required=True)
    ap.add_argument("--expect", default="", help="会话标题关键词；给出时当前会话不匹配就拒发")
    ap.add_argument("--switch-to", default="", help="先按侧栏标题切到这个会话")
    ap.add_argument("--no-now", action="store_true", help="不自动点插话/立即")
    ap.add_argument("--force", action="store_true", help="跳过 --expect 校验（明确知道自己在发哪）")
    args = ap.parse_args()

    text = open(args.text_file, encoding="utf-8").read().strip()
    t = first_page(args.port)
    if not t:
        print("无可用页面")
        return 1
    q = Page(args.port, target=t)

    before = chat_id(q)

    # 1) 需要时先切会话
    if args.switch_to:
        r = q.eval_js(JS_CLICK_TITLE % json.dumps(args.switch_to, ensure_ascii=False))
        print("切换会话:", r)
        if r != "NOT_FOUND":
            d = json.loads(r)
            click(q, d["x"], d["y"])
            time.sleep(3)
            after_switch = chat_id(q)
            print(f"  chat id: {before[:12]}… -> {after_switch[:12]}…")

    # 2) 归属校验
    if args.expect and not args.force:
        chk = q.eval_js(JS_TITLE_HIT % json.dumps(args.expect, ensure_ascii=False))
        info = json.loads(chk) if chk else {}
        print("归属校验:", info)
        if not (info.get("head_has") or info.get("body_has")):
            print(f"!! 当前会话不含「{args.expect}」，拒绝发送。")
            print("   用 --switch-to 指定会话标题，或 --force 明确强制。")
            q.close()
            return 2

    # 3) 注入 + 回车
    js = (
        "(() => {"
        " const eds=[...document.querySelectorAll('.loop-rich-editor,[contenteditable=true],"
        "[contenteditable=\"true\"]')].filter(e=>e.offsetHeight>0);"
        " if(!eds.length) return 'NO_INPUT';"
        " const ed=eds[eds.length-1]; ed.focus();"
        " const sel=window.getSelection(); const r=document.createRange();"
        " r.selectNodeContents(ed); r.collapse(false); sel.removeAllRanges(); sel.addRange(r);"
        " document.execCommand('insertText', false, " + json.dumps(text, ensure_ascii=False) + ");"
        " return 'OK';"
        " })()"
    )
    filled = q.eval_js(js)
    print("fill:", filled)
    if filled != "OK":
        q.close()
        return 1

    time.sleep(0.8)
    for typ in ("rawKeyDown", "keyUp"):
        q.cmd("Input.dispatchKeyEvent", type=typ, key="Enter", code="Enter",
              windowsVirtualKeyCode=13)
    time.sleep(1.5)

    # 4) 发送后核对：会话不能变
    now_id = chat_id(q)
    if now_id != before:
        print(f"!! 发送后会话变成了 {now_id[:12]}…，消息可能落到别的会话")
        q.close()
        return 3

    # 5) 清排队（Qoder 叫「插话」，ZCode 叫「立即」）
    queued = bool(queue_buttons(q))
    print("是否进入排队队列:", queued)
    flushed = True
    if queued and not args.no_now:
        flushed = flush_queue(q)
        print("队列已清空:", flushed)

    print(json.dumps({"port": args.port, "sent": True, "chat_id": now_id,
                      "was_queued": queued, "flushed": flushed}, ensure_ascii=False))
    q.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
