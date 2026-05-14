# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///

import argparse
import sys
import json
import os
from difflib import SequenceMatcher

def main():
    parser = argparse.ArgumentParser(description="Deduplicate items from multiple sources")
    parser.add_argument("--input", required=True, help="Path to input JSON file containing items")
    parser.add_argument("--title-similarity-threshold", type=float, default=0.7, help="Title similarity threshold for dedup (0-1)")
    parser.add_argument("--output", default=None, help="Output file path (default: stdout)")
    args = parser.parse_args()

    try:
        with open(args.input, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: Input file not found: {args.input}", file=sys.stderr)
        print("指引：请确保输入文件路径正确。")
        sys.exit(0)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in input file: {e}", file=sys.stderr)
        sys.exit(0)

    items = data.get("items", [])
    if not items:
        result = {"items": [], "removed": [], "meta": {"input_count": 0, "output_count": 0, "removed_count": 0}}
        output_json = json.dumps(result, ensure_ascii=False)
        print(output_json)
        return

    # Step 1: URL-based dedup (exact match)
    seen_urls = {}
    url_deduped = []
    url_removed = []

    for item in items:
        url = item.get("url", "")
        if url in seen_urls:
            url_removed.append({"kept": seen_urls[url], "removed": item, "reason": "url_duplicate"})
        else:
            seen_urls[url] = item
            url_deduped.append(item)

    # Step 2: Title similarity dedup
    title_deduped = []
    title_removed = []
    processed = [False] * len(url_deduped)

    for i in range(len(url_deduped)):
        if processed[i]:
            continue
        title_deduped.append(url_deduped[i])
        processed[i] = True

        for j in range(i + 1, len(url_deduped)):
            if processed[j]:
                continue
            title_i = url_deduped[i].get("title", "")
            title_j = url_deduped[j].get("title", "")
            similarity = SequenceMatcher(None, title_i.lower(), title_j.lower()).ratio()

            if similarity >= args.title_similarity_threshold:
                title_removed.append({
                    "kept": url_deduped[i],
                    "removed": url_deduped[j],
                    "reason": "title_similarity",
                    "similarity": round(similarity, 3)
                })
                processed[j] = True

    result = {
        "items": title_deduped,
        "removed": url_removed + title_removed,
        "meta": {
            "input_count": len(items),
            "output_count": len(title_deduped),
            "removed_count": len(url_removed) + len(title_removed),
            "url_dedup_removed": len(url_removed),
            "title_dedup_removed": len(title_removed),
            "title_similarity_threshold": args.title_similarity_threshold
        }
    }

    output_json = json.dumps(result, ensure_ascii=False)

    if args.output:
        os.makedirs(os.path.dirname(args.output) if os.path.dirname(args.output) else ".", exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output_json)
        print(f"Saved to {args.output}")
    else:
        print(output_json)


if __name__ == "__main__":
    main()