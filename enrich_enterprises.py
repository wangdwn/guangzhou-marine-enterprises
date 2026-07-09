#!/usr/bin/env python3
"""企业数据增强 —— 产业链标签回填（每月/首次运行）"""
import json, os, re, sys
from urllib.request import Request, urlopen

DATA_URL = "https://raw.githubusercontent.com/wangdwn/guangzhou-marine-enterprises/master/data.json"
OUTPUT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.json")

CHAIN_RULES = [
    ("研发设计", r"设计|研发|技术开发|研究院|科研|实验|检测"),
    ("装备制造", r"制造|生产|建造|加工|组装|锻造|铸造|模具|制"),
    ("工程建设", r"施工|安装|工程|建设|勘测|勘探|测绘|打捞"),
    ("运营服务", r"运维|服务|检测|保养|管理|维护|维修|咨询|评估"),
    ("贸易物流", r"物流|运输|仓储|货代|报关|贸易|进出口|船舶|航运|港口|码头"),
]

def tag_chain(main_biz):
    if not main_biz:
        return ["其他"]
    tags = [tag for tag, pat in CHAIN_RULES if re.search(pat, main_biz)]
    return tags if tags else ["其他"]

def main():
    # Load existing data
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, 'r') as f:
            raw = json.load(f)
    else:
        req = Request(DATA_URL, headers={"User-Agent": "GitHub Actions"})
        with urlopen(req, timeout=30) as f:
            raw = json.loads(f.read().decode('utf-8'))
    
    enterprises = raw.get("enterprises", [])
    tag_added = 0
    
    for e in enterprises:
        if "chain" not in e:
            tags = tag_chain(e.get("main_biz", ""))
            e["chain"] = tags
            e["chain_primary"] = tags[0]
            tag_added += 1
    
    raw["metadata"]["enrichedAt"] = "2026-07-09"
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(raw, f, ensure_ascii=False, indent=2)
    
    print(f"Tagged: {tag_added} new / {len(enterprises)} total")
    print(f"Output: {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
