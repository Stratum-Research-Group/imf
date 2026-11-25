"""
Fused Poincaré Cross-Scale Geodesic Feature Aggregator Kernel
=============================================================
Physical Workstation Benchmark: NVIDIA GeForce RTX 5060 Ti (SM 12.0)
Hardware Constrained: 16GB VRAM, 101KB Shared Memory Ceiling

Implements a fused cross-scale hyperbolic feature fusion layer on D^d_c.
Combines multiscale pyramid representations (G_coarse [B, N/2, D] and L_resid [B, N, D])
into a unified fine-scale representation:
1. Hyperbolic geodesic expansion of coarse token m = G_coarse[i // 2]
2. Fused non-Euclidean Möbius addition of bandpass residual L[i]:
   x_fine[i] = m (+) L[i]
3. Cross-scale adaptive gating:
   alpha_i = sigmoid( <m, L[i]> / tau )
   x_out[i] = alpha_i * x_fine[i] + (1 - alpha_i) * m
   with projective retraction to maintain ||x_out|| < 1/sqrt(c).
"""

import math
import time
import torch
import triton
import triton.language as tl

@triton.jit
def _poincare_cross_scale_aggregator_kernel(
    G_coarse_ptr,   # [B, N/2, D] float16 (coarse representations)
    L_resid_ptr,    # [B, N, D] float16 (bandpass residuals)
    Out_ptr,        # [B, N, D] float16 (reconstructed fine features)
    B: tl.constexpr,
    N: tl.constexpr,
    D: tl.constexpr,
    c: tl.constexpr,
    tau: tl.constexpr,
    stride_cb, stride_cn, stride_cd,
    stride_lb, stride_ln, stride_ld,
    stride_ob, stride_on, stride_od,
    BLOCK_D: tl.constexpr,
):
    pid_b = tl.program_id(0)
    pid_n = tl.program_id(1) # [0, N)

    d_offsets = tl.arange(0, BLOCK_D)
    mask_d = d_offsets < D

    # 1. Coarse index: pid_n // 2
    pid_coarse = pid_n // 2

    c_offset = pid_b * stride_cb + pid_coarse * stride_cn + d_offsets * stride_cd
    l_offset = pid_b * stride_lb + pid_n * stride_ln + d_offsets * stride_ld

    m = tl.load(G_coarse_ptr + c_offset, mask=mask_d, other=0.0).to(tl.float32)
    l = tl.load(L_resid_ptr + l_offset, mask=mask_d, other=0.0).to(tl.float32)

    # 2. Möbius addition: x_fine = m (+) l
    m_sq = tl.sum(m * m)
    l_sq = tl.sum(l * l)
    dot_ml = tl.sum(m * l)

    denom_m = tl.maximum(1.0 - c * m_sq, 1e-4)

    mob_num = (1.0 + 2.0 * c * dot_ml + c * l_sq) * m + denom_m * l
    mob_den = tl.maximum(1.0 + 2.0 * c * dot_ml + c * c * m_sq * l_sq, 1e-4)
    x_fine = mob_num / mob_den

    # 3. Adaptive cross-scale gating alpha = sigmoid(dot_ml / tau)
    scaled_dot = dot_ml / tau
    alpha = 1.0 / (1.0 + tl.exp(-scaled_dot))

    # Gated blend
    x_out = alpha * x_fine + (1.0 - alpha) * m

    # 4. Projective retraction onto open ball
    x_out_sq = tl.sum(x_out * x_out)
    max_sq = (1.0 / c) * 0.98
    if x_out_sq > max_sq:
        x_out = x_out * tl.sqrt(max_sq / x_out_sq)

    # Store reconstructed fine feature
    out_offset = pid_b * stride_ob + pid_n * stride_on + d_offsets * stride_od
    tl.store(Out_ptr + out_offset, x_out.to(tl.float16), mask=mask_d)


def triton_poincare_cross_scale_aggregator(g_coarse: torch.Tensor, l_resid: torch.Tensor, c: float = 1.0, tau: float = 0.5):
    B, N, D = l_resid.shape
    assert g_coarse.is_cuda and l_resid.is_cuda
    assert g_coarse.dtype == torch.float16 and l_resid.dtype == torch.float16
    assert g_coarse.shape[1] == N // 2

    out = torch.empty_like(l_resid)

    BLOCK_D = triton.next_power_of_2(D)
    grid = (B, N)

    _poincare_cross_scale_aggregator_kernel[grid](
        g_coarse, l_resid, out,
        B, N, D, c, tau,
        g_coarse.stride(0), g_coarse.stride(1), g_coarse.stride(2),
        l_resid.stride(0), l_resid.stride(1), l_resid.stride(2),
        out.stride(0), out.stride(1), out.stride(2),
        BLOCK_D=BLOCK_D,
        num_warps=4,
    )
    return out


