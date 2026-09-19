#!/usr/bin/env python3
"""Sector auto-tag rules v1 for 待打标 enterprises.

Maps name + main_biz (+ light sector_raw hints) → GB/T 20794-2021 major labels.
Writes:
  - high-confidence tags into enterprises.json (identity.confidence=auto)
  - data/reports/tag_sector_rules_v1_preview.json
  - data/reports/tag_sector_rules_v1_low_confidence.json (manual review)
  - data/reports/tag_sector_rules_v1_review.csv

Never invents revenue. Does not expand the roster.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from copy import deepcopy
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENT_PATH = ROOT / "data" / "enterprises.json"
TAX_PATH = ROOT / "data" / "taxonomy.json"
REPORT_DIR = ROOT / "data" / "reports"
RULE_VERSION = "tag_sector_rules_v1"
TODAY = date.today().isoformat()

# Skip obvious non-marine name traps before applying rules.
SKIP_NAME = re.compile(
    r"人力资源|劳务派遣|餐饮|火锅|烧烤|茶楼|物业|投资管理|资产管理|融资租赁|"
    r"文化传播|广告|传媒|房地产|置业|海鲜码头|舌尖码头|超市|便利店"
)

# (gbt_code, major_name, layer, confidence high|low, pattern)
# More specific patterns first.
RULES: list[tuple[str, str, str, str, str]] = [
    ("14", "海洋交通运输业", "core", "high", r"船舶代理|船务代理|船代|无船承运"),
    ("14", "海洋交通运输业", "core", "high", r"船舶管理|海务管理"),
    ("10", "海洋船舶工业", "core", "high", r"造船|船厂|修船|船舶制造|船舶修理|船舶改装|船舶工程|船用设备|船用机电"),
    ("11", "海洋工程装备制造业", "core", "high", r"海洋工程装备|海工装备|海洋工程制造|钻井平台|海洋平台"),
    ("13", "海洋工程建筑业", "core", "high", r"航道局|疏浚|打捞局|海洋工程建筑|围海|吹填"),
    ("14", "海洋交通运输业", "core", "high", r"海运|航运|远洋运输|集装箱码头|汽车码头|港口机械|港口装卸|轮驳|拖轮"),
    ("07", "海洋生物医药业", "core", "high", r"海洋生物医药|海洋药物|海洋生物技术|藻类生物活性"),
    ("08", "海洋电力业", "core", "high", r"海上风电|海洋风力|潮流能|波浪能|海洋能发电"),
    ("09", "海水淡化与综合利用业", "core", "high", r"海水淡化|海水综合利用|苦咸水淡化"),
    ("01", "海洋渔业", "core", "high", r"远洋捕捞|海洋捕捞|海水养殖|海洋渔业"),
    ("02", "海洋水产品加工业", "core", "high", r"水产品加工|海产品加工|冷冻水产"),
    ("19", "海洋技术服务", "support", "high", r"海洋测绘|海洋监测|海洋勘察|海洋调查|海洋环评|海事检验"),
    ("15", "海洋旅游业", "core", "high", r"邮轮|游艇会|滨海旅游|海上旅游|潜水旅游"),
    ("17", "海洋教育", "support", "high", r"海洋大学|海事大学|航海学院|海洋职业技术"),
    ("04", "海洋矿业", "core", "high", r"海砂|海洋矿产|滨海砂矿|深海矿产"),
    ("03", "海洋油气业", "core", "high", r"海洋油气|海上油气|海洋石油|海洋天然气"),
    # Lower confidence: broader keywords — review required
    ("14", "海洋交通运输业", "core", "low", r"(?<![陆空])航运|船务|海事服务|货运代理.*海|海运代理"),
    ("11", "海洋工程装备制造业", "core", "low", r"海洋工程|海工"),
    ("07", "海洋生物医药业", "core", "low", r"海洋生物(?!医药)"),
    ("19", "海洋技术服务", "support", "low", r"海洋科技|海洋技术|海洋信息|海洋咨询"),
    ("15", "海洋旅游业", "peripheral", "low", r"滨海|邮轮旅游|游艇"),
    ("10", "海洋船舶工业", "core", "low", r"船舶科技|船舶设计|船舶配套"),
]

# sector_raw → only boost confidence when name/main already matched; alone = low hint list
RAW_HINTS = {
    "交通运输、仓储和邮政业": ("14", "海洋交通运输业", "core"),
    "农、林、牧、渔业": ("01", "海洋渔业", "core"),
    "采矿业": ("04", "海洋矿业", "core"),
}


def load_json(path: Path):
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def dump_json(path: Path, obj, indent=2):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=indent)
        f.write("\n")


def is_pending(e: dict) -> bool:
    sector = e.get("sector") or ""
    major = (e.get("identity") or {}).get("major_name") or ""
    return sector in ("", "待打标", "未分类") or major in ("", "待打标", "未分类", None)


def score_match(e: dict) -> dict | None:
    name = e.get("name") or ""
    main = e.get("main_biz") or ""
    if SKIP_NAME.search(name):
        return None
    blob = f"{name} {main}"
    for code, major, layer, conf, pat in RULES:
        if re.search(pat, blob):
            return {
                "gbt_code": code,
                "major_name": major,
                "layer": layer,
                "confidence": "auto" if conf == "high" else "auto_low",
                "rule_confidence": conf,
                "tagged_by": RULE_VERSION,
                "tagged_at": TODAY,
                "matched_pattern": pat,
                "evidence": {
                    "name": name,
                    "main_biz_excerpt": (main[:120] + ("…" if len(main) > 120 else "")),
                    "sector_raw": e.get("sector_raw") or "",
                },
            }
    # raw-only hint → always low confidence review, never auto-apply alone
    raw = e.get("sector_raw") or ""
    if raw in RAW_HINTS and re.search(r"海|船|港|渔|航道|航运", blob):
        code, major, layer = RAW_HINTS[raw]
        return {
            "gbt_code": code,
            "major_name": major,
            "layer": layer,
            "confidence": "auto_low",
            "rule_confidence": "low",
            "tagged_by": RULE_VERSION,
            "tagged_at": TODAY,
            "matched_pattern": f"sector_raw:{raw}+marine_token",
            "evidence": {
                "name": name,
                "main_biz_excerpt": (main[:120] + ("…" if len(main) > 120 else "")),
                "sector_raw": raw,
            },
        }
    return None


def apply_high(e: dict, suggestion: dict) -> None:
    ident = e.setdefault("identity", {})
    ident.update(
        {
            "gbt_code": suggestion["gbt_code"],
            "major_name": suggestion["major_name"],
            "layer": suggestion["layer"],
            "marine_share": ident.get("marine_share") or "",
            "confidence": "auto",
            "tagged_by": RULE_VERSION,
            "tagged_at": TODAY,
        }
    )
    e["sector"] = suggestion["major_name"]


def recompute_meta(ents: list, prev: dict) -> dict:
    cap = Counter((e.get("capital") or {}).get("grade") for e in ents)
    layer = Counter((e.get("identity") or {}).get("layer") for e in ents)
    sector_pending = sum(1 for e in ents if (e.get("sector") or "") == "待打标")
    cc = sum(1 for e in ents if str(e.get("credit_code") or "").strip())
    listed = sum(1 for e in ents if (e.get("capital") or {}).get("listed"))
    tagged = sum(
        1
        for e in ents
        if (e.get("identity") or {}).get("major_name") not in ("", "待打标", None)
    )
    meta = deepcopy(prev)
    meta.update(
        {
            "updated_at": TODAY,
            "content_refreshed_at": TODAY,
            "count": len(ents),
            "credit_code_filled": cc,
            "listed_count": listed,
            "identity_tagged_count": tagged,
            "sector_pending_count": sector_pending,
            "tag_rules_version": RULE_VERSION,
            "capital_distribution": {
                "A": cap.get("A", 0),
                "B": cap.get("B", 0),
                "C": cap.get("C", 0),
                "D": cap.get("D", 0),
                "E": cap.get("E", 0),
            },
            "layer_distribution": {
                "core": layer.get("core", 0),
                "support": layer.get("support", 0),
                "peripheral": layer.get("peripheral", 0),
            },
        }
    )
    note = meta.get("note") or ""
    addon = (
        f" {TODAY} 应用 {RULE_VERSION}：名称+主营关键词预标高置信度记录；"
        "低置信度仅写入复核清单。未编造营收/财务。未扩大名录。"
    )
    if RULE_VERSION not in note:
        meta["note"] = (note + addon).strip()
    return meta


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--apply-low", action="store_true", help="Also apply low-confidence (default: review only)")
    args = ap.parse_args(argv)

    data = load_json(ENT_PATH)
    ents = data["enterprises"]
    pending_before = sum(1 for e in ents if (e.get("sector") or "") == "待打标")

    high_rows = []
    low_rows = []
    stats = Counter()

    for e in ents:
        if not is_pending(e):
            continue
        stats["pending_scanned"] += 1
        sug = score_match(e)
        if not sug:
            stats["no_match"] += 1
            continue
        row = {
            "id": e.get("id"),
            "name": e.get("name"),
            "sector_before": e.get("sector"),
            **{k: sug[k] for k in ("gbt_code", "major_name", "layer", "rule_confidence", "matched_pattern")},
            "evidence": sug["evidence"],
        }
        if sug["rule_confidence"] == "high":
            high_rows.append(row)
            stats["high"] += 1
            if not args.dry_run:
                apply_high(e, sug)
                stats["applied_high"] += 1
        else:
            low_rows.append(row)
            stats["low"] += 1
            if args.apply_low and not args.dry_run:
                apply_high(e, sug)
                e["identity"]["confidence"] = "auto_low"
                stats["applied_low"] += 1

    pending_after = sum(1 for e in ents if (e.get("sector") or "") == "待打标")

    if not args.dry_run and stats.get("applied_high", 0) + stats.get("applied_low", 0) > 0:
        data["meta"] = recompute_meta(ents, data.get("meta") or {})
        data["enterprises"] = ents
        dump_json(ENT_PATH, data, indent=None)

    preview = {
        "rule_version": RULE_VERSION,
        "generated_at": TODAY,
        "dry_run": args.dry_run,
        "pending_before": pending_before,
        "pending_after": pending_after if not args.dry_run else pending_before - stats["high"],
        "stats": dict(stats),
        "high_confidence_count": len(high_rows),
        "low_confidence_count": len(low_rows),
        "high_sample": high_rows[:30],
        "acceptance": {
            "pending_decreased": (pending_after if not args.dry_run else pending_before - stats["high"])
            < pending_before,
            "low_confidence_review_written": True,
        },
    }
    dump_json(REPORT_DIR / "tag_sector_rules_v1_preview.json", preview)
    dump_json(REPORT_DIR / "tag_sector_rules_v1_low_confidence.json", low_rows)
    dump_json(REPORT_DIR / "tag_sector_rules_v1_high_confidence.json", high_rows)

    csv_path = REPORT_DIR / "tag_sector_rules_v1_review.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "id",
                "name",
                "sector_before",
                "gbt_code",
                "major_name",
                "layer",
                "rule_confidence",
                "matched_pattern",
                "sector_raw",
                "main_biz_excerpt",
            ],
        )
        w.writeheader()
        for row in low_rows + high_rows:
            w.writerow(
                {
                    "id": row["id"],
                    "name": row["name"],
                    "sector_before": row["sector_before"],
                    "gbt_code": row["gbt_code"],
                    "major_name": row["major_name"],
                    "layer": row["layer"],
                    "rule_confidence": row["rule_confidence"],
                    "matched_pattern": row["matched_pattern"],
                    "sector_raw": row["evidence"].get("sector_raw", ""),
                    "main_biz_excerpt": row["evidence"].get("main_biz_excerpt", ""),
                }
            )

    print(json.dumps(preview, ensure_ascii=False, indent=2))
    print(f"Wrote reports under {REPORT_DIR}", file=__import__("sys").stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
