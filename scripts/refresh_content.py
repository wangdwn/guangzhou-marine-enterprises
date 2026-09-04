#!/usr/bin/env python3
"""Refresh Guangzhou marine enterprise CONTENT fields from verifiable sources.

Does not invent companies or financials. Applies:
  1) Field extraction already present in main_biz text
  2) Curated SSE/SZSE listing overlay (data/verified_listings.json)
  3) GB/T code normalization to 2-digit taxonomy codes
  4) Conservative name-keyword auto-tag for still-untagged marine names
  5) One additive public shipyard missing from the 广海汇 merge
"""
from __future__ import annotations

import json
import re
from collections import Counter
from copy import deepcopy
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENT_PATH = ROOT / "data" / "enterprises.json"
LISTING_PATH = ROOT / "data" / "verified_listings.json"
TAX_PATH = ROOT / "data" / "taxonomy.json"
CHANGELOG_PATH = ROOT / "data" / "content_refresh_changelog.json"

TODAY = "2026-09-04"
SCHEMA = "1.3"

PAT_CC = re.compile(r"统一社会信用代码[为是:：]?\s*([0-9A-HJ-NP-RTUW-Y]{18})")
PAT_ADDR = re.compile(r"企业注册地址位于([^，。；;]+)")
PAT_FOUNDED = re.compile(r"成立于(\d{4}-\d{2}-\d{2})")
PAT_LEGAL = re.compile(r"法定代表人[为是]([^，。,；;]+)")
PAT_CAPITAL = re.compile(r"注册资本为([^，。；;]+)")
PAT_DISTRICT = re.compile(r"广州市?((?:天河|黄埔|越秀|海珠|番禺|白云|南沙|花都|荔湾|增城|从化)区)")

# Skip labour / F&B / media false positives when auto-tagging from the name.
SKIP_NAME = re.compile(r"人力资源|餐饮|文化传播|物业|投资管理|海鲜码头|舌尖码头")

# Ordered: more specific first.
NAME_RULES = [
    ("14", "海洋交通运输业", "core", r"船舶代理|船务代理|船代"),
    ("14", "海洋交通运输业", "core", r"船舶管理"),
    ("10", "海洋船舶工业", "core", r"造船|船厂|修船|船舶工程|船舶科技|船用|海工装备"),
    ("11", "海洋工程装备制造业", "core", r"海洋工程装备"),
    ("13", "海洋工程建筑业", "core", r"打捞|航道局|疏浚"),
    ("14", "海洋交通运输业", "core", r"海运|航运|港口机械|汽车码头|集装箱码头|集装箱运输"),
    ("07", "海洋生物医药业", "core", r"海洋生物|海洋药物"),
    ("19", "海洋技术服务", "support", r"海洋测绘|海洋监测|海洋勘察"),
]

GBT_PREFIX = {
    "02": "02",
    "06": "06",
    "07": "07",
    "08": "08",
    "10": "10",
    "11": "11",
    "13": "13",
    "14": "14",
    "15": "15",
    "16": "16",
    "18": "18",
    "19": "19",
    "20": "20",
    "21": "21",
    "22": "22",
    "23": "23",
    "24": "24",
    "25": "25",
    "26": "26",
    "27": "27",
    "99": "17",  # local leftover; taxonomy 17 = 海洋教育
}


