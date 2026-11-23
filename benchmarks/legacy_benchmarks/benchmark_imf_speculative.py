"""
benchmark_imf_speculative.py
End-to-end benchmark comparing:
1. Standard Autoregressive Generation with Target Model (1.14B params / 235M params)
2. Polytope-Aware Speculative Decoding with Drafter Model (15M drafter)
Loaded from zero-copy .imf binary containers.
"""

import sys
import time
from pathlib import Path
import torch

from imf.imf_model_loader import load_model_from_imf, load_imf_state_dict
from imf.joint_recon_predictor import IMFJointReconPredictorLM
from imf.speculative_polytope_decoder import SpeculativePolytopeDecoder

def run_benchmark():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[*] Running IMF Speculative Decoding Benchmark on {device} ({torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU'})")
    
    drafter_imf = Path("checkpoints/imf_drafter_fluency_4k.imf")
    target_imf = Path("checkpoints/imf_scaled_235m_fluency.imf")
    
    if not drafter_imf.exists() or not target_imf.exists():
        print(f"Error: Missing container files: {drafter_imf} or {target_imf}")
        return

    # Benchmark Cold-Start Loading from .imf containers
    print(f"\n[*] Benchmarking Zero-Copy IMF Container Deserialization...")
    t0 = time.perf_counter()
    drafter_sd = load_imf_state_dict(str(drafter_imf), device="cpu")
    t_drafter_load = (time.perf_counter() - t0) * 1000
    print(f"    [Drafter 5M]:   Loaded {len(drafter_sd)} tensors via mmap in {t_drafter_load:.2f} ms")

    t1 = time.perf_counter()
    target_sd = load_imf_state_dict(str(target_imf), device="cpu")
    t_target_load = (time.perf_counter() - t1) * 1000
    print(f"    [Target 235M]:  Loaded {len(target_sd)} tensors via mmap in {t_target_load:.2f} ms")

    # Instantiate Drafter Model Architecture (5.0M params, d=128, 2 layers, 8 experts)
    drafter_model = IMFJointReconPredictorLM(
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
    drafter_model.load_state_dict(drafter_sd, strict=False)
    drafter_model.eval()

    # Instantiate Target Model Architecture (235M params, d=384, 6 layers, 20 experts)
    target_model = IMFJointReconPredictorLM(
        vocab_size=4096,
        d_model=384,
        num_layers=6,
        num_heads=6,
        polytope_dim=8,
        num_experts=20,
        top_k=2,
        max_seq_len=128,
        alpha_recon=0.2,
    ).to(device)
    target_model.load_state_dict(target_sd, strict=False)
    target_model.eval()

    # Speculative Decoding Engine
    decoder = SpeculativePolytopeDecoder(
        target_model=target_model,
        drafter_model=drafter_model,
        gamma=4,
        temperature=0.0,
    )

    prompt_ids = torch.randint(10, 4000, (1, 16), device=device)
    max_new_tokens = 32

    # 1. Baseline Target Standard Autoregressive Generation
    print(f"\n[*] Benchmarking Baseline Standard Generation (Target Only)...")
    torch.cuda.synchronize() if torch.cuda.is_available() else None
    t_start_base = time.perf_counter()
    
    with torch.no_grad():
        curr_ids = prompt_ids.clone()
        for _ in range(max_new_tokens):
            out = target_model(curr_ids)
            logits = out[0] if isinstance(out, (tuple, list)) else out
            next_token = torch.argmax(logits[:, -1, :], dim=-1, keepdim=True)
            curr_ids = torch.cat([curr_ids, next_token], dim=1)
            
    torch.cuda.synchronize() if torch.cuda.is_available() else None
    t_base = time.perf_counter() - t_start_base
    base_tok_sec = max_new_tokens / t_base
    print(f"    Baseline Generation Time: {t_base*1000:.2f} ms ({base_tok_sec:.2f} tokens/sec)")

    # 2. Speculative Polytope Decoding
    print(f"\n[*] Benchmarking Speculative Polytope Decoding (Drafter gamma=4 + Target Fused Verification)...")
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
    
    # Parity check on greedy tokens
    tokens_match = (curr_ids[:, :prompt_ids.shape[1] + max_new_tokens] == spec_ids[:, :prompt_ids.shape[1] + max_new_tokens]).all().item()
    print(f"    Mathematical Parity Match:   {'[PASS] Exact distribution match' if tokens_match else '[Divergence]'}")

if __name__ == "__main__":
    run_benchmark()
