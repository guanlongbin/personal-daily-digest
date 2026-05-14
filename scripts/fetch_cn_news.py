# /// script
# requires-python = ">=3.9"
# dependencies = [
#     "feedparser",
#     "requests",
# ]
# ///

"""
抓取国内新闻源：新华社、人民日报、央视新闻、澎湃新闻、
筛选：国内政经动态 + 和科技/互联网相关的政策动向
"""

import json
import sys
import argparse
from datetime import datetime
import feedparser

CN_NEWS_FEEDS = [
    {
        "name": "新华社",
        "url": "http://www.xinhuanet.com/politics/news_politics.xml",
        "priority": "high",
    },
    {
        "name": "GlobalTimes",
        "url": "https://www.globaltimes.cn/rss/outbrain.xml",
        "priority": "high",
    },
    {
        "name": "China Daily",
        "url": "https://www.chinadaily.com.cn/rss/cndy_rss.xml",
        "priority": "high",
    },
    {
        "name": "IT之家",
        "url": "https://www.ithome.com/rss/",
        "priority": "high",
    },
    {
        "name": "量子位",
        "url": "https://www.qbitai.com/feed",
        "priority": "high",
    },
    {
        "name": "InfoQ中文",
        "url": "https://www.infoq.cn/feed",
        "priority": "medium",
    },
    {
        "name": "少数派",
        "url": "https://sspai.com/feed",
        "priority": "medium",
    },
    {
        "name": "36Kr",
        "url": "https://36kr.com/feed",
        "priority": "medium",
    },
]

# 科技相关关键词（用于提升权重）
TECH_KEYWORDS = [
    "人工智能", "AI", "大模型", "数字经济", "互联网", "科技",
    "数据", "算法", "平台", "监管", "政策", "5G", "芯片",
    "半导体", "新能源", "智能", "数字化", "网络安全",
    "信息化", "创新", "产业", "经济", "发展",
]


def score_news(title: str, summary: str) -> int:
    text = title + " " + summary
    score = 0
    for kw in TECH_KEYWORDS:
        if kw in text:
            score += 1
    return score


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-per-feed", type=int, default=30)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    all_items = []
    errors = []

    for feed_cfg in CN_NEWS_FEEDS:
        urls_to_try = [feed_cfg["url"]]
        if "fallback" in feed_cfg:
            urls_to_try.append(feed_cfg["fallback"])

        success = False
        for url in urls_to_try:
            try:
                parsed = feedparser.parse(url)
                if not parsed.entries:
                    continue

                count = 0
                for entry in parsed.entries:
                    if count >= args.max_per_feed:
                        break

                    title = entry.get("title", "").strip()
                    summary = ""
                    if hasattr(entry, "summary"):
                        summary = entry.summary[:500]
                    link = entry.get("link", "")
                    published = entry.get("published", entry.get("updated", ""))

                    score = score_news(title, summary)

                    all_items.append({
                        "title": title,
                        "url": link,
                        "source": "cn_news",
                        "feed_name": feed_cfg["name"],
                        "priority": feed_cfg.get("priority", "medium"),
                        "publish_time": published,
                        "content": summary,
                        "score": score,
                        "dedup_key": f"cn_news:{link}",
                    })
                    count += 1
                success = True
                break
            except Exception as e:
                errors.append({"feed": feed_cfg["name"], "url": url, "error": str(e)})

        if not success and not any(e["feed"] == feed_cfg["name"] for e in errors):
            errors.append({"feed": feed_cfg["name"], "error": "All URLs failed"})

    # 按 score 排序
    all_items.sort(key=lambda x: x["score"], reverse=True)

    result = {
        "items": all_items,
        "errors": errors,
        "meta": {
            "total_items": len(all_items),
            "fetched_at": datetime.utcnow().isoformat() + "Z",
        }
    }

    out = json.dumps(result, ensure_ascii=False)
    if args.output:
        import os
        os.makedirs(os.path.dirname(args.output) if os.path.dirname(args.output) else ".", exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(out)
        print(f"国内新闻已保存到 {args.output}，共 {len(all_items)} 条")
    else:
        print(out)


if __name__ == "__main__":
    main()