def pytorch_poincare_cross_scale_aggregator_ref(g_coarse: torch.Tensor, l_resid: torch.Tensor, c: float = 1.0, tau: float = 0.5):
    B, N, D = l_resid.shape
    m_f = g_coarse.float().repeat_interleave(2, dim=1) # [B, N, D]
    l_f = l_resid.float()

    m_sq = torch.sum(m_f * m_f, dim=-1, keepdim=True)
    l_sq = torch.sum(l_f * l_f, dim=-1, keepdim=True)
    dot_ml = torch.sum(m_f * l_f, dim=-1, keepdim=True)

    denom_m = torch.clamp(1.0 - c * m_sq, min=1e-4)

    mob_num = (1.0 + 2.0 * c * dot_ml + c * l_sq) * m_f + denom_m * l_f
    mob_den = torch.clamp(1.0 + 2.0 * c * dot_ml + c * c * m_sq * l_sq, min=1e-4)
    x_fine = mob_num / mob_den

    alpha = torch.sigmoid(dot_ml / tau)
    x_out = alpha * x_fine + (1.0 - alpha) * m_f

    x_out_sq = torch.sum(x_out * x_out, dim=-1, keepdim=True)
    max_sq = (1.0 / c) * 0.98
    x_out = torch.where(x_out_sq > max_sq, x_out * torch.sqrt(max_sq / torch.clamp(x_out_sq, min=1e-5)), x_out)

    return x_out.half()


def benchmark():
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    print(f"[*] Benchmarking on: {torch.cuda.get_device_name(device)}")

    B, N, D = 16, 512, 128
    g_coarse = torch.randn(B, N // 2, D, device=device, dtype=torch.float16) * 0.1
    l_resid = torch.randn(B, N, D, device=device, dtype=torch.float16) * 0.05

    g_coarse = g_coarse / (torch.norm(g_coarse, dim=-1, keepdim=True) + 1.2)
    l_resid = l_resid / (torch.norm(l_resid, dim=-1, keepdim=True) + 1.2)

    # Correctness check
    out_tri = triton_poincare_cross_scale_aggregator(g_coarse, l_resid, c=1.0, tau=0.5)
    out_ref = pytorch_poincare_cross_scale_aggregator_ref(g_coarse, l_resid, c=1.0, tau=0.5)

    max_err = torch.max(torch.abs(out_tri - out_ref)).item()
    print(f"[+] Max Absolute Aggregation Error: {max_err:.6e}")
    assert max_err < 1e-4, f"Error too high: {max_err}"
    print("[✓] Poincaré Cross-Scale Feature Aggregator Correctness test PASSED.")

    # Benchmark
    warmup, iters = 20, 200
    for _ in range(warmup):
        _ = triton_poincare_cross_scale_aggregator(g_coarse, l_resid, c=1.0, tau=0.5)
        _ = pytorch_poincare_cross_scale_aggregator_ref(g_coarse, l_resid, c=1.0, tau=0.5)
    torch.cuda.synchronize()

    start_pt = time.perf_counter()
    for _ in range(iters):
        _ = pytorch_poincare_cross_scale_aggregator_ref(g_coarse, l_resid, c=1.0, tau=0.5)
    torch.cuda.synchronize()
    pt_time = (time.perf_counter() - start_pt) / iters

    start_tri = time.perf_counter()
    for _ in range(iters):
        _ = triton_poincare_cross_scale_aggregator(g_coarse, l_resid, c=1.0, tau=0.5)
    torch.cuda.synchronize()
    tri_time = (time.perf_counter() - start_tri) / iters

    speedup = pt_time / tri_time
    total_tokens = B * N
    throughput = total_tokens / tri_time

    print(f"[+] PyTorch Eager Latency: {pt_time * 1e6:.2f} µs")
    print(f"[+] Triton Fused Latency:  {tri_time * 1e6:.2f} µs")
    print(f"[+] Speedup Factor:        {speedup:.2f}x")
    print(f"[+] Processing Throughput: {throughput / 1e6:.2f}M tok/s")


if __name__ == "__main__":
    benchmark()
