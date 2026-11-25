"""
Physical Workstation Triton Kernel: Fused Poincaré Multi-Head Latent Attention (MLA) Kernel (Cycle 215)
Hardware Target: NVIDIA GeForce RTX 5060 Ti (AD106, SM 12.0), 16GB VRAM.

Optimized MLA execution: pre-project Query head into compressed latent space [B, H_Q, D_C]
once per step, and then evaluate fused GEMV against cached tokens across the sequence length S.
"""

import time
import torch
import triton
import triton.language as tl

@triton.jit
def fused_mla_score_kernel(
    Q_proj_ptr,     # [B, H_Q, D_C] Pre-projected query heads
    C_KV_ptr,       # [B, S, D_C] Compressed KV latent cache
    Scores_ptr,     # [B, H_Q, S] Output attention logits
    scale: tl.constexpr,
    B: tl.constexpr,
    S: tl.constexpr,
    H_Q: tl.constexpr,
    D_C: tl.constexpr,
    BLOCK_S: tl.constexpr,
):
    pid_b = tl.program_id(0)
    pid_h = tl.program_id(1)
    pid_s = tl.program_id(2)

    s_idx = pid_s * BLOCK_S + tl.arange(0, BLOCK_S)
    s_mask = s_idx < S

    # Load Q_proj for this batch and head [D_C]
    # D_C is typically 256, perfectly fitting inside registers
    acc = tl.zeros([BLOCK_S], dtype=tl.float32)

    for dc_offset in range(0, D_C, 64):
        dc_idx = dc_offset + tl.arange(0, 64)
        dc_mask = dc_idx < D_C

        q_val = tl.load(
            Q_proj_ptr + pid_b * (H_Q * D_C) + pid_h * D_C + dc_idx,
            mask=dc_mask,
            other=0.0
        ) # [64]

        # Load block of C_KV: [BLOCK_S, 64]
        c_kv = tl.load(
            C_KV_ptr + pid_b * (S * D_C) + s_idx[:, None] * D_C + dc_idx[None, :],
            mask=s_mask[:, None] & dc_mask[None, :],
            other=0.0
        ) # [BLOCK_S, 64]

        acc += tl.sum(c_kv * q_val[None, :], axis=1)

    out_offset = pid_b * (H_Q * S) + pid_h * S + s_idx
    tl.store(Scores_ptr + out_offset, acc * scale, mask=s_mask)


def run_benchmark():
    assert torch.cuda.is_available(), "Physical workstation GPU required"
    device = torch.device("cuda:0")

    B = 4          # Batch size
    S = 1024       # Context length (1,024 cached tokens)
    H_Q = 16       # 16 Query attention heads
    D_H = 128      # Head dimension
    D_C = 256      # Compressed latent dimension (8x compression)
    scale = float(1.0 / (D_H ** 0.5))

    torch.manual_seed(42)
    q = torch.randn(B, H_Q, D_H, device=device, dtype=torch.float32)
    c_kv = torch.randn(B, S, D_C, device=device, dtype=torch.float32)
    w_uk = torch.randn(H_Q, D_H, D_C, device=device, dtype=torch.float32) * 0.1

    # Pre-project query
    q_proj = torch.einsum("bhd,hdc->bhc", q, w_uk).contiguous()

    # PyTorch reference
    def ref_mla(q_proj, c_kv, scale):
        scores = torch.einsum("bhc,bsc->bhs", q_proj, c_kv)
        return scores * scale

    for _ in range(10):
        ref_out = ref_mla(q_proj, c_kv, scale)
    torch.cuda.synchronize()

    t0 = time.perf_counter()
    iters = 100
    for _ in range(iters):
        ref_out = ref_mla(q_proj, c_kv, scale)
    torch.cuda.synchronize()
    ref_time = (time.perf_counter() - t0) / iters

    out = torch.empty(B, H_Q, S, device=device, dtype=torch.float32)
    BLOCK_S = 64
    grid = (B, H_Q, (S + BLOCK_S - 1) // BLOCK_S)

    for _ in range(10):
        fused_mla_score_kernel[grid](
            q_proj, c_kv, out, scale, B, S, H_Q, D_C, BLOCK_S
        )
    torch.cuda.synchronize()

    t0 = time.perf_counter()
    for _ in range(iters):
        fused_mla_score_kernel[grid](
            q_proj, c_kv, out, scale, B, S, H_Q, D_C, BLOCK_S
        )
    torch.cuda.synchronize()
    triton_time = (time.perf_counter() - t0) / iters

    max_err = torch.max(torch.abs(out - ref_out)).item()
    speedup = ref_time / triton_time
    total_tokens = B * S
    throughput = (total_tokens * H_Q) / triton_time / 1e6
    uncompressed_kv_bytes = B * S * H_Q * D_H * 2
    compressed_kv_bytes = B * S * D_C * 2
    kv_cache_saving = uncompressed_kv_bytes / compressed_kv_bytes

    print(f"=== Workstation Benchmark: Cycle 215 Fused Multi-Head Latent Attention (MLA) ===")
    print(f"Hardware: {torch.cuda.get_device_name(0)}")
    print(f"Batch: {B}, Context: {S}, Heads: {H_Q}, Head Dim: {D_H}, Latent Dim: {D_C}")
    print(f"KV Cache Compression Ratio: {kv_cache_saving:.2f}x (Saves {(1.0 - 1.0/kv_cache_saving)*100:.1f}% VRAM)")
    print(f"PyTorch baseline latency:   {ref_time*1e6:.2f} us")
    print(f"Triton fused latency:       {triton_time*1e6:.2f} us")
    print(f"Speedup factor:             {speedup:.2f}x")
    print(f"Attention Throughput:       {throughput:.2f} M head-tokens/s")
    print(f"Max Absolute Error:         {max_err:.2e}")
    assert max_err < 1e-4, f"Tolerance exceeded: {max_err}"
    print("PHYSICAL HARDWARE TEST PASSED")

if __name__ == "__main__":
    run_benchmark()
