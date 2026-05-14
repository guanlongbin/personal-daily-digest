# /// script
# requires-python = ">=3.9"
# dependencies = [
#     "openai",
# ]
# ///

"""
生成 AI 每日快报：
  - 科技/AI 快讯 (rss_latest.json) — 保留
  - arXiv 论文 (arxiv_latest.json) — 中文摘要，取 top 15
  - 国内新闻 — 已移除

输出：
  - Markdown 日报文件（归档用）
  - KIM mixCard JSON 结构（供 message 工具发送）
"""

import json, os, sys, argparse, hashlib
from datetime import datetime


# ─── 增量去重：seen_ids ───────────────────────────────────────────────────────

SEEN_IDS_FILE = "daily-digest/cache/seen_ids.json"

def load_seen_ids() -> set:
    if os.path.exists(SEEN_IDS_FILE):
        with open(SEEN_IDS_FILE, encoding="utf-8") as f:
            data = json.load(f)
        return set(data.get("ids", []))
    return set()

def save_seen_ids(seen: set):
    os.makedirs(os.path.dirname(SEEN_IDS_FILE), exist_ok=True)
    # 只保留最近 5000 条，防止文件无限膨胀
    ids_list = list(seen)[-5000:]
    with open(SEEN_IDS_FILE, "w", encoding="utf-8") as f:
        json.dump({"ids": ids_list, "updated": datetime.now().isoformat()}, f, ensure_ascii=False)

def make_id(item: dict) -> str:
    """用 dedup_key 或 url+title 的 hash 作为唯一 ID"""
    key = item.get("dedup_key") or item.get("url") or item.get("title", "")
    return hashlib.md5(key.encode("utf-8")).hexdigest()

def deduplicate(items: list, seen: set) -> tuple[list, set]:
    """过滤已推送过的 item，返回新条目和更新后的 seen"""
    new_items = []
    new_ids = set()
    for item in items:
        uid = make_id(item)
        if uid not in seen:
            new_items.append(item)
            new_ids.add(uid)
    return new_items, seen | new_ids

def load_json(path):
    if not os.path.exists(path):
        return {"items": [], "errors": []}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def translate_papers_to_cn(papers: list, max_papers: int = 20) -> list:
    """
    用算法工程师视角解读每篇论文的实际意义，不是翻译 abstract
    使用内置 ks_aimate LLM 接口
    """
    import subprocess, sys

    top = sorted(papers, key=lambda x: x.get("score", 0), reverse=True)[:max_papers]

    paper_list_text = ""
    for i, p in enumerate(top, 1):
        title = p.get("title", "").replace("\n", " ").strip()
        abstract = p.get("content", "")[:800].replace("\n", " ")
        if "Abstract:" in abstract:
            abstract = abstract.split("Abstract:", 1)[-1].strip()
        paper_list_text += f"[{i}] 标题: {title}\n原始摘要: {abstract}\n\n"

    prompt = f"""你是一位专注于推荐系统、大模型和算法工程的资深工程师。
请阅读以下 arXiv 论文，用算法工程师的视角，写出每篇论文的中文快报。

重要要求：
- 不要翻译原始摘要，要用自己的话解释
- one_line：用一句话说清楚"这篇论文解决了什么工程问题"（20字以内，直接切入问题）
- cn_summary：2-3句话，说清楚做了什么、核心方法是什么、对实际推荐/大模型工程有什么用，要有具体性
- cn_title：中文标题，保留英文模型名/缩写

输出格式（严格 JSON，key 必须是 papers）：
{{"papers": [
  {{"index": 1, "cn_title": "...", "one_line": "...", "cn_summary": "..."}},
  ...
]}}

论文列表：
{paper_list_text}"""

    # 用内置 LLM 脚本
    translate_script = os.path.join(os.path.dirname(__file__), "llm_call.py")

    # 把 prompt 写成临时文件，避免命令行长度问题
    import tempfile
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write(prompt)
        prompt_file = f.name

    try:
        result = subprocess.run(
            [sys.executable, translate_script, "--prompt-file", prompt_file, "--json"],
            capture_output=True, text=True, timeout=120
        )
        raw = result.stdout.strip()
        if not raw:
            raise ValueError(f"LLM 返回空，stderr: {result.stderr[:300]}")
        parsed = json.loads(raw)
    finally:
        os.unlink(prompt_file)

    if isinstance(parsed, list):
        translations = parsed
    else:
        translations = next((v for v in parsed.values() if isinstance(v, list)), [])

    trans_map = {t["index"]: t for t in translations}
    result_papers = []
    for i, p in enumerate(top, 1):
        t = trans_map.get(i, {})
        result_papers.append({
            **p,
            "cn_title": t.get("cn_title", p.get("title", "")),
            "one_line": t.get("one_line", ""),
            "cn_summary": t.get("cn_summary", ""),
        })
    return result_papers


