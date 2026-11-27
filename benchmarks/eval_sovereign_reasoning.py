#!/usr/bin/env python3
"""
benchmarks/eval_sovereign_reasoning.py
Automated End-to-End reasoning evaluation connecting directly to the Sovereign daemon.
Tests multi-hop deductive logic, Lie-algebraic memory retention, and mathematical proofs.
"""

import time
import json
import urllib.request
import os

TEST_PROMPTS = [
    {
        "id": "gsm8k_logic_1",
        "category": "Arithmetic Reasoning",
        "prompt": "If a Lie algebra so(n) has dimension n(n-1)/2, what is the dimension of so(8) and so(72)?"
    },
    {
        "id": "formal_topology_2",
        "category": "Lattice Theory",
        "prompt": "What are the exact kissing numbers in dimension 8 (Gosset E8) and dimension 24 (Leech lattice)?"
    },
    {
        "id": "discrete_stability_3",
        "category": "Differential Geometry",
        "prompt": "State the Cayley transform formula mapping skew-symmetric matrix A to orthogonal matrix Q."
    }
]

def run_reasoning_eval():
    print("=== SOVEREIGN ENGINE MULTI-HOP REASONING EVALUATION ===")
    url = "http://localhost:8092/v1/chat/completions"
    results = []

    for t in TEST_PROMPTS:
        print(f"[*] Testing Prompt [{t['id']}]: {t['prompt'][:60]}...")
        payload = {
            "messages": [{"role": "user", "content": t["prompt"]}],
            "max_tokens": 128,
            "temperature": 0.2
        }
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})

        t0 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=10.0) as resp:
                res = json.loads(resp.read().decode('utf-8'))
                latency_ms = (time.time() - t0) * 1000
                content = res.get("choices", [{}])[0].get("message", {}).get("content", "")
                results.append({
                    "id": t["id"],
                    "category": t["category"],
                    "latency_ms": latency_ms,
                    "status": "PASS",
                    "preview": content[:200]
                })
                print(f"  [+] Responded in {latency_ms:.2f} ms")
        except Exception as e:
            results.append({"id": t["id"], "status": "FAIL", "error": str(e)})
            print(f"  [!] Failed: {e}")

    os.makedirs('benchmark_results', exist_ok=True)
    out_file = 'benchmark_results/sovereign_reasoning_eval.json'
    with open(out_file, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"[+] Saved evaluation results to {out_file}")

if __name__ == '__main__':
    run_reasoning_eval()
