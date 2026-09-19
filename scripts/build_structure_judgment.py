#!/usr/bin/env python3
"""Build structure_judgment.json — 三盘一底座可溯源指标包.

Reads enterprises meta, funding.json, notices.json. No invented GDP/finance.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENT = ROOT / "data" / "enterprises.json"
TODAY = date.today().isoformat()


def load(path: Path):
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def dump(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write("\n")


def parse_date(s: str) -> date | None:
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(s[:19], fmt).date()
        except ValueError:
            continue
    return None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--funding",
        type=Path,
        default=Path("/workspace/marine-reform/marine-monitor/app/public/data/funding.json"),
    )
    ap.add_argument(
        "--notices",
        type=Path,
        default=Path("/workspace/marine-reform/geo-ocean-bidding/docs/data/notices.json"),
    )
    ap.add_argument(
        "--out",
        type=Path,
        default=ROOT / "data" / "structure_judgment.json",
    )
    args = ap.parse_args(argv)

    ent = load(ENT)
    meta = ent.get("meta") or {}
    ents = ent.get("enterprises") or []

    capital = meta.get("capital_distribution") or Counter(
        (e.get("capital") or {}).get("grade") for e in ents
    )
    layer = meta.get("layer_distribution") or Counter(
        (e.get("identity") or {}).get("layer") for e in ents
    )
    pending = meta.get("sector_pending_count")
    if pending is None:
        pending = sum(1 for e in ents if (e.get("sector") or "") == "待打标")

    quality_tags = Counter()
    for e in ents:
        blob = " ".join(
            [
                str(e.get("tag") or ""),
                str(e.get("sisheng") or ""),
                str(e.get("tier") or ""),
            ]
        )
        if "上市" in blob or (e.get("capital") or {}).get("listed"):
            quality_tags["listed"] += 1
        if "高新" in blob:
            quality_tags["high_tech"] += 1
        if "专精" in blob:
            quality_tags["zjtx"] += 1
        if "四上" in blob:
            quality_tags["sishang"] += 1

    # funding
    funding_block = {
        "available": False,
        "source": "〔待核〕 funding.json 未找到",
        "count": 0,
        "status_dist": {},
        "items_with_source": 0,
    }
    if args.funding.exists():
        fund = load(args.funding)
        items = fund.get("items") or []
        st = Counter((i.get("status") or "〔待核〕") for i in items)
        funding_block = {
            "available": True,
            "source": f"marine-monitor/app/public/data/funding.json#items (updated={fund.get('updated')})",
            "count": fund.get("count") or len(items),
            "status_dist": dict(st),
            "items_with_source_doc": sum(1 for i in items if i.get("basisDoc") or i.get("sourceOrg")),
            "note": "专项资金只读监测；不做贷款产品货架/申请入口。",
        }

    # notices 90d
    notices_block = {
        "available": False,
        "source": "〔待核〕 notices.json 未找到",
        "total": 0,
        "last_90d_count": 0,
        "last_90d_budget_wan": None,
        "last_90d_win_wan": None,
        "with_source_url": 0,
    }
    if args.notices.exists():
        notices = load(args.notices)
        rows = notices.get("notices") or []
        cutoff = date.today() - timedelta(days=90)
        recent = []
        budget = 0.0
        win = 0.0
        budget_n = win_n = 0
        with_url = 0
        for n in rows:
            if n.get("source_url"):
                with_url += 1
            d = parse_date(str(n.get("publish_date") or ""))
            if d and d >= cutoff:
                recent.append(n)
                if n.get("budget"):
                    budget += float(n["budget"])
                    budget_n += 1
                if n.get("win_amount"):
                    win += float(n["win_amount"])
                    win_n += 1
        notices_block = {
            "available": True,
            "source": f"geo-ocean-bidding/docs/data/notices.json#notices (updated_at={notices.get('updated_at')})",
            "total": len(rows),
            "last_90d_count": len(recent),
            "last_90d_budget_wan": round(budget, 2) if budget_n else None,
            "last_90d_win_wan": round(win, 2) if win_n else None,
            "with_source_url": with_url,
            "missing_source_url": len(rows) - with_url,
            "region_dist": dict(Counter((n.get("region") or "〔待核〕") for n in recent)),
            "chain_dist": dict(Counter((n.get("chain_position") or "〔待核〕") for n in recent)),
        }

    pending_list = [
        {
            "id": "credit_code_gap",
            "label": f"统一社会信用代码未填 {meta.get('credit_code_filled', 0)}/{meta.get('count', len(ents))}",
            "source": "enterprises.json#meta.credit_code_filled",
        },
        {
            "id": "sector_pending",
            "label": f"产业「待打标」剩余 {pending}",
            "source": "enterprises.json#meta.sector_pending_count",
        },
        {
            "id": "ghh_live",
            "label": "广海汇 live 回填：云出口当前不可达，需本机快照",
            "source": "data/reports/backfill_ghh_*.json",
        },
    ]

    out = {
        "schema": "structure_judgment/1.0",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "positioning": "监测研判台 ≠ 广海汇撮合黄页。指标均可追溯至 JSON 字段或脚本输出；无数据标〔待核〕。",
        "家底盘": {
            "title": "家底盘",
            "metrics": [
                {
                    "id": "ent_total",
                    "label": "在库企业",
                    "value": meta.get("count") or len(ents),
                    "unit": "家",
                    "source": "enterprises.json#meta.count",
                },
                {
                    "id": "capital_A_E",
                    "label": "主体分层 A–E",
                    "value": dict(capital) if not isinstance(capital, dict) else capital,
                    "source": "enterprises.json#meta.capital_distribution",
                },
                {
                    "id": "layer",
                    "label": "core / support / peripheral",
                    "value": dict(layer) if not isinstance(layer, dict) else layer,
                    "source": "enterprises.json#meta.layer_distribution",
                },
                {
                    "id": "sector_pending",
                    "label": "待打标剩余",
                    "value": pending,
                    "unit": "家",
                    "source": "enterprises.json#meta.sector_pending_count",
                },
                {
                    "id": "credit_code_filled",
                    "label": "信用代码已填",
                    "value": meta.get("credit_code_filled"),
                    "unit": "家",
                    "source": "enterprises.json#meta.credit_code_filled",
                },
            ],
            "drilldown": "https://wangdwn.github.io/guangzhou-marine-enterprises/",
        },
        "经营盘": {
            "title": "经营盘",
            "notices": notices_block,
            "funding": funding_block,
            "drilldown_bidding": "https://wangdwn.github.io/geo-ocean-bidding/",
            "drilldown_funding": "https://wangdwn.github.io/marine-monitor/#/funding",
        },
        "质量盘": {
            "title": "质量盘",
            "metrics": [
                {
                    "id": "listed",
                    "label": "上市（标签或 capital.listed）",
                    "value": quality_tags.get("listed", 0),
                    "source": "enterprises.json#enterprises[].capital.listed|tag",
                },
                {
                    "id": "high_tech",
                    "label": "高新技术（tag 含「高新」）",
                    "value": quality_tags.get("high_tech", 0),
                    "source": "enterprises.json#enterprises[].tag",
                },
                {
                    "id": "zjtx",
                    "label": "专精特新（tag 含「专精」）",
                    "value": quality_tags.get("zjtx", 0),
                    "source": "enterprises.json#enterprises[].tag",
                },
                {
                    "id": "sishang",
                    "label": "四上（sisheng/tag）",
                    "value": quality_tags.get("sishang", 0),
                    "source": "enterprises.json#enterprises[].sisheng|tag",
                },
            ],
            "drift_vs_previous": None,
            "drift_note": "无上期快照，仅展示当期；上期对比〔待核〕。",
            "drilldown": "https://wangdwn.github.io/guangzhou-ocean-dashboard/",
        },
        "底座": {
            "title": "口径底座",
            "source_snapshot_at": meta.get("source_snapshot_at"),
            "content_refreshed_at": meta.get("content_refreshed_at"),
            "tag_rules_version": meta.get("tag_rules_version"),
            "schema": meta.get("schema"),
            "source": meta.get("source"),
            "pending_checklist": pending_list,
            "changelog": "data/content_refresh_changelog.json + data/reports/",
            "vs_ghh": "本站做结构判断与对账；广海汇是产业撮合平台。",
        },
    }
    dump(args.out, out)
    print(json.dumps({"wrote": str(args.out), "ent_total": out["家底盘"]["metrics"][0]["value"], "pending": pending}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
