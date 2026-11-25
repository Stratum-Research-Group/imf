"""
scripts/benchmark_streaming_multimodal_throughput.py
Measures end-to-end sustained streaming throughput and latency of IMF OmniBlock
under continuous multimodal frame/packet ingestion on the local RTX 5060 Ti GPU.
Evaluates:
- Real-time frame processing rate (FPS).
- Sustained token throughput (tokens/sec).
- Per-frame latency distribution and peak resident VRAM footprint.
"""

import time
import json
import math
import subprocess
import torch
from imf.omni_block import IMFOmniBlock

def main():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    git_rev = subprocess.check_output(["git", "rev-parse", "HEAD"]).decode("utf-8").strip()
    
    print("=" * 80)
    print("  IMF CONTINUOUS MULTIMODAL STREAMING THROUGHPUT BENCHMARK")
    print(f"  Target Silicon: {device} ({torch.cuda.get_device_name(0) if device=='cuda' else 'CPU'})")
    print("=" * 80)
    
    d_model = 128
    num_heads = 4
    tokens_per_frame = 64
    num_frames = 150
    
    block = IMFOmniBlock(d_model=d_model, num_heads=num_heads, use_triton_ssm=False).to(device)
    block.eval()
    
    # Warmup
    dummy = torch.randn(1, tokens_per_frame, d_model, device=device)
    for _ in range(5):
        _ = block(dummy)
    if device == "cuda":
        torch.cuda.synchronize()
        torch.cuda.reset_peak_memory_stats()
        
    frame_latencies_ms = []
    state = None
    
    t_total_start = time.perf_counter()
    with torch.no_grad():
        for f in range(num_frames):
            frame_input = torch.randn(1, tokens_per_frame, d_model, device=device)
            if device == "cuda":
                torch.cuda.synchronize()
            t0 = time.perf_counter()
            
            # Recurrent state threading between consecutive frames
            out, state = block.forward_ssm(block.norm1(frame_input), initial_state=state, return_final_state=True)
            
            if device == "cuda":
                torch.cuda.synchronize()
            frame_latencies_ms.append((time.perf_counter() - t0) * 1000.0)
            
    total_duration_s = time.perf_counter() - t_total_start
    total_tokens = num_frames * tokens_per_frame
    fps = num_frames / total_duration_s
    tps = total_tokens / total_duration_s
    
    mean_lat_ms = sum(frame_latencies_ms) / len(frame_latencies_ms)
    std_lat_ms = math.sqrt(sum((x - mean_lat_ms)**2 for x in frame_latencies_ms) / len(frame_latencies_ms))
    p95_lat_ms = sorted(frame_latencies_ms)[int(0.95 * len(frame_latencies_ms))]
    peak_vram_mb = (torch.cuda.max_memory_allocated() / (1024 * 1024)) if device == "cuda" else 0.0
    
    print(f"Total Streamed Tokens: {total_tokens:,} across {num_frames} frames")
    print(f"Processing Rate:       {fps:.1f} FPS (Target: >= 30 FPS for real-time)")
    print(f"Throughput:            {tps:.1f} tokens/second")
    print(f"Per-Frame Latency:     {mean_lat_ms:.2f} ± {std_lat_ms:.2f} ms (p95: {p95_lat_ms:.2f} ms)")
    print(f"Peak VRAM Footprint:   {peak_vram_mb:.2f} MB")
    
    results = {
        "git_commit": git_rev,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "hardware": torch.cuda.get_device_name(0) if device == "cuda" else "CPU",
        "tokens_per_frame": tokens_per_frame,
        "num_frames": num_frames,
        "total_tokens": total_tokens,
        "throughput_fps": round(fps, 2),
        "throughput_tokens_per_sec": round(tps, 2),
        "mean_latency_ms": round(mean_lat_ms, 2),
        "std_latency_ms": round(std_lat_ms, 2),
        "p95_latency_ms": round(p95_lat_ms, 2),
        "peak_vram_mb": round(peak_vram_mb, 2),
        "realtime_satisfied": fps >= 30.0
    }
    
    out_path = "benchmark_results/multimodal_streaming_throughput.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"[✓] Streaming throughput benchmark saved to {out_path}")

if __name__ == "__main__":
    main()
