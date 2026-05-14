# /// script
# requires-python = ">=3.9"
# dependencies = [
#     "feedparser",
#     "requests",
#     "beautifulsoup4",
# ]
# ///

"""
抓取 arXiv 最新论文，筛选方向：
  - 推荐系统 / 生成式推荐 / 广告排序
  - 大模型 / LLM / 多模态
  - cs.IR / cs.LG / cs.AI / cs.CV
"""

import json
import sys
import re
import time
import argparse
from datetime import datetime, timedelta
import feedparser
import requests
from bs4 import BeautifulSoup

ARXIV_FEEDS = [
    {
        "name": "arXiv cs.IR (信息检索/推荐系统)",
        "url": "https://rss.arxiv.org/rss/cs.IR",
    },
    {
        "name": "arXiv cs.LG (机器学习)",
        "url": "https://rss.arxiv.org/rss/cs.LG",
    },
    {
        "name": "arXiv cs.AI (人工智能)",
        "url": "https://rss.arxiv.org/rss/cs.AI",
    },
    {
        "name": "arXiv cs.CV (计算机视觉/多模态)",
        "url": "https://rss.arxiv.org/rss/cs.CV",
    },
]

# ── 核心高优先级关键词（命中得 3 分）──
CORE_KEYWORDS = [
    "recommendation system", "recommender system", "recommender",
    "generative recommendation", "sequential recommendation",
    "session-based recommendation", "collaborative filtering",
    "click-through rate", "CTR", "CVR", "conversion rate",
    "ads ranking", "ad ranking", "sponsored search",
    "retrieval augmented generation", "RAG",
    "large language model", "LLM", "GPT-", "Claude", "Gemini",
    "foundation model", "pre-trained model",
    "RLHF", "reinforcement learning from human feedback",
    "alignment", "instruction tuning", "fine-tuning",
    "multimodal recommendation", "multi-modal recommendation",
    "knowledge graph recommendation",
    "user behavior", "user interest", "user preference",
    "cold start", "long-tail",
    "diffusion model for recommendation",
]

# 次级关键词（命中得 1 分）
SECONDARY_KEYWORDS = [
    "transformer", "attention mechanism", "self-attention",
    "multimodal", "multi-modal", "vision language",
    "in-context learning", "chain-of-thought",
    "knowledge distillation", "contrastive learning",
    "graph neural network", "GNN",
    "ranking", "learning to rank", "listwise",
    "search", "information retrieval",
    "diffusion model", "generative model",
    "agent", "tool use", "reasoning",
]

# 噪音关键词（命中直接 -5 分，防止无关论文混入）
NOISE_KEYWORDS = [
    "medical", "clinical", "healthcare", "drug",
    "protein", "genome", "biology", "pathology",
    "autonomous driving", "self-driving", "lidar",
    "speech recognition", "speaker diarization",
    "point cloud", "3d reconstruction", "nerf",
    "weather forecast", "climate", "satellite",
]

# 机构关键词（国内大厂/高校）
ORG_KEYWORDS = [
    "Kuaishou", "快手", "ByteDance", "字节", "Alibaba", "阿里",
    "Tencent", "腾讯", "Baidu", "百度", "JD", "京东",
    "Huawei", "华为", "Xiaomi", "小米", "NetEase", "网易",
    "Tsinghua", "清华", "Peking", "北大", "Zhejiang", "浙大",
    "Fudan", "复旦", "SJTU", "交大", "RUC", "人大",
    "CAS", "中科院", "USTC", "中科大",
    "Google", "Meta", "OpenAI", "Microsoft", "DeepMind", "Anthropic",
    "Amazon", "Apple", "NVIDIA",
]


