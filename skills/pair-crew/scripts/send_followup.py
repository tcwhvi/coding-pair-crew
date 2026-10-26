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
sys.path.insert(0, sys.path[0] if sys.path else ".")
from cdp import Page, list_targets  # noqa: E402

try:
    from ide_guard import session_title, recent_sessions, message_count  # noqa: E402
except Exception:                                    # pragma: no cover
    session_title = recent_sessions = message_count = None

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
  // 侧栏可能滚出视口（实测 y 会是负数），先滚到中间再取坐标
  e.scrollIntoView({block: 'center'});
  const r = e.getBoundingClientRect();
  return JSON.stringify({x: Math.round(r.x + r.width / 2), y: Math.round(r.y + r.height / 2),
                         n: els.length, visible: r.y > 0 && r.y < window.innerHeight});
})()"""

JS_FIND_SEND = """(() => {
  const hit = [...document.querySelectorAll('button,[role=button],a,div,span')].filter(e => {
    const r = e.getBoundingClientRect();
    if (r.width === 0 || r.height === 0) return false;
    const al = (e.getAttribute('aria-label') || '') + ' ' +
               (e.getAttribute('title') || '') + ' ' +
               (e.getAttribute('data-testid') || '');
    const t = (e.innerText || '').trim();
    return /发送|send|submit/i.test(al) || t === '发送' || t === 'Send';
  });
  if (!hit.length) return 'NO_SEND_BTN';
  // 取最靠下的那个（发送按钮在输入框右侧/下方，不是顶栏）
  hit.sort((a, b) => b.getBoundingClientRect().y - a.getBoundingClientRect().y);
  const r = hit[0].getBoundingClientRect();
  return JSON.stringify({x: Math.round(r.x + r.width / 2),
                         y: Math.round(r.y + r.height / 2),
                         label: (hit[0].getAttribute('aria-label') || hit[0].innerText || '').slice(0, 20)});
})()"""


def press_enter(q: Page):
    """Enter。

    **必须用 keyDown 且带 text='\\r'**：`rawKeyDown` 只发 keydown、不带字符事件，
    React 受控的 contenteditable 常常收不到，表现为「注入成功但发不出去」
    （实测 Qoder：fill=OK、chat id 正确、数据库一条没增）。
    """
    q.cmd("Input.dispatchKeyEvent", type="keyDown", key="Enter", code="Enter",
          windowsVirtualKeyCode=13, nativeVirtualKeyCode=13,
          text="\r", unmodifiedText="\r")
    q.cmd("Input.dispatchKeyEvent", type="keyUp", key="Enter", code="Enter",
          windowsVirtualKeyCode=13, nativeVirtualKeyCode=13)


def press_ctrl_enter(q: Page):
    for mods in (2,):      # 2 = Ctrl
        q.cmd("Input.dispatchKeyEvent", type="keyDown", key="Enter", code="Enter",
              windowsVirtualKeyCode=13, nativeVirtualKeyCode=13, modifiers=mods,
              text="\r", unmodifiedText="\r")
        q.cmd("Input.dispatchKeyEvent", type="keyUp", key="Enter", code="Enter",
              windowsVirtualKeyCode=13, nativeVirtualKeyCode=13, modifiers=mods)


def click_send_button(q: Page) -> bool:
    r = q.eval_js(JS_FIND_SEND)
    if not r or r == "NO_SEND_BTN":
        return False
    d = json.loads(r)
    click(q, d["x"], d["y"])
    print(f"   点了发送按钮（{d.get('label') or 'icon'}）")
    return True


def wait_delivered(ide: str, chat_id: str, n_before: int, timeout=8.0) -> int:
    """等到消息数增加，返回最新条数（超时则返回原值）。"""
    if not (ide and message_count and n_before >= 0):
        return -1
    deadline = time.time() + timeout
    n = n_before
    while time.time() < deadline:
        time.sleep(1.0)
        n = message_count(ide, chat_id)
        if n > n_before:
            return n
    return n


def send_with_fallback(q: Page, ide: str, chat_id_: str, n_before: int) -> tuple[bool, int]:
    """三路发送，直到数据库里真的多出一条。

    返回 (是否送达, 最新消息数)。无 --ide 时退化成「发一次就信」。
    """
    if not (ide and message_count and n_before >= 0):
        press_enter(q)
        time.sleep(1.5)
        return True, -1

    attempts = [
        ("Enter(keyDown+text)", lambda: press_enter(q)),
        ("发送按钮", lambda: click_send_button(q)),
        ("Ctrl+Enter", lambda: press_ctrl_enter(q)),
        ("Enter 再来一次", lambda: press_enter(q)),
    ]
    n = n_before
    for i, (name, fn) in enumerate(attempts, 1):
        ok = fn()
        if ok is False:
            print(f"   [{i}] {name}: 不可用，跳过")
            continue
        n = wait_delivered(ide, chat_id_, n_before)
        if n > n_before:
            print(f"   [{i}] {name}: 已送达（消息数 {n_before} -> {n}）")
            return True, n
        print(f"   [{i}] {name}: 未送达（消息数仍为 {n}），换下一种")
    return False, n


def fill_editor(q: Page, text: str) -> bool:
    """把文本写进输入框。

    两级策略，**顺序不能反**：

    1. `Input.insertText`（CDP 原生输入）：走浏览器的真实输入通道，会触发 `input`
       事件，React 受控组件能收到。这是首选。
    2. `document.execCommand('insertText')`（DOM 兜底）：只改 DOM，**不触发 React
       的 onChange**。很多编辑器里看着有字，但组件 state 仍是空，点发送等于发空消息，
       表现为「fill: OK、按钮点到了、数据库一条没增」。

    实测 Qoder 的 `.loop-rich-editor` 就属于第 2 类坑，exeCommand 那条路走不通。
    """
    # 聚焦并清空
    focused = q.eval_js(
        "(() => {"
        " const eds=[...document.querySelectorAll('.loop-rich-editor,[contenteditable=true],"
        "[contenteditable=\"true\"]')].filter(e=>e.offsetHeight>0);"
        " if(!eds.length) return 'NO_INPUT';"
        " const ed=eds[eds.length-1]; ed.focus();"
        " const sel=window.getSelection(); const r=document.createRange();"
        " r.selectNodeContents(ed); sel.removeAllRanges(); sel.addRange(r);"
        " return 'OK';"
        " })()"
    )
    if focused != "OK":
        print("fill: NO_INPUT")
        return False
    # 先删掉旧内容，避免和之前失败的残留拼接
    q.cmd("Input.dispatchKeyEvent", type="keyDown", key="Delete",
          code="Delete", windowsVirtualKeyCode=46, nativeVirtualKeyCode=46)
    q.cmd("Input.dispatchKeyEvent", type="keyUp", key="Delete",
          code="Delete", windowsVirtualKeyCode=46, nativeVirtualKeyCode=46)
    time.sleep(0.3)

    try:
        q.cmd("Input.insertText", text=text)
        time.sleep(0.6)
        n = q.eval_js(
            "(() => { const eds=[...document.querySelectorAll('.loop-rich-editor,"
            "[contenteditable=true],[contenteditable=\"true\"]')].filter(e=>e.offsetHeight>0);"
            " if(!eds.length) return 0; return (eds[eds.length-1].innerText||'').length; })()"
        )
        print(f"fill: Input.insertText -> 编辑器内文本长度 {n}")
        if isinstance(n, int) and n > 20:
            return True
    except Exception as e:
        print(f"fill: Input.insertText 失败({e})，退回 execCommand")

    r = q.eval_js(
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
    print("fill: execCommand ->", r)
    return r == "OK"


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
    ap.add_argument("--ide", choices=["zcode", "qoder"], default="",
                    help="给了就用数据库按 chat id 核对会话身份（强烈建议给）")
    ap.add_argument("--expect", default="", help="会话标题关键词；当前会话不匹配就拒发")
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
        if r == "NOT_FOUND":
            print(f"!! 侧栏里找不到「{args.switch_to}」，保持当前会话")
        else:
            d = json.loads(r)
            click(q, d["x"], d["y"])
            time.sleep(3)
            switched = chat_id(q)
            print(f"  切换前 chat id: {before[:12]}…")
            print(f"  切换后 chat id: {switched[:12]}…")
            if switched != before:
                before = switched      # ← 必须更新，后续校验和落库比对的基准都靠它
            else:
                print("  !! 点完 chat id 没变，切换没生效（侧栏项可能在视口外或不可点）")

    # 2) 归属校验：按 chat id 查数据库里的**真实标题**，不看页面文本。
    #    页面 innerText 含整个侧栏，按文本匹配会把侧栏里别的会话名当成当前会话
    #    —— 实测把评审指令发进了「查找TTFT插件」。
    if args.expect and not args.force:
        title = ""
        info = {}
        if args.ide and session_title:
            info = session_title(args.ide, before) or {}
            title = info.get("title", "")
            print(f"当前会话:「{title or '未知'}」"
                  f"  {info.get('workspace') or info.get('directory') or ''}")
        ok = bool(title) and (args.expect in title)
        if not title:
            print("!! 没给 --ide 或查不到会话记录，退回页面文本判断（不可靠）")
            chk = q.eval_js(JS_TITLE_HIT % json.dumps(args.expect, ensure_ascii=False))
            info2 = json.loads(chk) if chk else {}
            ok = bool(info2.get("head_has"))
        if not ok:
            print(f"!! 当前会话标题不含「{args.expect}」，拒绝发送。")
            if args.ide and recent_sessions:
                print("   最近会话：")
                for s in (recent_sessions(args.ide, 12) or []):
                    print(f"     - {(s.get('title') or '')[:52]}")
            print("   用 --switch-to 指定会话标题，或 --force 明确强制。")
            q.close()
            return 2

    # 3) 注入（优先原生 Input.insertText）
    if not fill_editor(q, text):
        print("!! 输入框注入失败")
        q.close()
        return 1

    time.sleep(0.8)
    n_before = message_count(args.ide, before) if (args.ide and message_count) else -1
    print(f"发送前消息数: {n_before}")
    delivered, n_after = send_with_fallback(q, args.ide, before, n_before)

    # 4) 发送后核对：会话不能变
    now_id = chat_id(q)
    if now_id != before:
        print(f"!! 发送后会话变成了 {now_id[:12]}…，消息可能落到别的会话")
        q.close()
        return 3

    if not delivered:
        print("!! 三种发送方式都没能让数据库新增消息 —— 这条发不出去。")
        print("   这通常是因为用户正在同一会话里操作 IDE，输入被抢。")
        print(f"   请手动把 {args.text_file} 的内容粘进目标会话，或等 IDE 空闲重试。")
        q.close()
        return 4

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
