#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_freshness.py —— 检查海洋数据新鲜度，过期则报警（不阻断采集）"""
import json, os, sys, datetime

def load(p):
    with open(p, encoding='utf-8') as f: return json.load(f)

def main():
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    today = datetime.date.today()
    warn = 0
    # 1) 企业名录
    try:
        meta = load(os.path.join(base, 'data.json')).get('metadata', {})
        lu = meta.get('lastUpdated')
        d = datetime.date.fromisoformat(lu)
        days = (today - d).days
        flag = '⚠ 过期' if days > 90 else ('· 偏旧' if days > 30 else '✓')
        print(f'[企业名录] lastUpdated={lu} 距今 {days} 天 {flag}')
        if days > 90: warn += 1
    except Exception as e:
        print('[企业名录] 读取失败:', e); warn += 1
    # 2) 情报
    try:
        act = load(os.path.join(base, 'activity.json'))
        items = act if isinstance(act, list) else (act.get('items') or act.get('records') or [])
        dates = []
        for x in items:
            v = x.get('date') or x.get('time') or x.get('published_at') or x.get('created_at')
            if v: dates.append(str(v)[:10])
        def parse_d(v):
            v = str(v).strip()
            for fmt in ('%Y-%m-%d', '%Y-%m-%d %H:%M', '%Y/%m/%d', '%m-%d %H:%M', '%m-%d'):
                try:
                    dt = datetime.datetime.strptime(v, fmt)
                    if fmt.startswith('%m'):
                        dt = dt.replace(year=today.year)
                    return dt.date()
                except Exception:
                    continue
            return None
        parsed = [parse_d(v) for v in dates]
        parsed = [x for x in parsed if x]
        if parsed:
            latest = max(parsed); days = (today - latest).days
            flag = '⚠ 过期' if days > 7 else '✓'
            print(f'[情报流] 最新={latest} 距今 {days} 天 {flag}（共 {len(items)} 条）')
            if days > 7: warn += 1
        else:
            print(f'[情报流] 共 {len(items)} 条，但未找到日期字段')
    except Exception as e:
        print('[情报流] 读取失败:', e); warn += 1
    # 3) 政策清单
    try:
        dg = load(os.path.join(base, 'policy-digest-2026-10.json'))
        print(f"[政策清单] {len(dg['items'])} 条，窗口 {dg['window']}")
    except Exception as e:
        print('[政策清单] 缺失:', e)
    print('---')
    print('结论：' + ('⚠ 有 %d 项需要复核' % warn if warn else '✓ 数据新鲜'))
    return 0  # 不阻断采集

if __name__ == '__main__':
    sys.exit(main())
