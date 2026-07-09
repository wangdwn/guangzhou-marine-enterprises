#!/usr/bin/env python3
"""周度海洋经济情报采集 —— 博查搜索舆情 + 企业动态"""
import json, os, sys, re
from datetime import datetime, timedelta
from urllib.request import Request, urlopen

BOCHA_KEY = os.environ.get("BOCHA_API_KEY", "sk-9b59f18ea1d64d74bf4700c689c89a35")
BOCHA_URL = "https://api.bochaai.com/v1/web-search"
DATA_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE = os.path.join(DATA_DIR, "activity.json")

# 搜索关键词
QUERIES = [
    "广州 海洋经济 政策 2026",
    "广州 海洋工程装备 船舶 制造",
    "广州 海洋生物医药",
    "南沙 港口 航运 集装箱",
    "广东 海洋经济 投资 项目",
    "广州 涉海企业 招聘 人才",
]

def search_bocha(query, count=8):
    """调用博查搜索"""
    payload = json.dumps({"query": query, "count": count}).encode("utf-8")
    req = Request(BOCHA_URL, data=payload, headers={
        "Authorization": f"Bearer {BOCHA_KEY}",
        "Content-Type": "application/json"
    })
    try:
        with urlopen(req, timeout=15) as f:
            data = json.loads(f.read().decode("utf-8"))
        return data.get("data", {}).get("webPages", {}).get("value", [])
    except Exception as e:
        print(f"  Search error [{query[:30]}]: {e}")
        return []

def classify_sentiment(title, snippet):
    """简单情感分类"""
    positive = re.findall(r"增长|突破|领先|创新|落地|签约|投产|利好|加速", title + snippet)
    negative = re.findall(r"下滑|亏损|裁员|风险|违规|处罚|倒闭|衰退", title + snippet)
    if len(positive) > len(negative):
        return "positive"
    elif len(negative) > len(positive):
        return "negative"
    return "neutral"

def main():
    today = datetime.now().strftime("%Y-%m-%d")
    week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    
    results = {
        "collected_at": today,
        "period": f"{week_ago} ~ {today}",
        "queries": {},
        "sentiment_summary": {"positive": 0, "negative": 0, "neutral": 0},
        "signals": []
    }
    
    all_articles = []
    for q in QUERIES:
        print(f"Searching: {q}")
        items = search_bocha(q)
        results["queries"][q] = len(items)
        
        for item in items:
            sentiment = classify_sentiment(
                item.get("name", ""),
                item.get("snippet", "")
            )
            results["sentiment_summary"][sentiment] += 1
            
            article = {
                "title": item.get("name", ""),
                "url": item.get("url", ""),
                "snippet": item.get("snippet", "")[:200],
                "date": item.get("datePublished", ""),
                "source": item.get("siteName", ""),
                "sentiment": sentiment,
                "query": q
            }
            all_articles.append(article)
    
    # Extract key signals (articles with strong sentiment)
    signals = [a for a in all_articles if a["sentiment"] != "neutral"][:15]
    results["signals"] = signals
    results["total_articles"] = len(all_articles)
    
    # Load existing activity data and append
    existing = {"history": []}
    if os.path.exists(OUTPUT_FILE):
        try:
            with open(OUTPUT_FILE, "r") as f:
                existing = json.load(f)
        except:
            pass
    
    # Keep last 12 weeks
    existing["history"].append(results)
    existing["history"] = existing["history"][-12:]
    existing["last_updated"] = today
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)
    
    print(f"\nTotal articles: {len(all_articles)}")
    print(f"Sentiment: +{results['sentiment_summary']['positive']} / -{results['sentiment_summary']['negative']} / ~{results['sentiment_summary']['neutral']}")
    print(f"Signals: {len(signals)}")
    print(f"Output: {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
