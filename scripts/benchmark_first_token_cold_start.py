"""
scripts/benchmark_first_token_cold_start.py
Empirical measurement of First-Token Cold Start Latency (TTFT) and Warm Generation.
Quantifies genuine silicon execution latencies across:
1. Cold model forward pass (unwarmed caches, kernel JIT dispatch).
2. Warm sequential token generation passes.
3. Ratio and distribution across iterations.
"""

import time
import json
import math
import subprocess
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

def main():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    git_rev = subprocess.check_output(["git", "rev-parse", "HEAD"]).decode("utf-8").strip()
    
    print("=" * 80)
    print("  IMF FIRST-TOKEN COLD START & WARM TTFT BENCHMARK")
    print(f"  Target Silicon: {device} ({torch.cuda.get_device_name(0) if device=='cuda' else 'CPU'})")
    print("=" * 80)
    
    model_id = "Qwen/Qwen2.5-0.5B"
    tokenizer = AutoTokenizer.from_pretrained(model_id)
    model = AutoModelForCausalLM.from_pretrained(model_id, dtype=torch.float16, device_map=device)
    model.eval()
    
    prompt = "The foundational principles of mathematical interaction models require"
    inputs = tokenizer(prompt, return_tensors="pt").to(device)
    
    # Measure cold-start first-token latency
    if device == "cuda":
        torch.cuda.synchronize()
    t0 = time.perf_counter()
    with torch.no_grad():
        out = model(**inputs)
        _ = out.logits[:, -1, :].argmax(dim=-1)
    if device == "cuda":
        torch.cuda.synchronize()
    cold_start_ttft_ms = (time.perf_counter() - t0) * 1000.0
    
    # Measure warm-state latencies across 20 iterations
    warm_latencies = []
    for _ in range(20):
        if device == "cuda":
            torch.cuda.synchronize()
        t_start = time.perf_counter()
        with torch.no_grad():
            out = model(**inputs)
            _ = out.logits[:, -1, :].argmax(dim=-1)
        if device == "cuda":
            torch.cuda.synchronize()
        warm_latencies.append((time.perf_counter() - t_start) * 1000.0)
        
    mean_warm_ms = sum(warm_latencies) / len(warm_latencies)
    std_warm_ms = math.sqrt(sum((x - mean_warm_ms)**2 for x in warm_latencies) / len(warm_latencies))
    ratio = cold_start_ttft_ms / max(mean_warm_ms, 1e-6)
    
    print(f"Cold-Start TTFT:     {cold_start_ttft_ms:6.2f} ms")
    print(f"Warm Mean TTFT:      {mean_warm_ms:6.2f} ± {std_warm_ms:.2f} ms")
    print(f"Measured Ratio:      {ratio:6.2f}x (Cold over Warm)")
    
    results = {
        "git_commit": git_rev,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "hardware": torch.cuda.get_device_name(0) if device == "cuda" else "CPU",
        "model_id": model_id,
        "cold_start_ttft_ms": round(cold_start_ttft_ms, 2),
        "warm_mean_ttft_ms": round(mean_warm_ms, 2),
        "warm_std_ttft_ms": round(std_warm_ms, 2),
        "cold_to_warm_ratio": round(ratio, 2),
        "iterations": len(warm_latencies),
        "description": "Empirical first-token time-to-first-token (TTFT) measuring real silicon dispatch cold-start vs. warm execution."
    }
    
    out_path = "benchmark_results/first_token_cold_start.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"[✓] Cold start benchmark saved to {out_path}")

if __name__ == "__main__":
    main()
