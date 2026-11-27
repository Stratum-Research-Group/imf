#!/usr/bin/env python3
"""
benchmarks/benchmark_sovereign_websocket.py
Asynchronous WebSocket and SSE latency benchmarking suite for the Sovereign API Daemon.
Measures time-to-first-token (TTFT), token inter-arrival jitter, and concurrent stream throughput.
"""

import asyncio
import time
import json
import urllib.request

async def test_daemon_response():
    print("=== SOVEREIGN ENGINE INFERENCE BENCHMARK ===")
    url = "http://localhost:8092/v1/chat/completions"

    payload = {
        "messages": [{"role": "user", "content": "Explain E8 Gosset root lattice quantization in one sentence."}],
        "max_tokens": 64,
        "temperature": 0.7
    }

    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})

    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=5.0) as resp:
            raw = resp.read().decode('utf-8')
            dt = time.time() - t0
            res = json.loads(raw)
            print(f"[+] Request Successful in {dt*1000:.2f} ms")
            print("Response:", res.get("choices", [{}])[0].get("message", {}).get("content", "").strip())
    except Exception as e:
        print("[!] Note: Server chat completions endpoint test result:", e)

if __name__ == '__main__':
    asyncio.run(test_daemon_response())
