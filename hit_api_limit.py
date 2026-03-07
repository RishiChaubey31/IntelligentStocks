#!/usr/bin/env python3
"""
Script to call OpenRouter API repeatedly until rate limit is hit.
"""

import requests
import time

API_KEY = "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"
API_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "openai/gpt-oss-120b:free"

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
    "HTTP-Referer": "https://utsavdwivedi51.github.io/QuickTalk---Modern-AI-Chat/",
    "X-Title": "QuickTalk",
}


def call_api(call_num: int) -> bool:
    """Make a single API call. Returns True if successful, False if rate limited."""
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": "You are a helpful assistant. Reply briefly."},
            {"role": "user", "content": f"Say only the number: {call_num}"},
        ],
        "max_tokens": 10,
    }
    try:
        resp = requests.post(API_URL, json=payload, headers=headers, timeout=60)
        if resp.status_code == 429:
            print(f"\n[Call #{call_num}] RATE LIMIT HIT (429)")
            print(f"Response: {resp.text[:500]}")
            return False
        resp.raise_for_status()
        data = resp.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        print(f"[Call #{call_num}] OK - Response: {content.strip()[:80]}")
        return True
    except requests.exceptions.RequestException as e:
        if hasattr(e, "response") and e.response is not None and e.response.status_code == 429:
            print(f"\n[Call #{call_num}] RATE LIMIT HIT (429)")
            return False
        print(f"[Call #{call_num}] Error: {e}")
        raise


def main():
    print(f"Calling OpenRouter API ({MODEL}) until rate limit...\n")
    call_count = 0
    start = time.time()

    while True:
        call_count += 1
        success = call_api(call_count)
        if not success:
            break
        time.sleep(0.5)  # Small delay to avoid hammering

    elapsed = time.time() - start
    print(f"\n--- Summary ---")
    print(f"Total successful calls before limit: {call_count - 1}")
    print(f"Total time: {elapsed:.1f}s")


if __name__ == "__main__":
    main()
