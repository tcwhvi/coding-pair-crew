# -*- coding: utf-8 -*-
r"""派发前校验：目标 IDE 里**有没有**绑定到指定目录的项目。

## 为什么需要它（真实事故）

`send_qoder.py` / `send_zcode.py` 的旧逻辑只做「侧栏文本里含不含这个项目名」，
含就发到**当前会话**。后果：

- ZCode 侧栏里没有「捷安泊数据分析」项目，脚本不报错，直接把任务发进当时开着的
  `coding_skill` 会话 → 会话的 `directory` 是 `E:\project_self\coding_skill\.mimocode`，
  与用户要的项目毫无关系
- Qoder 有两个同名工作区（重复登记），无法靠名字区分

所以：**派发前必须按「绝对路径」核对，而不是按名字。**

数据来源（只读，不改任何 IDE 状态）：
- ZCode：`~/.zcode/cli/db/db.sqlite` 的 `session.project_id` + `session.directory`
- Qoder：`~/AppData/Roaming/com.qodercn.app.stable/main.sqlite`
  的 `workspaces.workspace_id/name/root_paths_json` 与 `chat_sessions.workspace_id`

  python ide_guard.py --ide zcode --path "D:\\projects\\捷安泊数据分析"
  python ide_guard.py --ide qoder --path "D:\\projects\\捷安泊数据分析"
  python ide_guard.py --ide zcode --list
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys

sys.stdout.reconfigure(encoding="utf-8")

ZCODE_DB = os.path.expanduser(r"~/.zcode/cli/db/db.sqlite")
QODER_DBS = [
    os.path.expanduser(r"~/AppData/Roaming/com.qodercn.app.stable/main.sqlite"),
    os.path.expanduser(r"~/AppData/Roaming/com.qoder.app.stable/main.sqlite"),
]


def _norm(p: str) -> str:
    return (p or "").replace("/", "\\").rstrip("\\").lower()


def _ro(path):
    return sqlite3.connect(f"file:{path}?mode=ro&immutable=1", uri=True)


# ---------------- ZCode ----------------
def zcode_projects() -> list[dict]:
    if not os.path.isfile(ZCODE_DB):
        return []
    try:
        con = _ro(ZCODE_DB)
        c = con.cursor()
        c.execute(
            "SELECT project_id, directory, COUNT(*) n, MAX(time_updated) t "
            "FROM session WHERE time_deleted IS NULL AND directory IS NOT NULL "
            "GROUP BY project_id, directory ORDER BY t DESC"
        )
        rows = [{"project_id": r[0], "directory": r[1], "sessions": r[2]}
                for r in c.fetchall()]
        con.close()
        return rows
    except Exception as e:
        return [{"error": str(e)}]


def zcode_sessions() -> list[dict]:
    if not os.path.isfile(ZCODE_DB):
        return []
    con = _ro(ZCODE_DB)
    c = con.cursor()
    c.execute(
        "SELECT id, project_id, directory, title, time_updated FROM session "
        "WHERE time_deleted IS NULL ORDER BY time_updated DESC LIMIT 40"
    )
    rows = [{"id": r[0], "project_id": r[1], "directory": r[2],
             "title": (r[3] or "")[:50]} for r in c.fetchall()]
    con.close()
    return rows


# ---------------- Qoder ----------------
def qoder_workspaces(db: str) -> list[dict]:
    if not os.path.isfile(db):
        return []
    con = _ro(db)
    c = con.cursor()
    c.execute("SELECT workspace_id, name, root_paths_json, deleted_at FROM workspaces")
    out = []
    for wid, name, rp, dl in c.fetchall():
        if dl:
            continue
        try:
            roots = json.loads(rp) if rp else []
        except Exception:
            roots = []
        out.append({"workspace_id": wid, "name": name, "roots": roots})
    con.close()
    return out


def qoder_sessions(db: str) -> list[dict]:
    if not os.path.isfile(db):
        return []
    con = _ro(db)
    c = con.cursor()
    try:
        c.execute(
            "SELECT s.session_id, s.title, s.workspace_id, w.root_paths_json "
            "FROM chat_sessions s LEFT JOIN workspaces w ON w.workspace_id = s.workspace_id "
            "ORDER BY s.rowid DESC LIMIT 40"
        )
    except Exception:
        con.close()
        return []
    out = []
    for sid, title, wid, rp in c.fetchall():
        try:
            roots = json.loads(rp) if rp else []
        except Exception:
            roots = []
        out.append({"session_id": sid, "title": (title or "")[:50],
                    "workspace_id": wid, "roots": roots})
    con.close()
    return out


# ---------------- 判定 ----------------
def check(ide: str, path: str) -> dict:
    want = _norm(path)
    if ide == "zcode":
        rows = zcode_projects()
        hits = [r for r in rows if _norm(r.get("directory")) == want]
        have = sorted({r.get("directory") for r in rows if r.get("directory")})
        return {"ok": bool(hits), "ide": ide, "want": path,
                "matched": hits, "available": have}
    for db in QODER_DBS:
        rows = qoder_workspaces(db)
        hits = [r for r in rows if any(_norm(x) == want for x in r["roots"])]
        if hits:
            return {"ok": True, "ide": ide, "want": path,
                    "matched": hits, "db": db}
    avail = []
    for db in QODER_DBS:
        for r in qoder_workspaces(db):
            avail.extend(r["roots"])
    return {"ok": False, "ide": ide, "want": path, "matched": [],
            "available": sorted(set(avail))}


def require(ide: str, path: str, hint: str = "") -> None:
    """不满足就抛 SystemExit，附上「怎么修」。"""
    r = check(ide, path)
    if r["ok"]:
        return
    lines = [f"!! {ide} 里没有绑定到 {path} 的项目，拒绝派发。",
             "   已绑定的目录："]
    for d in r.get("available", [])[:20]:
        lines.append(f"     - {d}")
    if ide == "zcode":
        lines.append("   修法：ZCode 侧栏点「新项目」→ 选上面的目录（原生文件夹框，需手动一次）。")
    else:
        lines.append("   修法：Qoder 里 文件 → 打开文件夹 → 选该目录，使其出现在工作区列表。")
    if hint:
        lines.append(f"   备注：{hint}")
    raise SystemExit("\n".join(lines))


# ---------------- 会话身份（按 chat id 查真实标题） ----------------
def session_title(ide: str, chat_id: str) -> dict:
    """用 chat id 反查会话的真实标题和所属工作区。

    这是唯一可靠的「我在跟谁说话」判定方式：
    页面上 `document.body.innerText` 含会话侧栏，按文本匹配会把侧栏里的
    别的会话名当成当前会话（实测踩过：消息被发进「查找TTFT插件」）。
    """
    chat_id = (chat_id or "").strip()
    if not chat_id:
        return {}
    if ide == "qoder":
        for db in QODER_DBS:
            if not os.path.isfile(db):
                continue
            con = _ro(db)
            c = con.cursor()
            c.execute(
                "SELECT s.title, s.workspace_id, w.name, w.root_paths_json "
                "FROM chat_sessions s LEFT JOIN workspaces w ON w.workspace_id = s.workspace_id "
                "WHERE s.session_id = ?",
                (chat_id,),
            )
            r = c.fetchone()
            con.close()
            if r:
                try:
                    roots = json.loads(r[3]) if r[3] else []
                except Exception:
                    roots = []
                return {"title": r[0] or "", "workspace_id": r[1],
                        "workspace": r[2], "roots": roots, "db": db}
        return {}
    # zcode
    if not os.path.isfile(ZCODE_DB):
        return {}
    con = _ro(ZCODE_DB)
    c = con.cursor()
    c.execute("SELECT title, project_id, directory FROM session WHERE id = ?", (chat_id,))
    r = c.fetchone()
    con.close()
    if not r:
        return {}
    return {"title": r[0] or "", "project_id": r[1], "directory": r[2]}


def recent_sessions(ide: str, limit: int = 15) -> list[dict]:
    """最近会话列表，用于「当前会话不对」时告诉用户该怎么选。"""
    if ide == "qoder":
        for db in QODER_DBS:
            if os.path.isfile(db):
                rows = qoder_sessions(db)
                if rows:
                    return rows[:limit]
        return []
    return zcode_sessions()[:limit]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ide", choices=["zcode", "qoder"], required=True)
    ap.add_argument("--path", default="")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--sessions", action="store_true")
    args = ap.parse_args()

    if args.list:
        if args.ide == "zcode":
            for r in zcode_projects():
                print(f"  {r.get('directory')}   [{r.get('sessions')} 会话]  {r.get('project_id')}")
        else:
            for db in QODER_DBS:
                ws = qoder_workspaces(db)
                if ws:
                    print(f"== {db}")
                    for r in ws:
                        print(f"  {r['roots']}   {r['name']}   {r['workspace_id']}")
        return 0

    if args.sessions:
        if args.ide == "zcode":
            for r in zcode_sessions():
                print(f"  {r['title']:<48} {r['directory']}")
        else:
            for db in QODER_DBS:
                ss = qoder_sessions(db)
                if ss:
                    print(f"== {db}")
                    for r in ss:
                        print(f"  {r['title']:<48} {r['roots']}")
        return 0

    if not args.path:
        ap.error("需要 --path 或 --list/--sessions")
    r = check(args.ide, args.path)
    print(json.dumps(r, ensure_ascii=False, indent=1))
    return 0 if r["ok"] else 2


if __name__ == "__main__":
    sys.exit(main())
