#!/usr/bin/env python3
"""历史数据回填 —— 生成最近4个季度的activity.json模板"""
import json, os
from datetime import datetime, timedelta

OUTPUT = "/tmp/activity-backfill.json"

# 4 quarters: 2025-Q3, 2025-Q4, 2026-Q1, 2026-Q2
quarters = [
    {"id": "2025-Q3", "period": "2025-07-01 ~ 2025-09-30", "collected_at": "2025-09-30"},
    {"id": "2025-Q4", "period": "2025-10-01 ~ 2025-12-31", "collected_at": "2025-12-31"},
    {"id": "2026-Q1", "period": "2026-01-01 ~ 2026-03-31", "collected_at": "2026-03-31"},
    {"id": "2026-Q2", "period": "2026-04-01 ~ 2026-06-30", "collected_at": "2026-06-30"},
]

# Template for each quarter
history = []
for q in quarters:
    entry = {
        "collected_at": q["collected_at"],
        "period": q["period"],
        "quarter": q["id"],
        "queries": {
            "广州 海洋经济 政策": 0,
            "广州 海洋工程装备 船舶 制造": 0,
            "广州 海洋生物医药": 0,
            "南沙 港口 航运 集装箱": 0,
            "广东 海洋经济 投资 项目": 0,
            "广州 涉海企业 招聘 人才": 0
        },
        "sentiment_summary": {"positive": 0, "negative": 0, "neutral": 0},
        "signals": [],
        "total_articles": 0,
        "indicators": {
            "enterprise_registration": {"value": 0, "unit": "家", "source": "市场监管局月度数据"},
            "marine_equipment_output": {"value": 0, "unit": "亿元", "source": "统计年鉴"},
            "recruitment_count": {"value": 0, "unit": "岗位", "source": "招聘网站抓取"},
            "bidding_projects": {"value": 0, "unit": "个", "source": "政府采购网"},
            "sentiment_index": {"value": 0, "unit": "正面率%", "source": "博查搜索舆情"}
        },
        "note": f"历史数据模板——待回填真实数据。数据源：市场监管局/统计年鉴/招聘网站/政府采购网/博查搜索。"
    }
    history.append(entry)

# Load current activity.json if exists
current = {}
if os.path.exists("/tmp/activity.json"):
    with open("/tmp/activity.json") as f:
        current = json.load(f)

# Merge: put historical quarters first, then existing history
existing_history = current.get("history", [])
merged = history + existing_history

result = {
    "history": merged,
    "last_updated": datetime.now().strftime("%Y-%m-%d"),
    "quarterly_indicators": {
        "description": "季度经济指标追踪。首次建库回填4个季度，后续每季度自动追加。",
        "fields": {
            "enterprise_registration": "涉海企业新增注册数（来源：市场监管局）",
            "marine_equipment_output": "海工装备类企业产值（来源：统计年鉴，需人工维护）",
            "recruitment_count": "涉海岗位招聘合计（来源：招聘网站抓取）",
            "bidding_projects": "新增中标项目数量（来源：公共资源交易中心）",
            "sentiment_index": "舆情正面率（来源：博查搜索，每周采集）"
        }
    }
}

with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)

print(f"Backfill: {len(merged)} entries ({len(history)} template + {len(existing_history)} real)")
print(f"Written: {OUTPUT} ({os.path.getsize(OUTPUT)} bytes)")
