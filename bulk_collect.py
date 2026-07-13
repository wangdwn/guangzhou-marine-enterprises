#!/usr/bin/env python3
"""全量企业情报补采 —— 批量搜索672家企业，补全缺失情报"""
import json, subprocess, re, time, os, sys
from datetime import datetime
from html import unescape
from collections import Counter

DATA_FILE = os.path.join(os.path.dirname(__file__), "data.json")
ACTIVITY_FILE = os.path.join(os.path.dirname(__file__), "activity.json")

# 并行度
BATCH_SIZE = 5       # 每批同时搜5家
GAP_SEC = 0.3        # 批间隔

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def search_360(query):
    """360搜索单条查询"""
    import urllib.parse
    encoded = urllib.parse.quote(query)
    url = f"https://www.so.com/s?q={encoded}"
    try:
        p = subprocess.run(
            ["curl", "-sL", "--max-time", "10",
             "-H", f"User-Agent: {USER_AGENT}",
             url],
            capture_output=True, text=True, timeout=12
        )
        return p.stdout
    except:
        return ""

def extract_titles(html):
    titles = []
    noise = {'其他人还搜了', '下一页', '上一页', '相关搜索', '为您推荐', '360搜索', '搜索一下', '猜你感兴趣'}
    patterns = [
        r'<h3[^>]*class="[^"]*res-title[^"]*"[^>]*>(.*?)</h3>',
        r'<h3[^>]*class="[^"]*title[^"]*"[^>]*>(.*?)</h3>',
        r'class="res-title"[^>]*>\s*<a[^>]*>(.*?)</a>',
        r'<a[^>]*data-url[^>]*>(.*?)</a>',
    ]
    for pat in patterns:
        matches = re.findall(pat, html, re.DOTALL | re.IGNORECASE)
        for m in matches:
            clean = re.sub(r'<[^>]+>', '', m).strip()
            clean = unescape(clean)
            clean = re.sub(r'\s+', ' ', clean)
            if clean and len(clean) > 4 and clean not in titles and clean not in noise:
                titles.append(clean)
    return titles[:5]  # 每个搜索最多取5条，减少垃圾

def search_enterprise(name, sector):
    """搜索一家企业的情报：3个关键词"""
    queries = [
        f"{name} {'招标' if '工程' in sector or '建设' in sector or '装备' in sector else '中标' } 2026",
        f"{name} 招聘",
        f"{name} {'工商变更' if len(name) < 10 else '最新动态'}",
    ]
    cat_map = {
        queries[0]: "招投标",
        queries[1]: "人才招聘",
        queries[2]: "工商变更",
    }
    
    results = []
    for q, cat in cat_map.items():
        html = search_360(q)
        titles = extract_titles(html)
        # 过滤掉不相关的（不含企业关键词的标题）
        name_parts = set(name.replace('(', ' ').replace(')', ' ').replace('（', ' ').replace('）', ' ').split())
        for t in titles:
            # 标题必须包含企业名中的至少一个字（不能完全不相关）
            if any(p in t for p in name_parts):
                results.append({
                    "type": cat,
                    "content": t,
                    "enterprise": name,
                    "source": "360搜索"
                })
        time.sleep(0.2)  # 单关键词间隔
    return results

def main():
    data = load_json(DATA_FILE)
    enterprises = data["enterprises"]
    total = len(enterprises)
    
    # 加载现有activity
    existing = []
    seen_keys = set()
    if os.path.exists(ACTIVITY_FILE):
        existing = load_json(ACTIVITY_FILE)
        for item in existing:
            k = (item.get("enterprise", ""), item.get("content", ""), item.get("type", ""))
            seen_keys.add(k)
    
    log(f"===== 全量企业情报补采 =====")
    log(f"企业总数: {total}")
    log(f"已有情报: {len(existing)} 条, {len(seen_keys)} 个唯一")
    
    # 统计已有覆盖的企业
    covered_ents = set()
    for item in existing:
        if item.get("enterprise"):
            covered_ents.add(item["enterprise"])
    log(f"已有情报的企业: {len(covered_ents)} 家")
    log(f"缺失情报的企业: {total - len(covered_ents)} 家")
    
    # 按批次扫描所有企业
    new_total = 0
    scanned = 0
    t_start = time.time()
    now = datetime.now().strftime("%m-%d %H:%M")
    
    for i in range(0, total, BATCH_SIZE):
        batch = enterprises[i:i+BATCH_SIZE]
        batch_new = 0
        
        for ent in batch:
            name = ent["name"]
            sector = ent.get("sector_raw", ent.get("sector", ""))
            
            # 跳过已有情报的企业（只补缺）
            if name in covered_ents:
                scanned += 1
                continue
            
            items = search_enterprise(name, sector)
            time_str = now if not items else now
            
            for it in items:
                key = (name, it["content"], it["type"])
                if key not in seen_keys:
                    it["time"] = time_str
                    existing.append(it)
                    seen_keys.add(key)
                    batch_new += 1
                    new_total += 1
            
            scanned += 1
            if batch_new > 0:
                log(f"  [{scanned}/{total}] {name}: +{batch_new}条")
            
            # 批间等待
            time.sleep(GAP_SEC)
        
        # 每批次保存一次，防止断点丢数据
        if batch_new > 0:
            save_json(ACTIVITY_FILE, existing)
        
        # 进度报告
        if (i // BATCH_SIZE) % 10 == 0 and i > 0:
            elapsed = time.time() - t_start
            rate = scanned / elapsed if elapsed > 0 else 0
            log(f"进度: {scanned}/{total} ({int(scanned/total*100)}%), +{new_total}条, {rate:.1f}企/秒")
    
    elapsed = time.time() - t_start
    final_covered = set()
    for item in existing:
        if item.get("enterprise"):
            final_covered.add(item["enterprise"])
    
    log(f"\n===== 补采完成 =====")
    log(f"耗时: {elapsed:.1f}s ({elapsed/60:.1f}分钟)")
    log(f"总情报: {len(existing)} 条")
    log(f"覆盖企业: {len(final_covered)}/{total} 家")
    log(f"新增: {new_total} 条")
    
    # 输出覆盖统计
    remain = total - len(final_covered)
    log(f"仍有 {remain} 家企业无情报")
    
    # 保存
    save_json(ACTIVITY_FILE, existing)
    log(f"已保存到: {ACTIVITY_FILE}")
    
    return new_total

if __name__ == "__main__":
    new = main()
    sys.exit(0)
