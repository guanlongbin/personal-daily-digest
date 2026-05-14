# /// script
# requires-python = ">=3.9"
# dependencies = [
#     "requests",
# ]
# ///

import argparse
import sys
import json
import os
from datetime import datetime, timedelta, timezone
import requests

def main():
    parser = argparse.ArgumentParser(description="Fetch GitHub releases for specified repos")
    parser.add_argument("--repos", required=True, help="JSON string of repo list, e.g. '[\"openai/openai-python\",\"anthropic/anthropic-sdk-python\"]'")
    parser.add_argument("--hours", type=int, default=24, help="Time window in hours to look back")
    parser.add_argument("--output", default=None, help="Output file path (default: stdout)")
    args = parser.parse_args()

    try:
        repos = json.loads(args.repos)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid repos JSON: {e}", file=sys.stderr)
        print("指引：请确保 --repos 参数是合法的 JSON 数组字符串。")
        sys.exit(0)

    if not isinstance(repos, list):
        print("Error: --repos must be a JSON array of strings", file=sys.stderr)
        print("指引：请传入仓库列表，格式如 '[\"owner/repo\"]'")
        sys.exit(0)

    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=args.hours)
    all_items = []
    errors = []

    for repo in repos:
        try:
            url = f"https://api.github.com/repos/{repo}/releases"
            resp = requests.get(url, timeout=15, headers={"Accept": "application/vnd.github+json"})
            if resp.status_code != 200:
                errors.append({"repo": repo, "error": f"HTTP {resp.status_code}", "detail": resp.text[:200]})
                continue

            releases = resp.json()
            for release in releases:
                published_at = release.get("published_at", "")
                if published_at:
                    try:
                        pub_time = datetime.strptime(published_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                        if pub_time < cutoff_time:
                            continue
                    except ValueError:
                        pass

                item = {
                    "title": release.get("name") or release.get("tag_name", ""),
                    "url": release.get("html_url", ""),
                    "source": "github",
                    "publish_time": published_at,
                    "content": release.get("body", "")[:500] if release.get("body") else "",
                    "repo": repo,
                    "version": release.get("tag_name", ""),
                    "is_prerelease": release.get("prerelease", False),
                    "dedup_key": f"github:{repo}:{release.get('tag_name', '')}"
                }
                all_items.append(item)

        except requests.RequestException as e:
            errors.append({"repo": repo, "error": str(e)})
        except Exception as e:
            errors.append({"repo": repo, "error": f"Unexpected: {str(e)}"})

    result = {
        "items": all_items,
        "errors": errors,
        "meta": {
            "total_repos": len(repos),
            "total_items": len(all_items),
            "total_errors": len(errors),
            "time_window_hours": args.hours,
            "fetched_at": datetime.now(timezone.utc).isoformat()
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