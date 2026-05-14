# /// script
# requires-python = ">=3.9"
# dependencies = [
#     "feedparser",
# ]
# ///

import argparse
import sys
import json
import os
from datetime import datetime, timedelta

def main():
    parser = argparse.ArgumentParser(description="Fetch items from RSS/Atom feeds")
    parser.add_argument("--feeds", required=True, help="JSON string of feed list, e.g. '[{\"name\":\"HackerNews\",\"url\":\"https://...\"}]'")
    parser.add_argument("--hours", type=int, default=24, help="Time window in hours to look back")
    parser.add_argument("--max-items-per-feed", type=int, default=20, help="Max items to fetch per feed")
    parser.add_argument("--output", default=None, help="Output file path (default: stdout)")
    args = parser.parse_args()

    try:
        feeds = json.loads(args.feeds)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid feeds JSON: {e}", file=sys.stderr)
        print("指引：请确保 --feeds 参数是合法的 JSON 数组字符串。")
        sys.exit(0)

    if not isinstance(feeds, list):
        print("Error: --feeds must be a JSON array", file=sys.stderr)
        sys.exit(0)

    import feedparser

    cutoff_time = datetime.utcnow() - timedelta(hours=args.hours)
    all_items = []
    errors = []

    for feed_config in feeds:
        feed_name = feed_config.get("name", "unknown")
        feed_url = feed_config.get("url", "")

        if not feed_url:
            errors.append({"feed": feed_name, "error": "No URL provided"})
            continue

        try:
            parsed = feedparser.parse(feed_url)

            if parsed.bozo and not parsed.entries:
                errors.append({"feed": feed_name, "error": f"Parse error: {parsed.bozo_exception}"})
                continue

            count = 0
            for entry in parsed.entries:
                if count >= args.max_items_per_feed:
                    break

                published_at = ""
                if hasattr(entry, "published") and entry.published:
                    published_at = entry.published
                elif hasattr(entry, "updated") and entry.updated:
                    published_at = entry.updated

                content = ""
                if hasattr(entry, "summary") and entry.summary:
                    content = entry.summary[:500]
                elif hasattr(entry, "description") and entry.description:
                    content = entry.description[:500]

                link = entry.get("link", "")

                item = {
                    "title": entry.get("title", ""),
                    "url": link,
                    "source": "rss",
                    "publish_time": published_at,
                    "content": content,
                    "feed_name": feed_name,
                    "dedup_key": f"rss:{feed_name}:{link}"
                }
                all_items.append(item)
                count += 1

        except Exception as e:
            errors.append({"feed": feed_name, "error": str(e)})

    result = {
        "items": all_items,
        "errors": errors,
        "meta": {
            "total_feeds": len(feeds),
            "total_items": len(all_items),
            "total_errors": len(errors),
            "time_window_hours": args.hours,
            "fetched_at": datetime.utcnow().isoformat() + "Z"
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