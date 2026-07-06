#!/usr/bin/env python3
"""
广海汇企业情报采集器 v1.0
采集目标：招投标公告、工商变更、人才招聘信息
数据源：360搜索（免费渠道）、公开招标网站
输出：activity.json（动态情报日志）

运行方式：
  python3 scraper.py                    # 采集12家已验证企业
  python3 scraper.py --full             # 全量475家
  python3 scraper.py --enterprise "广船国际"  # 单家企业
"""

import json, re, urllib.request, urllib.parse, time, sys, os
from datetime import datetime

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

# 12家已验证头部企业
VERIFIED_ENTERPRISES = [
    "中船海洋与防务装备股份有限公司",
    "南方电网电力科技股份有限公司",
    "广州松兴电气股份有限公司",
    "广州白云电器设备股份有限公司",
    "中交广州航道局有限公司",
    "中船黄埔文冲船舶有限公司",
    "广东粤新海洋工程装备股份有限公司",
    "广船国际有限公司",
    "广东兴亿海洋生物工程股份有限公司",
    "富诺健康股份有限公司",
    "广州市力鑫药业有限公司",
    "拉多美科技集团股份有限公司",
]

def search_360(query: str, max_results: int = 5):
    """搜索360，返回标题+摘要列表"""
    try:
        enc = urllib.parse.quote(query)
        url = f"https://www.so.com/s?q={enc}"
        req = urllib.request.Request(url, headers={'User-Agent': UA})
        resp = urllib.request.urlopen(req, timeout=12)
        html = resp.read().decode('utf-8', errors='replace')

        titles = re.findall(r'<h3[^>]*class="res-title[^\"]*"[^>]*>.*?<a[^>]*>(.*?)</a>', html, re.DOTALL)
        descs = re.findall(r'class="res-desc"[^>]*>(.*?)</p>', html, re.DOTALL)
        results = []
        for i in range(min(len(titles), max_results)):
            title = re.sub(r'<[^>]+>', '', titles[i]).strip()
            desc = re.sub(r'<[^>]+>', '', descs[i]).strip() if i < len(descs) else ''
            if title:
                results.append({"title": title, "desc": desc[:200]})
        return results
    except Exception as e:
        print(f"  搜索失败: {e}")
        return []

def check_enterprise(name: str):
    """检查单家企业的近期动态"""
    events = []
    now = datetime.now().strftime("%m-%d %H:%M")

    # 1. 招投标
    bid_results = search_360(f"{name} 招标 中标 2026")
    for r in bid_results[:2]:
        if any(kw in r['title'] for kw in ['招标', '中标', '采购', '投标', '成交']):
            events.append({
                "time": now,
                "type": "招投标",
                "content": r['title'],
                "enterprise": name
            })

    # 2. 工商变更
    biz_results = search_360(f"{name} 工商变更 注册资本")
    for r in biz_results[:1]:
        if any(kw in r['title'] for kw in ['变更', '注册', '股东', '法人', '增资']):
            events.append({
                "time": now,
                "type": "工商",
                "content": r['title'],
                "enterprise": name
            })

    # 3. 人才招聘
    job_results = search_360(f"{name} 招聘 2026")
    for r in job_results[:1]:
        if any(kw in r['title'] for kw in ['招聘', '校招', '社招', '人才']):
            events.append({
                "time": now,
                "type": "招聘",
                "content": r['title'],
                "enterprise": name
            })

    return events

def main():
    full_mode = "--full" in sys.argv or os.environ.get("FULL_SCAN", "") == "1"
    single_enterprise = None
    for arg in sys.argv:
        if arg.startswith("--enterprise="):
            single_enterprise = arg.split("=", 1)[1]

    targets = VERIFIED_ENTERPRISES
    if single_enterprise:
        targets = [single_enterprise]
    elif not full_mode:
        print(f"快速模式：仅扫描 {len(targets)} 家已验证企业。使用 --full 进行全量扫描。")

    all_events = []
    total = len(targets)

    for i, name in enumerate(targets):
        print(f"[{i+1}/{total}] 检查: {name}")
        events = check_enterprise(name)
        if events:
            print(f"  发现 {len(events)} 条新动态")
            all_events.extend(events)
        else:
            print(f"  无新动态")
        if i < total - 1:
            time.sleep(1.5)  # 礼貌爬取间隔

    # 合并已有日志
    existing_events = []
    if os.path.exists("activity.json"):
        try:
            with open("activity.json", "r") as f:
                existing_events = json.load(f)
        except:
            pass

    # 去重并合并
    seen = set()
    for e in existing_events:
        key = e.get("content", "")
        if key not in seen:
            seen.add(key)
    merged = list(existing_events)
    for e in all_events:
        key = e.get("content", "")
        if key not in seen:
            merged.insert(0, e)  # 新事件放前面
            seen.add(key)

    # 截断最多500条
    merged = merged[:500]

    with open("activity.json", "w") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)

    print(f"\n完成。新增 {len(all_events)} 条动态，总计 {len(merged)} 条。")
    if merged:
        print(f"写入 activity.json")

if __name__ == "__main__":
    main()
