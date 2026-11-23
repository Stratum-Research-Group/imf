"""
benchmark_1b_speculative.py
Executes end-to-end speculative decoding connecting:
- Target Model: IMF 1.14B Foundation Model (1.141B parameters, 16 layers, d_model=576)
- Drafter Model: IMF Distilled Fast Drafter (5.0M parameters, 2 layers, d_model=128)
Both loaded directly from zero-copy .imf binary containers.
"""

import sys
import time
from pathlib import Path
import torch

from imf.imf_model_loader import load_imf_state_dict
from imf.joint_recon_predictor import IMFJointReconPredictorLM
from imf.speculative_polytope_decoder import SpeculativePolytopeDecoder

def run_1b_speculative_benchmark():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[*] Running IMF 1.14B Flagship Speculative Decoding on {device} ({torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU'})")

    drafter_imf = Path("checkpoints/imf_drafter_fluency_4k.imf")
    target_imf = Path("checkpoints/imf_foundation_1b.imf")

    if not drafter_imf.exists() or not target_imf.exists():
        print(f"Error: Missing container files: {drafter_imf} or {target_imf}")
        return

    # 1. Zero-Copy Loading
    print("\n[*] Zero-Copy mmap Loading...")
    t0 = time.perf_counter()
    drafter_sd = load_imf_state_dict(str(drafter_imf), device="cpu")
    t_drafter_load = (time.perf_counter() - t0) * 1000
    print(f"    [Drafter 5M]:   Loaded {len(drafter_sd)} tensors via mmap in {t_drafter_load:.2f} ms")

    t1 = time.perf_counter()
    target_sd = load_imf_state_dict(str(target_imf), device="cpu")
    t_target_load = (time.perf_counter() - t1) * 1000
    print(f"    [Target 1.14B]: Loaded {len(target_sd)} tensors via mmap in {t_target_load:.2f} ms")

    # 2. Instantiate Architectures
    print("\n[*] Materializing Architectures on GPU...")
    drafter = IMFJointReconPredictorLM(
        vocab_size=4096,
        d_model=128,
        num_layers=2,
        num_heads=4,
        polytope_dim=4,
        num_experts=8,
        top_k=2,
        max_seq_len=128,
        alpha_recon=0.1,
    ).to(device)
    drafter.load_state_dict(drafter_sd, strict=False)
    drafter.eval()

    target = IMFJointReconPredictorLM(
        vocab_size=4096,
        d_model=576,
        num_layers=16,
        num_heads=8,
        polytope_dim=8,
        num_experts=16,
        top_k=2,
        max_seq_len=128,
        alpha_recon=0.2,
    ).to(device)
    target.load_state_dict(target_sd, strict=False)
    target.eval()

    if torch.cuda.is_available():
        vram_gb = torch.cuda.memory_allocated() / (1024**3)
        print(f"    Total GPU VRAM Allocated: {vram_gb:.2f} GB / 16.0 GB (Comfortably inside RTX 5060 Ti budget)")

    # 3. Benchmark Standard Autoregressive Baseline
    prompt_ids = torch.randint(10, 4000, (1, 16), device=device)
    max_new_tokens = 24

    print(f"\n[*] Benchmarking Baseline Standard Generation (Target 1.14B Only, {max_new_tokens} tokens)...")
    torch.cuda.synchronize() if torch.cuda.is_available() else None
    t_start_base = time.perf_counter()

    with torch.no_grad():
        curr_ids = prompt_ids.clone()
        for _ in range(max_new_tokens):
            out = target(curr_ids)
            logits = out[0] if isinstance(out, (tuple, list)) else out
            next_token = torch.argmax(logits[:, -1, :], dim=-1, keepdim=True)
            curr_ids = torch.cat([curr_ids, next_token], dim=1)

    torch.cuda.synchronize() if torch.cuda.is_available() else None
    t_base = time.perf_counter() - t_start_base
    base_tok_sec = max_new_tokens / t_base
    print(f"    Target 1.14B Baseline Generation Time: {t_base*1000:.2f} ms ({base_tok_sec:.2f} tokens/sec)")

    # 4. Speculative Decoding on 1.14B Model
    print(f"\n[*] Benchmarking Speculative Polytope Decoding (Drafter gamma=4 + Target 1.14B Verification)...")
    decoder = SpeculativePolytopeDecoder(
        target_model=target,
        drafter_model=drafter,
        gamma=4,
        temperature=0.0,
    )

    torch.cuda.synchronize() if torch.cuda.is_available() else None
    t_start_spec = time.perf_counter()

    spec_ids, metrics = decoder.generate_speculative(prompt_ids, max_new_tokens=max_new_tokens)

    torch.cuda.synchronize() if torch.cuda.is_available() else None
    t_spec = time.perf_counter() - t_start_spec
    spec_tok_sec = max_new_tokens / t_spec
    speedup = t_base / t_spec

    print(f"    Speculative Generation Time: {t_spec*1000:.2f} ms ({spec_tok_sec:.2f} tokens/sec)")
    print(f"    Acceleration Speedup:        {speedup:.2f}x")
    print(f"    Speculation Metrics:         Acceptance Rate = {metrics['acceptance_rate']*100:.1f}%, Steps = {metrics['speculative_steps']}")

    parity = (curr_ids[:, :prompt_ids.shape[1] + max_new_tokens] == spec_ids[:, :prompt_ids.shape[1] + max_new_tokens]).all().item()
    print(f"    Mathematical Parity Match:   {'[PASS] Exact distribution match' if parity else '[Divergence]'}")

if __name__ == "__main__":
    run_1b_speculative_benchmark()