def fetch_affiliations(arxiv_url: str, timeout: int = 10) -> dict:
    """
    从 arxiv /html/ 页面提取作者和机构信息。
    返回 {"authors": [...], "affiliations": [...]}
    arxiv_url 格式：https://arxiv.org/abs/2605.xxxxx
    """
    try:
        # 把 abs URL 转成 html URL
        arxiv_id = arxiv_url.rstrip("/").split("/")[-1]
        html_url = f"https://arxiv.org/html/{arxiv_id}"
        resp = requests.get(html_url, timeout=timeout,
                            headers={"User-Agent": "Mozilla/5.0 (compatible; arxiv-digest-bot/1.0)"})
        if resp.status_code != 200:
            return {}

        soup = BeautifulSoup(resp.text, "html.parser")

        # 提取作者名
        authors = []
        author_tags = soup.select(".ltx_personname")
        for tag in author_tags[:8]:
            name = tag.get_text(strip=True)
            if name:
                authors.append(name)

        # 提取机构
        affiliations = []
        affil_tags = soup.select(".ltx_affiliation .ltx_text, .ltx_contact.ltx_role_affiliation")
        for tag in affil_tags:
            text = tag.get_text(strip=True)
            if text and len(text) > 3:
                affiliations.append(text)

        # 去重保序
        seen = set()
        unique_affils = []
        for a in affiliations:
            if a not in seen:
                seen.add(a)
                unique_affils.append(a)

        return {
            "authors": authors[:8],
            "affiliations": unique_affils[:5],
        }
    except Exception:
        return {}


def score_paper(title: str, summary: str) -> int:
    text = (title + " " + summary).lower()
    score = 0
    # 噪音直接砍分
    for kw in NOISE_KEYWORDS:
        if kw.lower() in text:
            score -= 5
    # 核心命中 +3
    for kw in CORE_KEYWORDS:
        if kw.lower() in text:
            score += 3
    # 次级命中 +1
    for kw in SECONDARY_KEYWORDS:
        if kw.lower() in text:
            score += 1
    # 机构加分 +1
    for org in ORG_KEYWORDS:
        if org.lower() in text:
            score += 1
    return score


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-per-feed", type=int, default=50)
    parser.add_argument("--min-score", type=int, default=3, help="最低分数阈值，低于此分数不输出")
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    all_papers = []
    errors = []

    for feed_cfg in ARXIV_FEEDS:
        try:
            parsed = feedparser.parse(feed_cfg["url"])
            count = 0
            for entry in parsed.entries:
                if count >= args.max_per_feed:
                    break

                title = entry.get("title", "").replace("\n", " ").strip()
                summary = entry.get("summary", "")[:800]
                link = entry.get("link", "")
                published = entry.get("published", "")

                score = score_paper(title, summary)
                if score < args.min_score:
                    count += 1
                    continue

                # 提取作者
                authors = []
                if hasattr(entry, "authors"):
                    authors = [a.get("name", "") for a in entry.authors[:5]]
                elif hasattr(entry, "author"):
                    authors = [entry.author]

                all_papers.append({
                    "title": title,
                    "url": link,
                    "source": "arxiv",
                    "feed_name": feed_cfg["name"],
                    "publish_time": published,
                    "content": summary,
                    "authors": authors,
                    "score": score,
                    "dedup_key": f"arxiv:{link}",
                })
                count += 1
        except Exception as e:
            errors.append({"feed": feed_cfg["name"], "error": str(e)})

    # 按分数排序，只取 Top 15 去补全机构（节省时间）
    all_papers.sort(key=lambda x: x["score"], reverse=True)
    top_papers = all_papers[:15]

    print(f"开始补全机构信息，共 {len(top_papers)} 篇，每篇间隔 2s...", file=sys.stderr)
    for i, paper in enumerate(top_papers):
        affil_data = fetch_affiliations(paper["url"])
        if affil_data.get("authors"):
            paper["authors"] = affil_data["authors"]
        if affil_data.get("affiliations"):
            paper["affiliations"] = affil_data["affiliations"]
        else:
            paper["affiliations"] = []
        if i < len(top_papers) - 1:
            time.sleep(2)

    result = {
        "items": top_papers,
        "errors": errors,
        "meta": {
            "total_papers": len(top_papers),
            "fetched_at": datetime.utcnow().isoformat() + "Z",
        }
    }

    out = json.dumps(result, ensure_ascii=False)
    if args.output:
        import os
        os.makedirs(os.path.dirname(args.output) if os.path.dirname(args.output) else ".", exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(out)
        print(f"arXiv 论文已保存到 {args.output}，共 {len(all_papers)} 篇")
    else:
        print(out)


if __name__ == "__main__":
    main()