def load_json(path: Path):
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def dump_json(path: Path, obj, indent=None):
    with path.open("w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=indent)
        f.write("\n")


def normalize_gbt(code: str) -> str:
    if not code:
        return ""
    code = str(code).strip()
    if re.fullmatch(r"\d{2}", code):
        return code
    prefix = code.split("-", 1)[0]
    if prefix in GBT_PREFIX:
        return GBT_PREFIX[prefix]
    m = re.match(r"(\d{2})", code)
    return m.group(1) if m else code


def extract_from_main_biz(e: dict) -> dict:
    text = e.get("main_biz") or ""
    out = {}
    m = PAT_CC.search(text)
    if m:
        out["credit_code"] = m.group(1)
        out["credit_code_source"] = "main_biz_text"
    m = PAT_FOUNDED.search(text)
    if m:
        out["founded_at"] = m.group(1)
    m = PAT_LEGAL.search(text)
    if m:
        out["legal_rep"] = m.group(1).strip()
    m = PAT_CAPITAL.search(text)
    if m:
        out["registered_capital"] = m.group(1).strip()
    m = PAT_ADDR.search(text)
    if m:
        out["registered_address"] = m.group(1).strip()
        dm = PAT_DISTRICT.search(m.group(1))
        if dm and (not e.get("district") or e.get("district") in ("广州市", "广州")):
            out["district"] = dm.group(1)
    return out


def demote_false_a(e: dict) -> str:
    tag = e.get("tag") or ""
    tier = e.get("tier") or ""
    sisheng = e.get("sisheng") or ""
    blob = tag + tier + sisheng
    if any(k in blob for k in ("四上", "龙头", "高新技术", "专精特新", "央企国企")):
        return "D"
    return "E"


def apply_listing(e: dict, rec: dict, stats: Counter):
    cap = e.setdefault("capital", {})
    cap["listed"] = True
    cap["ticker"] = rec["ticker"]
    cap["short_name"] = rec.get("short_name", "")
    if rec.get("keep_in_932056"):
        cap["in_932056"] = bool(cap.get("in_932056") or rec.get("in_932056"))
    else:
        cap["in_932056"] = bool(rec.get("in_932056"))
    cap["grade"] = rec["grade"]
    cap["listing_source"] = rec["source"]
    cap["updated_at"] = TODAY
    if rec.get("credit_code") and not e.get("credit_code"):
        e["credit_code"] = rec["credit_code"]
        e["credit_code_source"] = rec["source"]
    elif rec.get("credit_code") and e.get("credit_code") != rec["credit_code"]:
        # Prefer SSE/SZSE overlay when the extracted/empty field differs.
        e["credit_code"] = rec["credit_code"]
        e["credit_code_source"] = rec["source"]
    stats["listing_overlay"] += 1


def auto_tag(e: dict) -> dict | None:
    name = e.get("name") or ""
    if SKIP_NAME.search(name):
        return None
    for code, major, layer, pat in NAME_RULES:
        if re.search(pat, name):
            return {
                "gbt_code": code,
                "major_name": major,
                "layer": layer,
                "marine_share": "",
                "confidence": "auto",
                "tagged_by": "name-keyword-2026-09-04",
                "tagged_at": TODAY,
            }
    return None


def yinghui_record(next_id: str) -> dict:
    return {
        "id": next_id,
        "name": "英辉南方造船（广州番禺）有限公司",
        "credit_code": "914401136187842302",
        "credit_code_source": "公开工商信息（企查查/企知道/建设通一致）",
        "district": "番禺区",
        "sector": "海洋船舶工业",
        "sector_raw": "铁路、船舶、航空航天和其他运输设备制造业",
        "main_biz": "高性能铝合金船舶研发、设计与建造；金属/非金属船舶制造、修理、改装及船舶设计服务。注册地址：广州市番禺区洛浦街西宁路40号。",
        "tag": "高新技术企业,专精特新",
        "sisheng": "",
        "tier": "潜力",
        "chain": ["船舶与海洋工程装备"],
        "chain_primary": "船舶与海洋工程装备",
        "revenue": "",
        "source": "公开工商/行业名录核验",
        "founded_at": "1992-08-10",
        "legal_rep": "严承祥",
        "registered_capital": "1979.2813万人民币",
        "registered_address": "广州市番禺区洛浦街西宁路40号",
        "website": "http://www.afaisouth.com",
        "identity": {
            "gbt_code": "10",
            "layer": "core",
            "major_name": "海洋船舶工业",
            "marine_share": ">50%",
            "confidence": "verified",
            "tagged_by": "public-register-2026-09-04",
            "tagged_at": TODAY,
        },
        "capital": {
            "grade": "D",
            "listed": False,
            "ticker": "",
            "in_932056": False,
            "updated_at": TODAY,
        },
        "facility": {
            "needs_deepwater": False,
            "depth_required_m": 0,
            "test_types": [],
            "time_window": "",
        },
        "latitude": "",
        "longitude": "",
    }


def recompute_meta(ents: list, prev_meta: dict) -> dict:
    cap = Counter(e.get("capital", {}).get("grade") for e in ents)
    layer = Counter(e.get("identity", {}).get("layer") for e in ents)
    dw = sum(1 for e in ents if e.get("facility", {}).get("needs_deepwater"))
    cc = sum(1 for e in ents if e.get("credit_code"))
    listed = sum(1 for e in ents if e.get("capital", {}).get("listed"))
    tagged = sum(1 for e in ents if e.get("identity", {}).get("major_name") not in ("", "待打标"))
    meta = deepcopy(prev_meta)
    meta.update(
        {
            "updated_at": TODAY,
            "source_snapshot_at": "2026-08-25",
            "content_refreshed_at": TODAY,
            "count": len(ents),
            "schema": SCHEMA,
            "source": "广海汇 ghh.gzlpc.gov.cn + 公开上市/工商核验",
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
            "deepwater_demand_count": dw,
            "credit_code_filled": cc,
            "listed_count": listed,
            "identity_tagged_count": tagged,
            "note": (
                "底库仍为广海汇在穗企业（产业链+重点企业去重）。"
                f"{TODAY} 内容刷新：抽取主营文本中的信用代码/成立日期等、核对A股代码、"
                "修正错挂ticker与明显错分产业、对名称可判涉海的待打标记录做自动预标，"
                "并校正英辉南方造船产业分类。未编造营收/财务。完整211只932056成分股仍不可得。"
            ),
        }
    )
    return meta


def main():
    data = load_json(ENT_PATH)
    overlay = load_json(LISTING_PATH)
    ents = data["enterprises"]
    stats = Counter()

    listing_by_name = {r["name"]: r for r in overlay["listings"]}
    delist = {r["name"]: r for r in overlay["delist_false_tickers"]}
    ident_fix = {r["name"]: r for r in overlay["identity_corrections"]}
    existing_names = {e["name"] for e in ents}

    for e in ents:
        # 1) extract from existing prose
        extracted = extract_from_main_biz(e)
        if extracted.get("credit_code") and not e.get("credit_code"):
            e["credit_code"] = extracted["credit_code"]
            e["credit_code_source"] = extracted.get("credit_code_source")
            stats["credit_code_extracted"] += 1
        for k in ("founded_at", "legal_rep", "registered_capital", "registered_address"):
            if extracted.get(k) and not e.get(k):
                e[k] = extracted[k]
                stats[f"extracted_{k}"] += 1
        if extracted.get("district"):
            e["district"] = extracted["district"]
            stats["district_from_address"] += 1

        # 2) normalize gbt codes
        ident = e.setdefault("identity", {})
        old = ident.get("gbt_code") or ""
        new = normalize_gbt(old)
        if new != old:
            ident["gbt_code"] = new
            stats["gbt_normalized"] += 1

        # 3) identity corrections
        if e["name"] in ident_fix:
            fx = ident_fix[e["name"]]
            ident["gbt_code"] = fx["gbt_code"]
            ident["major_name"] = fx["major_name"]
            ident["layer"] = fx["layer"]
            ident["confidence"] = "verified"
            ident["tagged_by"] = "public-correction-2026-09-04"
            ident["tagged_at"] = TODAY
            e["sector"] = fx["sector"]
            if fx.get("chain"):
                e["chain"] = fx["chain"]
                e["chain_primary"] = fx.get("chain_primary") or fx["chain"][0]
            if fx.get("website") and not e.get("website"):
                e["website"] = fx["website"]
            stats["identity_corrected"] += 1

        # 4) listing overlay / false ticker removal
        cap = e.setdefault("capital", {})
        if e["name"] in delist:
            cap["listed"] = False
            cap["ticker"] = ""
            cap["in_932056"] = False
            if cap.get("grade") == "A":
                cap["grade"] = demote_false_a(e)
            cap["listing_source"] = delist[e["name"]]["reason"]
            cap["updated_at"] = TODAY
            stats["false_ticker_cleared"] += 1
        elif e["name"] in listing_by_name:
            apply_listing(e, listing_by_name[e["name"]], stats)

        # 5) demote leftover A that are not listed and not in index
        if cap.get("grade") == "A" and not cap.get("listed") and not cap.get("in_932056"):
            cap["grade"] = demote_false_a(e)
            cap["listing_source"] = "原A级但非上市公司、且非已核验932056成分股，按口径下调"
            cap["updated_at"] = TODAY
            stats["false_A_demoted"] += 1

        # 6) conservative auto-tag for 待打标
        if ident.get("major_name") in ("", "待打标", None):
            suggestion = auto_tag(e)
            if suggestion:
                ident.update(suggestion)
                if not e.get("sector") or e.get("sector") == "待打标":
                    e["sector"] = suggestion["major_name"]
                stats["auto_tagged"] += 1

    # 7) additive verified shipyard
    added = []
    yinghui_name = "英辉南方造船（广州番禺）有限公司"
    if yinghui_name not in existing_names:
        max_n = 0
        for e in ents:
            m = re.match(r"E(\d+)$", e.get("id") or "")
            if m:
                max_n = max(max_n, int(m.group(1)))
        rec = yinghui_record(f"E{max_n + 1:04d}")
        ents.append(rec)
        added.append(rec["name"])
        stats["additive_verified"] += 1

    data["meta"] = recompute_meta(ents, data.get("meta") or {})
    data["enterprises"] = ents
    dump_json(ENT_PATH, data)

    changelog = {
        "date": TODAY,
        "schema": SCHEMA,
        "stats": dict(stats),
        "additive_names": added,
        "listing_names": sorted(listing_by_name),
        "identity_corrections": [r["name"] for r in overlay["identity_corrections"]],
        "false_tickers_cleared": [r["name"] for r in overlay["delist_false_tickers"]],
        "gaps": [
            "广海汇平台无公开可下载全量名录；本次未做大规模抓取。",
            "统一社会信用代码仅从已有主营文本及少数上市公司公告回填，大部分重点企业仍空。",
            "营收等财务字段仍空，未用估算值填充。",
            "932056 完整211只成分股未公开，A级仅覆盖样本文件+底库已标 true 的记录。",
            "待打标企业仍占多数；名称关键词预标需人工复核。",
        ],
    }
    dump_json(CHANGELOG_PATH, changelog, indent=2)
    print(json.dumps(changelog, ensure_ascii=False, indent=2))
    print("meta", json.dumps(data["meta"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
