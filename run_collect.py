#!/usr/bin/env python3
"""企业情报采集 —— 并行curl，1.5s企业间隔"""
import json, subprocess, re, time, os, sys
from datetime import datetime
from html import unescape

REPO_DIR = "/Users/macos13/guangzhou-marine-enterprises"
DATA_FILE = os.path.join(REPO_DIR, "data.json")
ACTIVITY_FILE = os.path.join(REPO_DIR, "activity.json")
BATCH_SIZE = 100
GAP_SEC = 1.5

def log(msg):
    print(msg, flush=True)

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def curl_search_parallel(queries):
    """并行执行多个curl查询，返回 {query: html}"""
    import urllib.parse
    procs = {}
    for query in queries:
        encoded = urllib.parse.quote(query)
        url = f"https://www.so.com/s?q={encoded}"
        p = subprocess.Popen(
            ["curl", "-sL", "--max-time", "10",
             "-H", "User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
             url],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True
        )
        procs[query] = p

    results = {}
    for query, p in procs.items():
        try:
            out, _ = p.communicate(timeout=12)
            results[query] = out
        except:
            p.kill()
            results[query] = ""
    return results

def extract_titles(html):
    titles = []
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
            if clean and len(clean) > 4 and clean not in titles:
                titles.append(clean)
    return titles[:8]

def load_existing_activity():
    if os.path.exists(ACTIVITY_FILE):
        data = load_json(ACTIVITY_FILE)
        keys = set()
        for item in data:
            k = (item.get("enterprise", ""), item.get("content", ""), item.get("type", ""))
            keys.add(k)
        return data, keys
    return [], set()

def main():
    data = load_json(DATA_FILE)
    enterprises = data["enterprises"]
    total = len(enterprises)

    now = datetime.now()
    day_of_year = now.timetuple().tm_yday
    num_batches = (total + BATCH_SIZE - 1) // BATCH_SIZE
    batch_idx = day_of_year % num_batches
    start = batch_idx * BATCH_SIZE
    end = min(start + BATCH_SIZE, total)
    batch = enterprises[start:end]

    log(f"=== 企业情报采集 ===")
    log(f"日期: {now.strftime('%Y-%m-%d')} (day {day_of_year})")
    log(f"批次: {batch_idx+1}/{num_batches}, 企业 {start+1}-{end} ({len(batch)}家)")
    log(f"首企: {batch[0]['name']} | 尾企: {batch[-1]['name']}")

    existing, seen_keys = load_existing_activity()
    log(f"现有活动记录: {len(existing)} 条")

    new_entries = []
    scanned = 0
    time_str = now.strftime("%m-%d %H:%M")
    t_start = time.time()

    for i, ent in enumerate(batch):
        name = ent["name"]

        queries = [
            f"{name} 招标 中标 2026",
            f"{name} 工商变更 注册资本",
            f"{name} 招聘 2026",
        ]
        cat_map = {queries[0]: "招投标", queries[1]: "工商变更", queries[2]: "人才招聘"}

        # 并行执行3个curl
        html_map = curl_search_parallel(queries)

        found_any = False
        for query, html in html_map.items():
            cat = cat_map[query]
            titles = extract_titles(html)
            for t in titles:
                key = (name, t, cat)
                if key not in seen_keys:
                    entry = {
                        "time": time_str,
                        "type": cat,
                        "content": t,
                        "enterprise": name,
                        "source": "360搜索"
                    }
                    new_entries.append(entry)
                    seen_keys.add(key)
                    found_any = True

        if found_any:
            count = sum(1 for e in new_entries if e['enterprise'] == name)
            log(f"  [{i+1}/{len(batch)}] {name}: +{count}条")
        elif (i+1) % 20 == 0:
            log(f"  [{i+1}/{len(batch)}] ...")

        scanned += 1
        if i < len(batch) - 1:
            time.sleep(GAP_SEC)

    elapsed = time.time() - t_start

    if new_entries:
        existing.extend(new_entries)
        save_json(ACTIVITY_FILE, existing)
        log(f"\n新增 {len(new_entries)} 条情报，总计 {len(existing)} 条")
    else:
        log(f"\n无新增情报")

    log(f"耗时: {elapsed:.1f}s | SCANNED:{scanned} | NEW_COUNT:{len(new_entries)}")

    status = {
        "date": now.strftime("%Y-%m-%d"),
        "day_of_year": day_of_year,
        "batch": batch_idx,
        "scanned": scanned,
        "new_count": len(new_entries),
        "total_activity": len(existing),
        "first_enterprise": batch[0]["name"],
        "last_enterprise": batch[-1]["name"],
    }
    save_json(os.path.join(REPO_DIR, "last_run.json"), status)

    return len(new_entries)

if __name__ == "__main__":
    new_cnt = main()
    sys.exit(0)
