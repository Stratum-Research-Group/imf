"""
Triton Fused Polytope Landauer Energy & Thermodynamic Entropy Gauge Kernel
==========================================================================
Computes the thermodynamic Landauer dissipation per token state transition:
    ΔE = k_B T ln(2) · D_{KL}(P_t || P_{t-1})
and the discrete geodesic curvature on the Riemannian Poincaré disk:
    κ = 2 / (1 - ||z||^2)^2
directly in GPU vector registers in a single pass without intermediate memory allocations.
"""

import math
import time
import torch
import triton
import triton.language as tl

KB_T_LN2_300K = 2.87e-21  # Joules per bit at 300K (Landauer limit)


@triton.jit
def _fused_landauer_entropy_kernel(
    probs_curr_ptr,        # [BATCH, VOCAB_DIM] fp16
    probs_prev_ptr,        # [BATCH, VOCAB_DIM] fp16
    poincare_coords_ptr,   # [BATCH, 2] fp16 (x, y on Poincaré disk)
    dissipation_out_ptr,   # [BATCH] fp32 (Landauer energy dissipation in Joules)
    curvature_out_ptr,     # [BATCH] fp32 (Riemannian curvature)
    kl_div_out_ptr,        # [BATCH] fp32 (D_KL in bits)
    BATCH_SIZE,
    VOCAB_DIM: tl.constexpr, # e.g. 1024 or 2048
    BLOCK_SIZE: tl.constexpr,
):
    pid = tl.program_id(0)
    if pid >= BATCH_SIZE:
        return

    # 1. Compute D_KL(P_curr || P_prev) in SRAM across VOCAB_DIM
    kl_accum = 0.0
    for v_start in range(0, VOCAB_DIM, BLOCK_SIZE):
        v_offs = v_start + tl.arange(0, BLOCK_SIZE)
        v_mask = v_offs < VOCAB_DIM

        p = tl.load(probs_curr_ptr + pid * VOCAB_DIM + v_offs, mask=v_mask, other=1e-8).to(tl.float32)
        q = tl.load(probs_prev_ptr + pid * VOCAB_DIM + v_offs, mask=v_mask, other=1e-8).to(tl.float32)

        p = tl.maximum(p, 1e-8)
        q = tl.maximum(q, 1e-8)

        # KL in nats: p * ln(p / q)
        term = p * tl.log(p / q)
        kl_accum += tl.sum(tl.where(v_mask, term, 0.0))

    # Convert nats to bits: bits = nats / ln(2)
    inv_ln2 = 1.4426950408889634
    kl_bits = kl_accum * inv_ln2

    # Landauer dissipation: E = k_B T ln(2) * bits
    landauer_joules = kl_bits * 2.87e-21

    # 2. Compute Poincaré disk geodesic metric curvature
    px = tl.load(poincare_coords_ptr + pid * 2 + 0).to(tl.float32)
    py = tl.load(poincare_coords_ptr + pid * 2 + 1).to(tl.float32)

    norm_sq = px * px + py * py
    norm_sq = tl.minimum(norm_sq, 0.998) # clip to horizon

    denom = 1.0 - norm_sq
    # Metric scale factor lambda = 2 / (1 - ||z||^2)
    # Curvature scale: kappa = lambda^2
    curvature = (2.0 / denom) * (2.0 / denom)

    # Store outputs
    tl.store(dissipation_out_ptr + pid, landauer_joules)
    tl.store(curvature_out_ptr + pid, curvature)
    tl.store(kl_div_out_ptr + pid, kl_bits)


def triton_fused_landauer_entropy(
    probs_curr: torch.Tensor,
    probs_prev: torch.Tensor,
    poincare_coords: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """
    Computes thermodynamic Landauer dissipation and Poincaré curvature.
    probs_curr: [BATCH, VOCAB_DIM] fp16
    probs_prev: [BATCH, VOCAB_DIM] fp16
    poincare_coords: [BATCH, 2] fp16
    Returns: (dissipation: [BATCH] fp32, curvature: [BATCH] fp32, kl_bits: [BATCH] fp32)
    """
    assert probs_curr.is_cuda and probs_prev.is_cuda and poincare_coords.is_cuda
    batch_size, vocab_dim = probs_curr.shape

    dissipation = torch.empty(batch_size, device=probs_curr.device, dtype=torch.float32)
    curvature = torch.empty(batch_size, device=probs_curr.device, dtype=torch.float32)
    kl_div = torch.empty(batch_size, device=probs_curr.device, dtype=torch.float32)

    BLOCK_SIZE = 512
    grid = (batch_size,)

    _fused_landauer_entropy_kernel[grid](
        probs_curr,
        probs_prev,
        poincare_coords,
        dissipation,
        curvature,
        kl_div,
        batch_size,
        VOCAB_DIM=vocab_dim,
        BLOCK_SIZE=BLOCK_SIZE,
    )
    return dissipation, curvature, kl_div


def benchmark_landauer_kernel():
    if not torch.cuda.is_available():
        print("[!] CUDA not available, skipping hardware kernel benchmark.")
        return

    device = torch.device("cuda:0")
    batch_size = 8192  # 8k token transitions in flight
    vocab_dim = 2048   # 2048 top vocabulary slice

    print(f"[*] Benchmarking Fused Landauer Entropy & Poincaré Curvature Kernel ({batch_size:,} tokens, {vocab_dim} vocab)...")

    p_curr = torch.softmax(torch.randn(batch_size, vocab_dim, device=device, dtype=torch.float16), dim=-1)
    p_prev = torch.softmax(torch.randn(batch_size, vocab_dim, device=device, dtype=torch.float16), dim=-1)
    coords = torch.rand(batch_size, 2, device=device, dtype=torch.float16) * 0.9 - 0.45

    # Warmup
    for _ in range(5):
        _ = triton_fused_landauer_entropy(p_curr, p_prev, coords)
    torch.cuda.synchronize()

    # Timed run
    iters = 100
    t0 = time.perf_counter()
    for _ in range(iters):
        diss, curv, kl = triton_fused_landauer_entropy(p_curr, p_prev, coords)
    torch.cuda.synchronize()
    elapsed = (time.perf_counter() - t0) / iters

    tok_sec = batch_size / elapsed
    print(f"[✓] Kernel Execution Time: {elapsed * 1000:.3f} ms ({elapsed * 1e6:.1f} µs)")
    print(f"[✓] Thermodynamic Throughput: {tok_sec / 1e6:.2f} M token-transitions/sec")
    print(f"[✓] Mean Landauer Dissipation: {diss.mean().item():.3e} J/token (Mean KL: {kl.mean().item():.2f} bits)")
    print(f"[✓] Mean Poincaré Curvature: {curv.mean().item():.3f} (Max: {curv.max().item():.3f})")

    # Correctness verification vs PyTorch reference
    ref_kl_nats = torch.sum(p_curr.float() * (torch.log(p_curr.float() + 1e-8) - torch.log(p_prev.float() + 1e-8)), dim=-1)
    ref_kl_bits = ref_kl_nats / math.log(2)
    max_err = (kl - ref_kl_bits).abs().max().item()
    print(f"[✓] Max Absolute Numerical Difference vs Analytical KL: {max_err:.6e}")
    assert max_err < 1e-2, f"Numerical deviation too high: {max_err}"
    print("[✓] Correctness verification passed!")


if __name__ == "__main__":
    benchmark_landauer_kernel()
