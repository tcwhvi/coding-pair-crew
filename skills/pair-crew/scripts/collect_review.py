# -*- coding: utf-8 -*-
r"""读回外部评审的结论（直接查 IDE 数据库，不占用用户界面）。

## 为什么必须有这个脚本

派发是异步的：外部 IDE 一跑就是半小时到一小时，而 agent 的会话是同步的 ——
一轮答完就结束。没有这个工具，「派发了」很容易被当成「评审完了」，
用户那边还在跑，这边已经收工，评审结论就永远没人读。

## 用法

```bash
# 1. 列出最近 12 小时内有活动的会话（一眼看出哪些评审还没收口）
python collect_review.py

# 2. 只看某个 IDE
python collect_review.py --ide qoder

# 3. 按标题关键词过滤
python collect_review.py --title 评审

# 4. 输出某个会话的完整最后一条结论
python collect_review.py --session 849f8409-bd0e-4432-b9a3-33029ed06ce7 --full
```

判读要点：
- **消息条数不变 ≠ 没有新结论**。实测 Qoder 会在同一条 assistant 消息上原地更新内容，
  条数一直是 6，但里面已经从「第一轮结论」换成了「第三轮复核」。
  所以这里输出的是「最后一条 assistant 消息的摘要 + 其 updated_at」，
  而不是只给条数。
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import sqlite3
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ide_guard import QODER_DBS, ZCODE_DB  # noqa: E402


def _ro(path):
    # 不加 immutable=1（会忽略 WAL，读到旧快照，导致「消息数一直不变」的误判）
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    con.execute("PRAGMA query_only=1")
    return con


def _ts(ms):
    try:
        return datetime.datetime.fromtimestamp(int(ms) / 1000)
    except Exception:
        return None


def _fmt(dt):
    return dt.strftime("%m-%d %H:%M") if dt else "?"


# ---------------- Qoder ----------------
def qoder_sessions(since_hours: float) -> list[dict]:
    out = []
    cutoff = datetime.datetime.now() - datetime.timedelta(hours=since_hours)
    for db in QODER_DBS:
        if not os.path.isfile(db):
            continue
        con = _ro(db)
        c = con.cursor()
        try:
            c.execute(
                "SELECT s.session_id, s.title, s.cwd, s.updated_at, s.workspace_id, w.name "
                "FROM chat_sessions s LEFT JOIN workspaces w ON w.workspace_id = s.workspace_id "
                "WHERE s.deleted_at IS NULL ORDER BY s.updated_at DESC LIMIT 200"
            )
            rows = c.fetchall()
        except Exception:
            con.close()
            continue
        for sid, title, cwd, upd, wid, wname in rows:
            dt = _ts(upd)
            if dt and dt < cutoff:
                continue
            info = {
                "ide": "qoder", "session_id": sid, "title": title or "",
                "cwd": cwd or "", "workspace": wname or "",
                "updated": _fmt(dt), "db": db,
            }
            try:
                c.execute(
                    "SELECT sequence, role, updated_at, payload_json "
                    "FROM chat_session_messages WHERE session_id=? "
                    "ORDER BY sequence DESC LIMIT 1",
                    (sid,),
                )
                r = c.fetchone()
                if r:
                    seq, role, upd2, pj = r
                    info["messages"] = _qoder_count(c, sid)
                    info["last_role"] = role
                    info["last_time"] = _fmt(_ts(upd2))
                    info["last_text"] = _qoder_text(pj)
            except Exception:
                pass
            out.append(info)
        con.close()
    return out


def _qoder_count(c, sid) -> int:
    try:
        c.execute("SELECT COUNT(*) FROM chat_session_messages WHERE session_id=?", (sid,))
        return int(c.fetchone()[0])
    except Exception:
        return -1


def _qoder_text(payload_json, limit=None) -> str:
    try:
        d = json.loads(payload_json)
    except Exception:
        return ""
    parts = d.get("parts") or []
    texts = [p.get("text", "") for p in parts
             if isinstance(p, dict) and p.get("type") == "text" and p.get("text")]
    txt = "\n\n".join(texts).strip()
    return txt if limit is None else txt[:limit]


def qoder_full(db: str, sid: str) -> str:
    con = _ro(db)
    c = con.cursor()
    c.execute(
        "SELECT payload_json FROM chat_session_messages "
        "WHERE session_id=? AND role='assistant' ORDER BY sequence DESC LIMIT 1",
        (sid,),
    )
    r = c.fetchone()
    con.close()
    return _qoder_text(r[0]) if r else ""


# ---------------- ZCode ----------------
def zcode_sessions(since_hours: float) -> list[dict]:
    if not os.path.isfile(ZCODE_DB):
        return []
    cutoff = datetime.datetime.now() - datetime.timedelta(hours=since_hours)
    con = _ro(ZCODE_DB)
    c = con.cursor()
    try:
        c.execute(
            "SELECT id, title, directory, time_updated, last_outcome "
            "FROM session WHERE time_deleted IS NULL ORDER BY time_updated DESC LIMIT 200"
        )
        rows = c.fetchall()
    except Exception:
        con.close()
        return []
    out = []
    for sid, title, directory, tu, outcome in rows:
        dt = _ts(tu)
        if dt and dt < cutoff:
            continue
        info = {"ide": "zcode", "session_id": sid, "title": title or "",
                "cwd": directory or "", "workspace": "", "db": ZCODE_DB,
                "updated": _fmt(dt), "outcome": outcome or ""}
        try:
            c.execute("SELECT COUNT(*) FROM message WHERE session_id=?", (sid,))
            info["messages"] = int(c.fetchone()[0])
            c.execute(
                "SELECT id, data FROM message WHERE session_id=? AND data LIKE '%%assistant%%' "
                "ORDER BY sequence DESC LIMIT 1",
                (sid,),
            )
            r = c.fetchone()
            if r:
                info["last_role"] = "assistant"
                info["last_text"] = _zcode_text(c, r[0])
        except Exception:
            pass
        out.append(info)
    con.close()
    return out


def _zcode_text(c, message_id) -> str:
    try:
        c.execute("SELECT data FROM part WHERE message_id=? ORDER BY sequence", (message_id,))
    except Exception:
        return ""
    texts = []
    for (pd,) in c.fetchall():
        try:
            p = json.loads(pd)
        except Exception:
            continue
        if p.get("type") == "text" and p.get("text"):
            texts.append(p["text"])
    return "\n".join(texts).strip()


def zcode_full(sid: str) -> str:
    con = _ro(ZCODE_DB)
    c = con.cursor()
    c.execute(
        "SELECT id FROM message WHERE session_id=? AND data LIKE '%%assistant%%' "
        "ORDER BY sequence DESC LIMIT 1", (sid,))
    r = c.fetchone()
    txt = _zcode_text(c, r[0]) if r else ""
    con.close()
    return txt


# ---------------- 输出 ----------------
VERDICTS = ["可以开工", "还不能开工", "改完 P0 再开工", "换方案"]


def verdict_of(text: str) -> str:
    for v in VERDICTS:
        if v in (text or ""):
            return v
    return "（未见明确判定）"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ide", choices=["qoder", "zcode", "all"], default="all")
    ap.add_argument("--hours", type=float, default=12, help="只看这么多小时内有活动的")
    ap.add_argument("--title", default="", help="会话标题关键词过滤")
    ap.add_argument("--session", default="", help="输出该会话最后一条完整结论")
    ap.add_argument("--full", action="store_true")
    ap.add_argument("--chars", type=int, default=260)
    args = ap.parse_args()

    rows = []
    if args.ide in ("qoder", "all"):
        rows += qoder_sessions(args.hours)
    if args.ide in ("zcode", "all"):
        rows += zcode_sessions(args.hours)

    if args.session:
        for r in rows:
            if r["session_id"] == args.session:
                txt = (qoder_full(r["db"], args.session) if r["ide"] == "qoder"
                       else zcode_full(args.session))
                print(f"== {r['ide']} / {r['title']}  ({r['cwd']})")
                print(f"   判定: {verdict_of(txt)}")
                print("-" * 70)
                print(txt)
                return 0
        # 不在时间窗内也试一次
        for r in (qoder_sessions(24 * 30) + zcode_sessions(24 * 30)):
            if r["session_id"] == args.session:
                txt = (qoder_full(r["db"], args.session) if r["ide"] == "qoder"
                       else zcode_full(args.session))
                print(f"== {r['ide']} / {r['title']}  ({r['cwd']})")
                print(txt)
                return 0
        print("没找到该会话")
        return 1

    if args.title:
        rows = [r for r in rows if args.title in (r.get("title") or "")]

    if not rows:
        print(f"最近 {args.hours} 小时内没有活动会话")
        return 0

    for r in rows:
        last = r.get("last_text") or ""
        v = verdict_of(last)
        print(f"[{r['ide']}] {r.get('updated')}  {r['title'][:44]}")
        print(f"    目录: {r.get('cwd')}")
        if r.get("workspace"):
            print(f"    工作区: {r['workspace']}")
        print(f"    消息数: {r.get('messages')}  最后一条: {r.get('last_role')} @ {r.get('last_time')}")
        print(f"    判定: {v}")
        if args.full and last:
            print("-" * 70)
            print(last)
            print("-" * 70)
        elif last:
            print(f"    摘要: {last[:args.chars]}".replace("\n", " "))
        print(f"    session_id: {r['session_id']}")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
