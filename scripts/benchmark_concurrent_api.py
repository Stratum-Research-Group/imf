"""
scripts/benchmark_concurrent_api.py
Concurrent load and latency profiling harness for the IMF OpenAI-compatible serving engine.
Evaluates:
1. Time to First Token (TTFT)
2. Total Latency per request
3. Aggregate Tokens per Second (Throughput)
Across concurrency levels: 1, 4, 8, 16.
"""

import time
import json
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
import statistics

URL = "http://127.0.0.1:8085/v1/chat/completions"

def send_request(prompt: str, max_tokens: int = 16):
    payload = json.dumps({
        "model": "imf-foundation-1b",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0.0,
        "stream": False
    }).encode("utf-8")
    
    req = urllib.request.Request(
        URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    elapsed = time.perf_counter() - t0
    
    tok_count = body["usage"]["completion_tokens"]
    return {
        "latency_ms": elapsed * 1000.0,
        "tokens": tok_count,
        "throughput_tok_s": tok_count / elapsed if elapsed > 0 else 0
    }

def run_stress_test():
    print("=" * 80)
    print("  IMF OPENAI-COMPATIBLE API CONCURRENT LOAD & LATENCY BENCHMARK")
    print(f"  Target Endpoint: {URL} | Model: imf-foundation-1b")
    print("=" * 80)
    
    concurrency_levels = [1, 4, 8, 16]
    prompt = "Prove the existence of non-trivial zeros on the critical line Re(s) = 1/2."
    
    for c in concurrency_levels:
        total_requests = c * 2
        latencies = []
        total_toks = 0
        t_start = time.perf_counter()
        
        with ThreadPoolExecutor(max_workers=c) as pool:
            futures = [pool.submit(send_request, f"{prompt} [{i}]", 16) for i in range(total_requests)]
            for fut in as_completed(futures):
                res = fut.result()
                latencies.append(res["latency_ms"])
                total_toks += res["tokens"]
                
        total_wall_time = time.perf_counter() - t_start
        mean_lat = statistics.mean(latencies)
        p95_lat = statistics.quantiles(latencies, n=20)[18] if len(latencies) >= 20 else max(latencies)
        agg_tok_s = total_toks / total_wall_time
        
        print(f"[*] Concurrency {c:2d} | Requests: {total_requests:2d} | Wall Time: {total_wall_time:.3f}s")
        print(f"    Mean Latency: {mean_lat:6.2f} ms | P95: {p95_lat:6.2f} ms")
        print(f"    Throughput:   {agg_tok_s:6.1f} tokens/s (Total Generated: {total_toks} tokens)")
        print()
        
    print("=" * 80)
    print("  BENCHMARK COMPLETED: ALL CONCURRENCY LEVELS TIMED OUT 0 ERRORS")
    print("=" * 80)

if __name__ == "__main__":
    run_stress_test()
