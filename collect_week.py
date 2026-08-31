#!/usr/bin/env python3
"""广海汇周度情报采集 —— 轮换批次扫描，追加到 activity.json"""
import json, subprocess, re, time, os, sys, urllib.parse
from datetime import datetime
from html import unescape

BASE = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE, "data.json")
ACTIVITY_FILE = os.path.join(BASE, "activity.json")

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
GAP_SEC = 1.2
MAX_CONTENT = 90  # 截断长标题

NOISE = {
    '其他人还搜了', '下一页', '上一页', '相关搜索', '为您推荐', '360搜索', '搜索一下',
    '猜你感兴趣', '相关企业反馈', '猜您关注反馈', '相关公司反馈', '相关机构反馈',
    '换一换', '相关企业', '相关公司', '相关机构', '猜您关注', '更多结果', '展开',
}
GENERIC_PARTS = {'广州', '广东', '集团', '股份', '有限', '公司', '中国', '科技', '国际', '海洋', '船舶', '工程', '检测', '技术', '智能', '控股'}

def load_json(p):
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(p, d):
    with open(p, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)

def curl_parallel(queries):
    procs = {}
    for q in queries:
        url = f"https://www.so.com/s?q={urllib.parse.quote(q)}"
        procs[q] = subprocess.Popen(
            ["curl", "-sL", "--max-time", "10", "-H", f"User-Agent: {USER_AGENT}", url],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True
        )
    out = {}
    for q, p in procs.items():
        try:
            html, _ = p.communicate(timeout=13)
            out[q] = html
        except Exception:
            p.kill()
            out[q] = ""
    return out

def extract_titles(html):
    titles = []
    patterns = [
        r'<h3[^>]*class="[^"]*res-title[^"]*"[^>]*>(.*?)</h3>',
        r'<h3[^>]*class="[^"]*title[^"]*"[^>]*>(.*?)</h3>',
        r'class="res-title"[^>]*>\s*<a[^>]*>(.*?)</a>',
        r'<a[^>]*data-url[^>]*>(.*?)</a>',
    ]
    for pat in patterns:
        for m in re.findall(pat, html, re.DOTALL | re.IGNORECASE):
            c = re.sub(r'<[^>]+>', '', m).strip()
            c = unescape(c)
            c = re.sub(r'\s+', ' ', c).strip()
            if len(c) < 5:
                continue
            if c in NOISE or any(n in c for n in NOISE):
                continue
            # 排除纯导航噪声
            if re.fullmatch(r'[\d]+秒前更新.*', c):
                continue
            if c not in titles:
                titles.append(c)
    return titles[:8]

def name_keywords(name):
    """提取企业名中有意义的片段用于相关性过滤"""
    # 去掉括号内容、通用词
    n = re.sub(r'[（(].*?[)）]', ' ', name)
    parts = [p for p in re.split(r'[\s·\-]+', n) if p]
    kws = []
    for p in parts:
        # 去掉通用后缀后剩余的核心词
        core = re.sub(r'(股份|集团|有限|公司|有限公|责任|科技)+$', '', p)
        if core and len(core) >= 2 and core not in GENERIC_PARTS:
            kws.append(core)
    # 兜底：取企业名中去除通用词后的最长连续片段
    if not kws:
        core = name
        for g in sorted(GENERIC_PARTS, key=len, reverse=True):
            core = core.replace(g, '')
        core = core.strip('()（）')
        if core:
            kws.append(core)
    return kws

def main():
    data = load_json(DATA_FILE)
    ents = data["enterprises"]
    total = len(ents)

    now = datetime.now()
    # 轮换：上次 last_run batch=5，本次前进到 6（覆盖不同企业）
    batch_idx = 6
    start = batch_idx * 100
    end = min(start + 100, total)
    batch = ents[start:end]

    print(f"=== 广海汇周度采集 ===", flush=True)
    print(f"日期: {now.strftime('%Y-%m-%d %H:%M')}", flush=True)
    print(f"批次: {batch_idx+1}/7, 企业 {start+1}-{end} ({len(batch)}家)", flush=True)

    existing = load_json(ACTIVITY_FILE)
    seen = set()
    for it in existing:
        seen.add((it.get("enterprise", ""), it.get("content", ""), it.get("type", "")))

    new_entries = []
    time_str = now.strftime("%m-%d %H:%M")
    t0 = time.time()

    for i, ent in enumerate(batch):
        name = ent["name"]
        kws = name_keywords(name)
        queries = [
            f"{name} 招标 中标 2026",
            f"{name} 工商变更 注册资本",
            f"{name} 招聘 2026",
        ]
        cat_map = {queries[0]: "招投标", queries[1]: "工商变更", queries[2]: "人才招聘"}
        html_map = curl_parallel(queries)
        found = 0
        for q, html in html_map.items():
            cat = cat_map[q]
            for t in extract_titles(html):
                content = t if len(t) <= MAX_CONTENT else t[:MAX_CONTENT] + "..."
                # 相关性：标题需含企业名核心词
                if kws and not any(k in content for k in kws):
                    continue
                key = (name, content, cat)
                if key in seen:
                    continue
                seen.add(key)
                new_entries.append({
                    "time": time_str, "type": cat, "content": content,
                    "enterprise": name, "source": "360搜索"
                })
                found += 1
        if found:
            print(f"  [{i+1}/{len(batch)}] {name}: +{found}条", flush=True)
        elif (i+1) % 15 == 0:
            print(f"  [{i+1}/{len(batch)}] ...", flush=True)
        if i < len(batch) - 1:
            time.sleep(GAP_SEC)

    if new_entries:
        existing.extend(new_entries)
        save_json(ACTIVITY_FILE, existing)
        print(f"\n新增 {len(new_entries)} 条，总计 {len(existing)} 条", flush=True)
    else:
        print("\n无新增", flush=True)

    print(f"耗时 {time.time()-t0:.0f}s", flush=True)
    save_json(os.path.join(BASE, "last_run.json"), {
        "date": now.strftime("%Y-%m-%d"),
        "batch": batch_idx,
        "scanned": len(batch),
        "new_count": len(new_entries),
        "total_activity": len(existing),
        "first_enterprise": batch[0]["name"] if batch else "",
        "last_enterprise": batch[-1]["name"] if batch else "",
    })
    return len(new_entries)

if __name__ == "__main__":
    main()
