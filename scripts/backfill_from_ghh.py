#!/usr/bin/env python3
"""Backfill ent fields from 广海汇 public listEnterprise / offline snapshot.

Hard constraints (Cursor 提示词包 W1):
  - Match by credit_code or exact enterprise name only.
  - Fill credit_code / lat / lon / main_biz / chain* when source has values.
  - Never invent revenue or other financials.
  - No login bypass, no form submit, no auth-only write APIs.

Usage:
  python3 scripts/backfill_from_ghh.py              # try live API, else fail soft
  python3 scripts/backfill_from_ghh.py --dry-run
  python3 scripts/backfill_from_ghh.py --from-snapshot data/ghh_snapshots/listEnterprise.json
  python3 scripts/backfill_from_ghh.py --page-size 100 --max-pages 80

Snapshot shape (any of):
  {"data":{"list":[...], "total": N}} | {"list":[...]} | {"records":[...]} | [...]
Record field aliases accepted: name/enterpriseName, uscNo/creditCode/credit_code,
  lat/latitude/y, lon/longitude/x, mainBiz/main_biz/businessScope, chain/industryChain.
"""
from __future__ import annotations

import argparse
import json
import ssl
import sys
import urllib.error
import urllib.request
from collections import Counter
from copy import deepcopy
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENT_PATH = ROOT / "data" / "enterprises.json"
REPORT_DIR = ROOT / "data" / "reports"
GHH_URL = "https://ghh.gzlpc.gov.cn/hyjj_backend/listEnterprise"
TODAY = date.today().isoformat()
UA = (
    "Mozilla/5.0 (compatible; GuangzhouMarineMonitor/1.0; "
    "+https://github.com/wangdwn/guangzhou-marine-enterprises)"
)


def load_json(path: Path):
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def dump_json(path: Path, obj, indent=2):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=indent)
        f.write("\n")


def norm_name(s: str) -> str:
    if not s:
        return ""
    s = str(s).strip()
    for a, b in (("（", "("), ("）", ")"), (" ", ""), ("\u3000", "")):
        s = s.replace(a, b)
    return s


def pick(rec: dict, *keys: str):
    for k in keys:
        if k in rec and rec[k] not in (None, ""):
            return rec[k]
    return None


def normalize_record(rec: dict) -> dict | None:
    if not isinstance(rec, dict):
        return None
    name = pick(rec, "name", "enterpriseName", "entName", "companyName", "qymc")
    if not name:
        return None
    cc = pick(rec, "uscNo", "creditCode", "credit_code", "tyxydm", "uniscid")
    lat = pick(rec, "lat", "latitude", "y", "wd", "gcj02Lat")
    lon = pick(rec, "lon", "lng", "longitude", "x", "jd", "gcj02Lng")
    main = pick(rec, "mainBiz", "main_biz", "businessScope", "jyfw", "intro", "desc")
    chain = pick(rec, "chain", "industryChain", "chains", "cyl")
    chain_primary = pick(rec, "chain_primary", "primaryChain", "cylPrimary")
    if isinstance(chain, str):
        chain = [c.strip() for c in chain.replace("、", ",").split(",") if c.strip()]
    out = {
        "name": str(name).strip(),
        "credit_code": str(cc).strip() if cc else "",
        "latitude": str(lat).strip() if lat not in (None, "") else "",
        "longitude": str(lon).strip() if lon not in (None, "") else "",
        "main_biz": str(main).strip() if main else "",
        "chain": chain if isinstance(chain, list) else [],
        "chain_primary": str(chain_primary).strip() if chain_primary else "",
        "raw_keys": sorted(rec.keys()),
    }
    if out["chain"] and not out["chain_primary"]:
        out["chain_primary"] = out["chain"][0]
    return out


def extract_list(payload) -> tuple[list, int | None]:
    if isinstance(payload, list):
        return payload, len(payload)
    if not isinstance(payload, dict):
        return [], None
    total = pick(payload, "total", "count", "totalCount")
    for key in ("list", "records", "rows", "items", "enterprises", "data"):
        val = payload.get(key)
        if isinstance(val, list):
            return val, int(total) if total is not None else len(val)
        if isinstance(val, dict):
            nested, nested_total = extract_list(val)
            if nested:
                return nested, nested_total if nested_total is not None else (
                    int(total) if total is not None else len(nested)
                )
    return [], int(total) if total is not None else None


def post_ghh(page_num: int, page_size: int, timeout: float = 25.0) -> dict:
    body = json.dumps(
        {"pageNum": page_num, "pageSize": page_size},
        ensure_ascii=False,
    ).encode("utf-8")
    req = urllib.request.Request(
        GHH_URL,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json;charset=UTF-8",
            "Accept": "application/json, text/plain, */*",
            "User-Agent": UA,
            "Origin": "https://ghh.gzlpc.gov.cn",
            "Referer": "https://ghh.gzlpc.gov.cn/",
        },
    )
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
        return json.loads(raw) if raw.strip() else {}


