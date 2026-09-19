#!/usr/bin/env python3
"""Apply W1 tag patch without replacing the full enterprises.json blob."""
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
ENT = ROOT / "data" / "enterprises.json"
PATCH = ROOT / "data" / "reports" / "w1_apply_patch.json"

def main():
    data = json.loads(ENT.read_text(encoding="utf-8"))
    patch = json.loads(PATCH.read_text(encoding="utf-8"))
    by_id = {e["id"]: e for e in data["enterprises"]}
    n = 0
    for row in patch["enterprise_patches"]:
        e = by_id.get(row["id"])
        if not e:
            continue
        e["sector"] = row["sector"]
        e["identity"] = row["identity"]
        n += 1
    data["meta"].update(patch["meta_updates"])
    ENT.write_text(json.dumps(data, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"applied {n} enterprise patches; meta updated")

if __name__ == "__main__":
    main()
