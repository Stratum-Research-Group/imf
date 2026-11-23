"""
scripts/client_demo_openai_api.py
Interactive & Streaming Client Demo Querying the Local IMF OpenAI-Compatible API (Track 3).

Demonstrates:
1. Model discovery query (GET /v1/models)
2. Synchronous chat completion query (POST /v1/chat/completions)
3. Server-Sent Events (SSE) streaming token query (stream=True)
4. Telemetry and latency benchmarks.
"""

import sys
import time
import json
import urllib.request
import urllib.error

API_BASE = "http://127.0.0.1:8085"


def test_models():
    print(f"[*] Querying active models from {API_BASE}/v1/models...")
    req = urllib.request.Request(f"{API_BASE}/v1/models")
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode())
        print(f"[✓] Active Models Response (HTTP {resp.status}):")
        for m in data.get("data", []):
            print(f"    - ID: {m['id']} (Capabilities: {', '.join(m.get('capabilities', []))})")


def test_chat_completion(prompt: str = "Explain the Lie-algebraic memory split in IMF."):
    print(f"\n[*] Sending Chat Completion request (Prompt: '{prompt}')...")
    payload = json.dumps({
        "model": "imf-foundation-1b",
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.2,
        "stream": False
    }).encode("utf-8")

    t0 = time.perf_counter()
    req = urllib.request.Request(
        f"{API_BASE}/v1/chat/completions",
        data=payload,
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as resp:
        res = json.loads(resp.read().decode())
        latency_ms = (time.perf_counter() - t0) * 1000.0
        content = res["choices"][0]["message"]["content"]
        tokens = res["usage"]["total_tokens"]
        print(f"[✓] Response Received in {latency_ms:.1f}ms ({tokens} total tokens):")
        print("-" * 60)
        print(content)
        print("-" * 60)


def test_streaming_completion(prompt: str = "Stream speculative tokens for 100B Leech MoPE."):
    print(f"\n[*] Initiating Server-Sent Events (SSE) Streaming Token Query...")
    payload = json.dumps({
        "model": "imf-foundation-1b",
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "stream": True
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{API_BASE}/v1/chat/completions",
        data=payload,
        headers={"Content-Type": "application/json"}
    )
    print("    Stream Output: ", end="", flush=True)
    with urllib.request.urlopen(req) as resp:
        for line in resp:
            decoded = line.decode("utf-8").strip()
            if decoded.startswith("data: ") and not decoded.endswith("[DONE]"):
                data_json = json.loads(decoded[6:])
                delta = data_json["choices"][0]["delta"].get("content", "")
                print(delta, end="", flush=True)
    print("\n[✓] Stream Completed cleanly.")


def main():
    print("=" * 80)
    print("  IMF OPENAI-COMPATIBLE API CLIENT DEMO (TRACK 3)")
    print(f"  Target Host: {API_BASE}")
    print("=" * 80)
    test_models()
    test_chat_completion()
    test_streaming_completion()
    print("=" * 80)
    print("  All API Client Verification Tests Passed Cleanly.")
    print("=" * 80)


if __name__ == "__main__":
    main()