def build_markdown(rss_items, translated_papers, date_str):
    lines = []
    lines.append(f"# 🤖 AI 每日快报 — {date_str}\n")
    lines.append("> 面向算法工程师的个人科技情报流\n")
    lines.append("---\n")

    # 板块一：AI & 科技快讯
    lines.append("## 一、AI & 科技快讯\n")
    from collections import defaultdict
    by_source = defaultdict(list)
    for item in rss_items:
        by_source[item.get("feed_name", "其他")].append(item)

    # 来源展示顺序
    priority = ["极客公园", "36Kr", "OpenAI Blog", "TechCrunch AI", "The Verge", "爱范儿", "Hacker News"]
    sorted_sources = sorted(by_source.keys(), key=lambda x: priority.index(x) if x in priority else 99)

    for src in sorted_sources:
        items = by_source[src]
        lines.append(f"### {src}\n")
        for item in items:
            title = item.get("title", "").strip()
            url = item.get("url", "")
            if title and url:
                lines.append(f"- **[{title}]({url})**")
        lines.append("")

    lines.append("---\n")

    # 板块二：论文追踪
    lines.append("## 二、📄 arXiv 论文精选（中文摘要）\n")
    lines.append(f"_方向：大模型 / 推荐系统 / 生成式推荐 / 广告排序 / 多模态 | 共 {len(translated_papers)} 篇_\n")

    for i, p in enumerate(translated_papers, 1):
        title_en = p.get("title", "").replace("\n", " ").strip()
        cn_title = p.get("cn_title", title_en)
        one_line = p.get("one_line", "")
        cn_summary = p.get("cn_summary", "")
        url = p.get("url", "")
        authors = ", ".join(p.get("authors", [])[:4])
        score = p.get("score", 0)
        feed = p.get("feed_name", "")

        lines.append(f"### {i}. [{cn_title}]({url})")
        if title_en != cn_title:
            lines.append(f"_原题：{title_en}_")
        if one_line:
            lines.append(f"\n**核心贡献：** {one_line}")
        if cn_summary:
            lines.append(f"\n{cn_summary}")
        if authors:
            lines.append(f"\n> 作者：{authors}  |  来源：{feed}  |  相关度：{'⭐'*(min(score//2,5))}")
        lines.append("")

    lines.append("---\n")
    lines.append(f"_生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')} (北京时间)_\n")
    return "\n".join(lines)


