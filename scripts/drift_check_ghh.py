#!/usr/bin/env python3
"""Quarterly / on-demand drift check: local enterprises total vs 广海汇 listEnterprise total.

Writes data/reports/drift_ghh_YYYY-MM-DD.json for the D 底座更新日志.
Never bypasses auth; public POST only. Offline: --remote-total N.
"""
from __future__ import annotations

import argparse
import json
import ssl
import urllib.request
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENT_PATH = ROOT / "data" / "enterprises.json"
REPORT_DIR = ROOT / "data" / "reports"
CHANGELOG = ROOT / "data" / "content_refresh_changelog.json"
GHH_URL = "https://ghh.gzlpc.gov.cn/hyjj_backend/listEnterprise"
TODAY = date.today().isoformat()


def load_json(path: Path):
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def dump_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write("\n")


def fetch_remote_total(timeout: float = 25.0) -> tuple[int | None, dict]:
    body = json.dumps({"pageNum": 1, "pageSize": 1}).encode()
    req = urllib.request.Request(
        GHH_URL,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json;charset=UTF-8",
            "Accept": "application/json",
            "User-Agent": "GuangzhouMarineMonitor/1.0",
            "Origin": "https://ghh.gzlpc.gov.cn",
            "Referer": "https://ghh.gzlpc.gov.cn/",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ssl.create_default_context()) as resp:
            payload = json.loads(resp.read().decode("utf-8", errors="replace") or "{}")
    except Exception as exc:  # noqa: BLE001
        return None, {"ok": False, "error": f"{type(exc).__name__}: {exc}"}

    total = None
    if isinstance(payload, dict):
        for key in ("total", "count", "totalCount"):
            if key in payload and payload[key] is not None:
                total = int(payload[key])
                break
        data = payload.get("data")
        if total is None and isinstance(data, dict):
            for key in ("total", "count", "totalCount"):
                if key in data and data[key] is not None:
                    total = int(data[key])
                    break
    return total, {"ok": True, "payload_keys": list(payload)[:20] if isinstance(payload, dict) else type(payload).__name__}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--remote-total", type=int, help="Manual GHH total when live API unreachable")
    args = ap.parse_args(argv)

    data = load_json(ENT_PATH)
    local_total = int((data.get("meta") or {}).get("count") or len(data.get("enterprises") or []))
    fetch_info: dict
    if args.remote_total is not None:
        remote_total = args.remote_total
        fetch_info = {"ok": True, "mode": "manual", "remote_total": remote_total}
    else:
        remote_total, fetch_info = fetch_remote_total()
        fetch_info["mode"] = "live"

    delta = None if remote_total is None else local_total - remote_total
    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "date": TODAY,
        "script": "scripts/drift_check_ghh.py",
        "ghh_endpoint": GHH_URL,
        "local_total": local_total,
        "local_source_snapshot_at": (data.get("meta") or {}).get("source_snapshot_at"),
        "remote_total": remote_total,
        "delta_local_minus_remote": delta,
        "fetch": fetch_info,
        "positioning": "本站为监测研判底库，不是广海汇企业撮合黄页；差额需人工解释（口径/去重/快照日）。",
    }
    out = REPORT_DIR / f"drift_ghh_{TODAY}.json"
    dump_json(out, report)

    # Append pointer into content changelog if present
    try:
        clog = load_json(CHANGELOG) if CHANGELOG.exists() else {}
    except json.JSONDecodeError:
        clog = {}
    clog.setdefault("drift_checks", []).append(
        {"date": TODAY, "report": str(out.relative_to(ROOT)), "delta": delta, "remote_total": remote_total}
    )
    dump_json(CHANGELOG, clog)

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if remote_total is not None else 2


if __name__ == "__main__":
    raise SystemExit(main())