def fetch_live(page_size: int, max_pages: int) -> tuple[list[dict], dict]:
    meta = {"mode": "live", "url": GHH_URL, "pages": 0, "errors": []}
    records: list[dict] = []
    seen_names: set[str] = set()
    for page in range(1, max_pages + 1):
        try:
            payload = post_ghh(page, page_size)
        except Exception as exc:  # noqa: BLE001 — report to caller
            meta["errors"].append({"page": page, "error": f"{type(exc).__name__}: {exc}"})
            break
        rows, total = extract_list(payload)
        if not rows:
            meta["errors"].append({"page": page, "error": "empty list", "payload_keys": list(payload)[:20] if isinstance(payload, dict) else type(payload).__name__})
            break
        meta["pages"] += 1
        if total is not None:
            meta["remote_total"] = total
        for row in rows:
            n = normalize_record(row)
            if not n:
                continue
            key = norm_name(n["name"])
            if key in seen_names:
                continue
            seen_names.add(key)
            records.append(n)
        if len(rows) < page_size:
            break
        if total is not None and len(records) >= int(total):
            break
    meta["fetched"] = len(records)
    return records, meta


def load_snapshot(path: Path) -> tuple[list[dict], dict]:
    payload = load_json(path)
    rows, total = extract_list(payload)
    records = []
    for row in rows:
        n = normalize_record(row)
        if n:
            records.append(n)
    return records, {
        "mode": "snapshot",
        "path": str(path),
        "remote_total": total,
        "fetched": len(records),
    }


def fill_rate(ents: list, field_pred) -> tuple[int, float]:
    n = len(ents) or 1
    c = sum(1 for e in ents if field_pred(e))
    return c, 100.0 * c / n


def apply_backfill(
    ents: list, source_recs: list[dict], dry_run: bool
) -> tuple[Counter, list, list]:
    by_cc = {}
    by_name = {}
    for e in ents:
        cc = (e.get("credit_code") or "").strip()
        if cc:
            by_cc[cc] = e
        by_name[norm_name(e.get("name") or "")] = e

    stats: Counter = Counter()
    conflicts: list = []
    unmatched: list = []

    for src in source_recs:
        target = None
        match_via = None
        scc = (src.get("credit_code") or "").strip()
        if scc and scc in by_cc:
            target = by_cc[scc]
            match_via = "credit_code"
        else:
            sn = norm_name(src["name"])
            if sn in by_name:
                target = by_name[sn]
                match_via = "name"

        if not target:
            unmatched.append({"name": src["name"], "credit_code": scc})
            stats["unmatched"] += 1
            continue

        stats["matched"] += 1
        stats[f"match_via_{match_via}"] += 1

        # credit_code
        if scc:
            cur = (target.get("credit_code") or "").strip()
            if not cur:
                if not dry_run:
                    target["credit_code"] = scc
                    target["credit_code_source"] = f"ghh-backfill:{TODAY}"
                stats["filled_credit_code"] += 1
            elif cur != scc:
                conflicts.append(
                    {
                        "name": target.get("name"),
                        "field": "credit_code",
                        "local": cur,
                        "ghh": scc,
                    }
                )
                stats["conflict_credit_code"] += 1

        # coords
        if src.get("latitude") and src.get("longitude"):
            clat = str(target.get("latitude") or "").strip()
            clon = str(target.get("longitude") or "").strip()
            if not clat or not clon:
                if not dry_run:
                    target["latitude"] = src["latitude"]
                    target["longitude"] = src["longitude"]
                    target["coord_source"] = f"ghh-backfill:{TODAY}"
                stats["filled_coords"] += 1
            elif clat != src["latitude"] or clon != src["longitude"]:
                # keep local; record conflict only if both sides present and differ
                conflicts.append(
                    {
                        "name": target.get("name"),
                        "field": "coords",
                        "local": [clat, clon],
                        "ghh": [src["latitude"], src["longitude"]],
                    }
                )
                stats["conflict_coords"] += 1

        # main_biz
        if src.get("main_biz") and len(src["main_biz"]) > 5:
            cur = (target.get("main_biz") or "").strip()
            if not cur or cur in ("-", "—"):
                if not dry_run:
                    target["main_biz"] = src["main_biz"]
                    target["main_biz_source"] = f"ghh-backfill:{TODAY}"
                stats["filled_main_biz"] += 1

        # chain
        if src.get("chain") and not target.get("chain"):
            if not dry_run:
                target["chain"] = src["chain"]
                target["chain_primary"] = src.get("chain_primary") or src["chain"][0]
                target["chain_source"] = f"ghh-backfill:{TODAY}"
            stats["filled_chain"] += 1

    stats["conflicts"] = len(conflicts)
    return stats, conflicts, unmatched


