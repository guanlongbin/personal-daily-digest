# /// script
# requires-python = ">=3.9"
# dependencies = [
#     "requests",
# ]
# ///

"""
内置 LLM 调用工具，对接 ks_aimate 接口。
用法：
  uv run llm_call.py --prompt "..." [--json]
  uv run llm_call.py --prompt-file /path/to/prompt.txt [--json]
"""

import argparse
import json
import os
import sys
import requests


def call_llm(prompt: str, expect_json: bool = False) -> str:
    """调用内置 LLM 接口"""
    api_base = os.environ.get("OPENAI_API_BASE", "")
    api_key = os.environ.get("OPENAI_API_KEY", "")

    if not api_base or not api_key:
        # 尝试读取 ks_aimate 配置
        config_paths = [
            "/home/myflicker/.config/ks_aimate/config.json",
            "/data/aime/config.json",
        ]
        for cp in config_paths:
            if os.path.exists(cp):
                with open(cp) as f:
                    cfg = json.load(f)
                api_base = cfg.get("api_base", api_base)
                api_key = cfg.get("api_key", api_key)
                break

    if not api_base:
        # fallback: 直接用环境变量里能找到的任意 OpenAI 兼容接口
        api_base = "https://api.openai.com/v1"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
    }
    if expect_json:
        payload["response_format"] = {"type": "json_object"}

    resp = requests.post(
        f"{api_base.rstrip('/')}/chat/completions",
        headers=headers,
        json=payload,
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt", default=None)
    parser.add_argument("--prompt-file", default=None)
    parser.add_argument("--json", action="store_true", dest="expect_json")
    args = parser.parse_args()

    if args.prompt_file:
        with open(args.prompt_file, encoding="utf-8") as f:
            prompt = f.read()
    elif args.prompt:
        prompt = args.prompt
    else:
        prompt = sys.stdin.read()

    result = call_llm(prompt, expect_json=args.expect_json)
    print(result)


if __name__ == "__main__":
    main()
