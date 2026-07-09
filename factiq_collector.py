#!/usr/bin/env python3
"""FactIQ → 涉海经济监测指标 · 每周自动采集"""
import asyncio, httpx, json, os
from collections import defaultdict
from datetime import datetime, timezone
from mcp.client.streamable_http import streamablehttp_client
from mcp.client.session import ClientSession

TOKEN = 'fiq_LwVaBPEOONXIOZrNO6qvJSJ4ntOR-3k8Da2hD2Z6WZU'
FACTIQ_URL = 'https://api.factiq.com/mcp'
OUTPUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'factiq_marine_indicators.json')

async def call(tool, args):
    def factory(**kw):
        return httpx.AsyncClient(verify=False, **kw)
    headers = {'Authorization': f'Bearer {TOKEN}'}
    async with streamablehttp_client(FACTIQ_URL, headers=headers, httpx_client_factory=factory) as (r, w, _):
        async with ClientSession(r, w) as s:
            await s.initialize()
            res = await s.call_tool(tool, args)
            for item in res.content:
                if hasattr(item, 'text'):
                    try: return json.loads(item.text)
                    except: return {"raw": item.text[:500]}
    return None

def trend(s):
    if len(s) < 4: return 'flat'
    r = sum(p['value'] for p in s[-2:])/2
    o = sum(p['value'] for p in s[-4:-2])/2
    if r > o*1.02: return 'up'
    if r < o*0.98: return 'down'
    return 'flat'

async def main():
    indicators = []

    # 1. 布伦特原油
    try:
        r = await call('get_market_data', {'function': 'TIME_SERIES_DAILY', 'symbol': 'Brent'})
        if r and 'results' in r:
            monthly = defaultdict(list)
            for p in r['results']:
                monthly[p[0][:7]].append(float(p[4]))
            series = [{'date': m, 'value': round(sum(monthly[m])/len(monthly[m]), 2)} 
                      for m in sorted(monthly.keys())[-12:]]
            indicators.append({
                'name': '布伦特原油', 'unit': '美元/桶', 'latest': series[-1]['value'],
                'trend': trend(series), 'series': series, 'source': 'Market Data via FactIQ'
            })
            print(f"✅ 布伦特: {len(series)}个月, ${series[-1]['value']}")
    except Exception as e:
        print(f"❌ 布伦特: {e}")

    # 2. IMF 中国GDP增速
    try:
        r = await call('get_series', {'schema': 'imf', 'series_id': 'NGDP_RPCH_CHN'})
        if r and 'results' in r:
            series = [{'date': p[0][:4], 'value': p[1]} for p in r['results']]
            indicators.append({
                'name': '中国GDP增速(IMF预测)', 'unit': '%', 'latest': series[-1]['value'],
                'trend': trend(series), 'series': series, 'source': 'IMF WEO via FactIQ'
            })
            print(f"✅ IMF GDP: {series[-1]['value']}% (2026)")
    except Exception as e:
        print(f"❌ IMF: {e}")

    # 3. 中国海关出口(标记：SQL超时)
    indicators.append({
        'name': '中国出口总值', 'unit': '亿美元', 'latest': None,
        'trend': 'flat', 'series': [], 'source': '中国海关总署 via FactIQ',
        'note': 'FactIQ海关数据按HS6位码存储，SQL聚合超时(286万行)。需联系FactIQ申请预聚合视图或改用World Bank NY.GDP.MKTP.KD.ZG替代。'
    })

    result = {
        'fetchTime': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'indicators': indicators
    }
    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    with open(OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"📁 {OUTPUT} ({len(indicators)} indicators)")

asyncio.run(main())
