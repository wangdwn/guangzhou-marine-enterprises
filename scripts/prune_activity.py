#!/usr/bin/env python3
"""activity.json 清理与保留策略（2026-11-26 修订）

背景：原 scraper.py 里 merged[:5000] 是硬截断，新情报挤掉旧情报，库不增长只换水，
且 360/博查 抓回来的大量是企业信息聚合站与招聘站的重复页面标题（爱企查/BOSS直聘等），
不构成情报。

现行规则：
1. 噪音剔除：聚合站、招聘站、信用查询站的页面标题（JUNK_PATTERNS）
2. 时间保留：只保留最近 RETAIN_MONTHS 个月（默认 18）
3. 去重：content 相同视为同一条，保留时间最新的一条
4. 硬顶：MAX_EVENTS 仅在异常情况下生效（正常远达不到）

时间格式兼容：
  "MM-DD HH:MM"   旧格式，年份按 now 推断（月日大于今天则视为上一年）
  "YYYY-MM-DD HH:MM" / "YYYY-MM-DD"  新格式

用法：
  python3 scripts/prune_activity.py            # 干跑，只打印统计
  python3 scripts/prune_activity.py --apply    # 写回 activity.json
  python3 scripts/prune_activity.py --months 24 --apply
"""
import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta

RETAIN_MONTHS = 18
MAX_EVENTS = 5000

JUNK_PATTERNS = (
    "爱企查", "水滴信用", "天眼查", "企查查", "启信宝", "看准网",
    "BOSS直聘", "boss直聘", "智联招聘", "前程无忧", "猎聘", "58同城",
    "就业信息网", "招聘信息网", "人才网",
)

# 泛化标题：只有"XX-招标信息""XX-采购信息"这类空壳，无项目、无金额、无日期
JUNK_CONTENT_RE = re.compile(r"[-—–]\s*(招标信息|采购信息|企业信息|工商信息)\s*$")

# 招聘/工商类只在搜索聚合来源里算噪音；Exa 抓到的招聘含岗位与年薪，反映扩产，保留
NOISY_TYPES = {"招聘", "人才招聘"}
NOISY_SOURCES = {"360搜索", "博查搜索"}

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(ROOT, "activity.json")


def parse_time(raw, now=None):
    """把 activity 的 time 字段解析成 datetime；解析不了返回 None。"""
    if not raw or not isinstance(raw, str):
        return None
    now = now or datetime.now()
    s = raw.strip()
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            pass
    m = re.match(r"^(\d{1,2})-(\d{1,2})(?:\s+(\d{1,2}):(\d{2}))?$", s)
    if m:
        mo, dy = int(m.group(1)), int(m.group(2))
        hh = int(m.group(3) or 0)
        mi = int(m.group(4) or 0)
        try:
            dt = datetime(now.year, mo, dy, hh, mi)
        except ValueError:
            return None
        if dt > now + timedelta(days=1):  # 未来日期→视为上一年
            try:
                dt = datetime(now.year - 1, mo, dy, hh, mi)
            except ValueError:
                return None
        return dt
    return None


def is_junk(event):
    text = " ".join(str(event.get(k) or "") for k in ("content", "source"))
    if any(p in text for p in JUNK_PATTERNS):
        return True
    content = str(event.get("content") or "")
    if JUNK_CONTENT_RE.search(content):
        return True
    if event.get("type") in NOISY_TYPES and event.get("source") in NOISY_SOURCES:
        return True
    return False


def clean_events(events, months=RETAIN_MONTHS, now=None, max_events=MAX_EVENTS):
    """返回 (kept, stats)。kept 按时间倒序（新在前）。"""
    now = now or datetime.now()
    cutoff = now - timedelta(days=int(months * 30.44))

    stats = {"输入": len(events), "噪音": 0, "过期": 0, "重复": 0, "无时间": 0, "超出硬顶": 0, "输出": 0}
    seen = set()
    kept = []

    for e in events or []:
        if not isinstance(e, dict):
            continue
        if is_junk(e):
            stats["噪音"] += 1
            continue
        dt = parse_time(e.get("time"), now)
        if dt is None:
            stats["无时间"] += 1
            continue
        if dt < cutoff:
            stats["过期"] += 1
            continue
        key = (e.get("content") or "").strip()
        if not key or key in seen:
            stats["重复"] += 1
            continue
        seen.add(key)
        kept.append((dt, e))

    kept.sort(key=lambda x: x[0], reverse=True)
    kept = [e for _, e in kept]
    if len(kept) > max_events:
        stats["超出硬顶"] = len(kept) - max_events
        kept = kept[:max_events]
    stats["输出"] = len(kept)
    stats["时间窗起"] = cutoff.strftime("%Y-%m-%d")
    return kept, stats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--months", type=int, default=RETAIN_MONTHS)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--path", default=PATH)
    args = ap.parse_args()

    with open(args.path, encoding="utf-8") as f:
        events = json.load(f)

    kept, stats = clean_events(events, months=args.months)
    print(json.dumps(stats, ensure_ascii=False, indent=1))

    if args.apply:
        with open(args.path, "w", encoding="utf-8") as f:
            json.dump(kept, f, ensure_ascii=False, indent=2)
        print(f"已写回 {args.path}")
    else:
        print("干跑，未写回。加 --apply 生效。")


if __name__ == "__main__":
    sys.exit(main())