def pct(n: int, d: int) -> float:
    return round(100.0 * n / d, 2) if d else 0.0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--from-snapshot", type=Path, help="Offline GHH JSON dump")
    ap.add_argument("--page-size", type=int, default=100)
    ap.add_argument("--max-pages", type=int, default=100)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--write-empty-report", action="store_true", help="Always write report even if fetch fails")
    args = ap.parse_args(argv)

    data = load_json(ENT_PATH)
    ents = data["enterprises"]
    before = {
        "credit_code": fill_rate(ents, lambda e: bool(str(e.get("credit_code") or "").strip())),
        "coords": fill_rate(
            ents,
            lambda e: bool(str(e.get("latitude") or "").strip())
            and bool(str(e.get("longitude") or "").strip()),
        ),
        "main_biz": fill_rate(ents, lambda e: len(str(e.get("main_biz") or "").strip()) > 5),
        "chain": fill_rate(ents, lambda e: bool(e.get("chain"))),
    }

    fetch_meta: dict
    if args.from_snapshot:
        source_recs, fetch_meta = load_snapshot(args.from_snapshot)
    else:
        source_recs, fetch_meta = fetch_live(args.page_size, args.max_pages)

    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "script": "scripts/backfill_from_ghh.py",
        "ghh_endpoint": GHH_URL,
        "fetch": fetch_meta,
        "local_total": len(ents),
        "source_records": len(source_recs),
        "before": {k: {"filled": v[0], "pct": round(v[1], 2)} for k, v in before.items()},
        "dry_run": args.dry_run,
        "note": "未编造营收/财务。广海汇不可达时请用 --from-snapshot 导入本机抓取的公开 JSON。",
    }

    if not source_recs:
        report["status"] = "no_source"
        report["after"] = report["before"]
        report["stats"] = {"matched": 0, "unmatched": 0, "conflicts": 0}
        report["acceptance"] = {
            "credit_code_improved": False,
            "coords_improved": False,
            "reason": "live GHH unreachable or snapshot empty; no fields written",
        }
        out = REPORT_DIR / f"backfill_ghh_{TODAY}.json"
        dump_json(out, report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        print(f"Wrote {out}", file=sys.stderr)
        return 2 if not args.write_empty_report else 0

    stats, conflicts, unmatched = apply_backfill(ents, source_recs, args.dry_run)
    after = {
        "credit_code": fill_rate(ents, lambda e: bool(str(e.get("credit_code") or "").strip())),
        "coords": fill_rate(
            ents,
            lambda e: bool(str(e.get("latitude") or "").strip())
            and bool(str(e.get("longitude") or "").strip()),
        ),
        "main_biz": fill_rate(ents, lambda e: len(str(e.get("main_biz") or "").strip()) > 5),
        "chain": fill_rate(ents, lambda e: bool(e.get("chain"))),
    }

    if not args.dry_run and (
        stats.get("filled_credit_code")
        or stats.get("filled_coords")
        or stats.get("filled_main_biz")
        or stats.get("filled_chain")
    ):
        meta = deepcopy(data.get("meta") or {})
        meta["content_refreshed_at"] = TODAY
        meta["updated_at"] = TODAY
        meta["credit_code_filled"] = after["credit_code"][0]
        meta["backfill_ghh_at"] = TODAY
        meta["source_snapshot_at"] = meta.get("source_snapshot_at") or TODAY
        note = meta.get("note") or ""
        addon = f" {TODAY} 广海汇回填：credit_code/坐标/主营/链字段按名或信用代码匹配写入，未编造财务。"
        if addon.strip() not in note:
            meta["note"] = (note + addon).strip()
        data["meta"] = meta
        data["enterprises"] = ents
        dump_json(ENT_PATH, data, indent=None)

    report.update(
        {
            "status": "ok",
            "stats": dict(stats),
            "after": {k: {"filled": v[0], "pct": round(v[1], 2)} for k, v in after.items()},
            "delta_pct": {
                k: round(after[k][1] - before[k][1], 2) for k in before
            },
            "conflicts_sample": conflicts[:50],
            "unmatched_sample": unmatched[:50],
            "unmatched_count": len(unmatched),
            "acceptance": {
                "credit_code_improved": after["credit_code"][1] > before["credit_code"][1],
                "coords_improved": after["coords"][1] > before["coords"][1],
            },
        }
    )
    out = REPORT_DIR / f"backfill_ghh_{TODAY}.json"
    dump_json(out, report)
    dump_json(REPORT_DIR / f"backfill_ghh_conflicts_{TODAY}.json", conflicts)
    dump_json(REPORT_DIR / f"backfill_ghh_unmatched_{TODAY}.json", unmatched[:500])
    print(json.dumps({k: report[k] for k in report if k not in ("conflicts_sample", "unmatched_sample")}, ensure_ascii=False, indent=2))
    print(f"Wrote {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