def build_mixcard(rss_items, translated_papers, date_str, doc_url=None) -> dict:
    """
    构建 KIM kimMixCard JSON，不含 outer envelope 字段
    最多放：AI&科技摘要 + 论文 Top 15
    """
    from collections import defaultdict

    blocks = []

    # ── 头部说明 ──
    blocks.append({
        "blockId": "header_desc",
        "type": "content",
        "text": {
            "type": "kimMd",
            "content": f"来源：极客公园 / 36Kr / OpenAI / arXiv 等 | 论文精选 {len(translated_papers)} 篇"
        }
    })

    # ── 板块一：AI & 科技 Top N ──
    # 按优先来源取前 12 条
    priority = ["极客公园", "量子位", "36Kr", "OpenAI Blog", "TechCrunch AI", "The Verge", "爱范儿"]
    sorted_items = sorted(rss_items, key=lambda x: priority.index(x.get("feed_name","")) if x.get("feed_name","") in priority else 99)
    top_tech = sorted_items[:12]

    tech_md = "## 🔥 AI & 科技快讯\n\n"
    for item in top_tech:
        title = item.get("title", "").strip()
        url = item.get("url", "")
        source = item.get("feed_name", "")
        if title and url:
            tech_md += f"- [{title}]({url})  `{source}`\n"

    blocks.append({
        "blockId": "tech_news",
        "type": "content",
        "text": {"type": "kimMd", "content": tech_md}
    })

    # ── 板块二：论文 Top 15（中文摘要）──
    papers_md = f"## 📄 arXiv 论文精选（{len(translated_papers)} 篇）\n\n"
    papers_md += "_方向：大模型 / 推荐系统 / 生成式推荐 / 广告排序_\n\n"

    for i, p in enumerate(translated_papers, 1):
        cn_title = p.get("cn_title", p.get("title", "")).strip()
        one_line = p.get("one_line", "")
        cn_summary = p.get("cn_summary", "")
        url = p.get("url", "")
        authors_raw = p.get("authors", [])
        authors = ", ".join(authors_raw[:3]) + ("..." if len(authors_raw) > 3 else "")
        score = p.get("score", 0)

        papers_md += f"### {i}. [{cn_title}]({url})\n"
        if one_line:
            papers_md += f"**{one_line}**\n\n"
        if cn_summary:
            papers_md += f"{cn_summary}\n\n"
        if authors:
            papers_md += f"> {authors}\n\n"

    blocks.append({
        "blockId": "arxiv_papers",
        "type": "content",
        "text": {"type": "kimMd", "content": papers_md}
    })

    # ── 底部：完整日报链接 ──
    if doc_url:
        blocks.append({
            "blockId": "footer",
            "type": "content",
            "text": {
                "type": "kimMd",
                "content": f"---\n[📋 查看完整日报归档]({doc_url})"
            }
        })

    return {
        "header": {
            "title": f"🤖 AI 每日快报 — {date_str}",
            "style": "blue"
        },
        "blocks": blocks
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rss-cache", default="daily-digest/cache/rss_latest.json")
    parser.add_argument("--arxiv-cache", default="daily-digest/cache/arxiv_latest.json")
    parser.add_argument("--output-dir", default="daily-digest/output")
    parser.add_argument("--date", default=None)
    parser.add_argument("--max-papers", type=int, default=20)
    parser.add_argument("--doc-url", default=None, help="完整日报 Docs URL")
    parser.add_argument("--skip-translate", action="store_true", help="跳过翻译（调试用）")
    parser.add_argument("--no-dedup", action="store_true", help="跳过增量去重（调试用）")
    args = parser.parse_args()

    date_str = args.date or datetime.now().strftime("%Y-%m-%d")
    os.makedirs(args.output_dir, exist_ok=True)

    rss_data = load_json(args.rss_cache)
    arxiv_data = load_json(args.arxiv_cache)

    rss_items_raw = rss_data.get("items", [])
    arxiv_items_raw = arxiv_data.get("items", [])

    print(f"原始数据：科技源 {len(rss_items_raw)} 条 | arXiv {len(arxiv_items_raw)} 篇")

    # ── 增量去重 ──
    if args.no_dedup:
        rss_items = rss_items_raw
        arxiv_items = arxiv_items_raw
        seen = set()
    else:
        seen = load_seen_ids()
        rss_items, seen = deduplicate(rss_items_raw, seen)
        arxiv_items, seen = deduplicate(arxiv_items_raw, seen)
        print(f"去重后：科技源 {len(rss_items)} 条（新） | arXiv {len(arxiv_items)} 篇（新）")

    # 翻译论文
    if args.skip_translate:
        # 调试模式：只取 top N，不翻译
        translated = sorted(arxiv_items, key=lambda x: x.get("score",0), reverse=True)[:args.max_papers]
        for p in translated:
            p["cn_title"] = p.get("title","")
            p["one_line"] = ""
            p["cn_summary"] = p.get("content","")[:200]
    else:
        print(f"翻译论文中（top {args.max_papers}）...")
        translated = translate_papers_to_cn(arxiv_items, max_papers=args.max_papers)
        print(f"翻译完成，{len(translated)} 篇")

    # 保存翻译结果缓存
    trans_cache = os.path.join(args.output_dir, f"{date_str}_papers_cn.json")
    with open(trans_cache, "w", encoding="utf-8") as f:
        json.dump(translated, f, ensure_ascii=False, indent=2)
    print(f"论文中文缓存：{trans_cache}")

    # 生成 Markdown 日报
    md = build_markdown(rss_items, translated, date_str)
    md_path = os.path.join(args.output_dir, f"{date_str}_daily.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"✅ 完整日报：{md_path}")

    # 生成 mixCard JSON
    mixcard = build_mixcard(rss_items, translated, date_str, doc_url=args.doc_url)
    mc_path = os.path.join(args.output_dir, f"{date_str}_mixcard.json")
    with open(mc_path, "w", encoding="utf-8") as f:
        json.dump(mixcard, f, ensure_ascii=False, indent=2)
    print(f"✅ mixCard JSON：{mc_path}")

    print(f"\n📊 统计：科技快讯 {len(rss_items)} 条 | 精选论文 {len(translated)} 篇（含中文解读）")

    # ── 保存 seen_ids（只在真正推送完才更新，防止失败后漏掉内容）──
    if not args.no_dedup:
        save_seen_ids(seen)
        print(f"✅ seen_ids 已更新，累计 {len(seen)} 条")


if __name__ == "__main__":
    main()
