#!/usr/bin/env python3
"""生成 data/catalog_stats.json —— 投融资目录归口统计（小而快，供 catalog.html 直接读）

为什么单独出一个小文件：enterprises.json 有 6.6MB，手机上拉不动；
catalog 页只需要分布与代表企业，预计算后只有几 KB。

用法：python3 scripts/build_catalog_stats.py
"""
import json
import os
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CST = timezone(timedelta(hours=8))

TIER_RANK = {"龙头": 0, "重点": 1, "潜力": 2}
GRADE_RANK = {"A": 0, "B": 1, "C": 2, "D": 3, "E": 4}


def main():
    with open(os.path.join(ROOT, "data/enterprises.json"), encoding="utf-8") as f:
        doc = json.load(f)
    with open(os.path.join(ROOT, "data/catalog2026.json"), encoding="utf-8") as f:
        catalog = json.load(f)

    ents = doc["enterprises"]
    meta = doc.get("meta", {})
    names = {c["code"]: c["name"] for c in catalog["categories"]}

    by_code = defaultdict(list)
    levels = Counter()
    for e in ents:
        cat = e.get("catalog") or {}
        code = cat.get("code") or "unlisted"
        levels[cat.get("level") or "unlisted"] += 1
        by_code[code].append(e)

    def rank(e):
        return (
            TIER_RANK.get(e.get("tier"), 9),
            GRADE_RANK.get((e.get("capital") or {}).get("grade"), 9),
            0 if (e.get("capital") or {}).get("listed") else 1,
            e.get("name") or "",
        )

    categories = []
    for c in catalog["categories"]:
        pool = sorted(by_code.get(c["code"], []), key=rank)
        categories.append({
            "code": c["code"],
            "name": c["name"],
            "count": len(pool),
            "level_mix": dict(Counter((e.get("catalog") or {}).get("level") or "unlisted" for e in pool)),
            "top": [
                {
                    "name": e.get("name"),
                    "tier": e.get("tier") or "",
                    "grade": (e.get("capital") or {}).get("grade") or "",
                    "chain": e.get("chain_primary") or "",
                    "district": e.get("district") or "",
                }
                for e in pool[:8]
            ],
        })

    unlisted = sorted(by_code.get("unlisted", []), key=rank)
    total = len(ents)
    aligned = total - len(unlisted)

    # 未归口的主要来源：按 GB/T 大类汇总，说明为什么目录未单列
    gbt_unlisted = Counter(
        (e.get("identity") or {}).get("gbt_code") or "—" for e in unlisted
    )
    gbt_names = {}
    for e in unlisted:
        g = (e.get("identity") or {}).get("gbt_code") or "—"
        if g not in gbt_names:
            gbt_names[g] = (e.get("identity") or {}).get("major_name") or ""

    payload = {
        "generated_at": datetime.now(CST).strftime("%Y-%m-%d %H:%M"),
        "standard": catalog["standard"],
        "issued_at": catalog.get("issued_at"),
        "published_at": catalog.get("published_at"),
        "source_url": catalog.get("source_url"),
        "total": total,
        "aligned": aligned,
        "coverage": round(aligned * 100.0 / total, 1),
        "unlisted": len(unlisted),
        "levels": dict(levels),
        "aligned_at": meta.get("catalog_aligned_at"),
        "categories": categories,
        "unlisted_breakdown": [
            {"gbt": g, "major": gbt_names.get(g, ""), "count": n}
            for g, n in gbt_unlisted.most_common(10)
        ],
        "mapping": catalog.get("gbt_mapping", {}),
    }

    out = os.path.join(ROOT, "data/catalog_stats.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    print(f"写出 {out}")
    print(f"  总 {total} / 已归口 {aligned}（{payload['coverage']}%）/ 未归口 {len(unlisted)}")
    for c in categories:
        print(f"  {c['code']} {c['name']}: {c['count']}")


if __name__ == "__main__":
    main()
