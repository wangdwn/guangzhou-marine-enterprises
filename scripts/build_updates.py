#!/usr/bin/env python3
"""从 git 历史生成 data/updates.json —— 给网站提供「更新日志」。

用途：解决"数据更新了但页面看不出来"的问题。首页顶部读这个文件，
显示最近 5 次变更；catalog.html 显示全部。

字段：date / title / author / scope / files / add / del / hash

用法：python3 scripts/build_updates.py [--limit 40]
部署：每次提交后由 .github/workflows/update.yml 调用，或本地手工跑。
"""
import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "updates.json")
CST = timezone(timedelta(hours=8))

SCOPE_RULES = [
    ("data/", "底库"),
    ("index.html", "页面"),
    ("catalog.html", "页面"),
    ("ranking.html", "页面"),
    ("bay-stage.html", "页面"),
    (".github/", "自动化"),
    ("scripts/", "工具"),
    ("activity.json", "情报流"),
    ("DATA.md", "文档"),
]

FLUFF_RE = re.compile(r"^(chore|docs|feat|fix|data|style|refactor)[\(:]", re.I)


def run(args):
    return subprocess.run(args, cwd=ROOT, capture_output=True, text=True, timeout=60).stdout


def scope_of(files):
    for path, name in SCOPE_RULES:
        if any(f.startswith(path) or f == path.rstrip("/") for f in files):
            return name
    return "其他"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=40)
    args = ap.parse_args()

    sep = "\x1f"
    raw = run(["git", "log", f"-{args.limit}", f"--pretty=format:%h{sep}%ad{sep}%an{sep}%s", "--date=format:%Y-%m-%d %H:%M"])
    entries = []
    for line in raw.strip().split("\n"):
        if not line.strip():
            continue
        parts = line.split(sep)
        if len(parts) < 4:
            continue
        h, when, author, subject = parts[0], parts[1], parts[2], sep.join(parts[3:])

        numstat = run(["git", "show", "--numstat", "--format=", h])
        files, add, dele = [], 0, 0
        for ln in numstat.strip().split("\n"):
            cols = ln.split("\t")
            if len(cols) != 3:
                continue
            a, d, path = cols
            files.append(path)
            add += int(a) if a.isdigit() else 0
            dele += int(d) if d.isdigit() else 0

        entries.append({
            "date": when,
            "title": subject,
            "author": author,
            "scope": scope_of(files),
            "files": len(files),
            "add": add,
            "del": dele,
            "hash": h,
        })

    payload = {
        "generated_at": datetime.now(CST).strftime("%Y-%m-%d %H:%M"),
        "count": len(entries),
        "entries": entries,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    print(f"写出 {OUT}：{len(entries)} 条")
    for e in entries[:5]:
        print(f"  {e['date']} [{e['scope']}] {e['title'][:52]} (+{e['add']}/-{e['del']})")


if __name__ == "__main__":
    sys.exit(main())
