"""
Fused Poincaré Hyperbolic Laplacian Pyramid Kernel
===================================================
Physical Workstation Benchmark: NVIDIA GeForce RTX 5060 Ti (SM 12.0)
Hardware Constrained: 16GB VRAM, 101KB Shared Memory Ceiling

Implements a fused multi-resolution Laplacian pyramid decomposition on D^d_c.
Constructs:
1. Coarse approximation: G_{k+1}[i] = Geodesic_Midpoint( G_k[2i], G_k[2i+1] )
2. Expanded prediction: Expand(G_{k+1}) via hyperbolic geodesic interpolation
3. Bandpass Laplacian residual:
   L_k[i] = G_k[i] (-) Expand(G_{k+1})[i]
   using exact Möbius subtraction: a (-) b = a (+) (-b).
"""

import math
import time
import torch
import triton
import triton.language as tl

@triton.jit
def _poincare_laplacian_pyramid_kernel(
    G_in_ptr,       # [B, N, D] float16 (fine-level tokens G_0)
    G_coarse_ptr,   # [B, N/2, D] float16 (coarse tokens G_1)
    L_resid_ptr,    # [B, N, D] float16 (Laplacian bandpass residuals L_0)
    B: tl.constexpr,
    N: tl.constexpr,
    D: tl.constexpr,
    c: tl.constexpr,
    stride_gb, stride_gn, stride_gd,
    stride_cb, stride_cn, stride_cd,
    stride_lb, stride_ln, stride_ld,
    BLOCK_D: tl.constexpr,
):
    pid_b = tl.program_id(0)
    pid_coarse = tl.program_id(1) # [0, N/2)

    d_offsets = tl.arange(0, BLOCK_D)
    mask_d = d_offsets < D

    # 1. Load fine tokens: x0 = G[2i], x1 = G[2i + 1]
    i0 = pid_coarse * 2
    i1 = i0 + 1

    x0_ptr = G_in_ptr + pid_b * stride_gb + i0 * stride_gn + d_offsets * stride_gd
    x1_ptr = G_in_ptr + pid_b * stride_gb + i1 * stride_gn + d_offsets * stride_gd

    x0 = tl.load(x0_ptr, mask=mask_d, other=0.0).to(tl.float32)
    x1 = tl.load(x1_ptr, mask=mask_d, other=0.0).to(tl.float32)

    # 2. Hyperbolic geodesic midpoint m = 0.5 * (x0 (+) x1)
    # Using weighted Möbius midpoint: m = (x0 + x1) / (1 + sqrt( (1 - c ||x0||^2)(1 - c ||x1||^2) ) + c <x0, x1>)
    dot_01 = tl.sum(x0 * x1)
    norm_sq_0 = tl.sum(x0 * x0)
    norm_sq_1 = tl.sum(x1 * x1)

    conf_0 = tl.maximum(1.0 - c * norm_sq_0, 1e-4)
    conf_1 = tl.maximum(1.0 - c * norm_sq_1, 1e-4)
    denom_mid = tl.maximum(1.0 + tl.sqrt(conf_0 * conf_1) + c * dot_01, 1e-4)
    m = (x0 + x1) / denom_mid

    # Project m inside ball
    m_sq = tl.sum(m * m)
    max_sq = (1.0 / c) * 0.98
    if m_sq > max_sq:
        m = m * tl.sqrt(max_sq / m_sq)

    # Store coarse token G_1
    c_ptr = G_coarse_ptr + pid_b * stride_cb + pid_coarse * stride_cn + d_offsets * stride_cd
    tl.store(c_ptr, m.to(tl.float16), mask=mask_d)

    # 3. Expand prediction: both positions i0 and i1 predict m
    # Compute Laplacian residuals:
    # L[i0] = x0 (-) m = x0 (+) (-m)
    # L[i1] = x1 (-) m = x1 (+) (-m)
    # Möbius addition a (+) b = ( (1 + 2c <a, b> + c ||b||^2) a + (1 - c ||a||^2) b ) / ( 1 + 2c <a, b> + c^2 ||a||^2 ||b||^2 )

    # Residual for i0:
    dot_0_negm = -tl.sum(x0 * m)
    num_0 = (1.0 + 2.0 * c * dot_0_negm + c * m_sq) * x0 - conf_0 * m
    den_0 = tl.maximum(1.0 + 2.0 * c * dot_0_negm + c * c * norm_sq_0 * m_sq, 1e-4)
    l0 = num_0 / den_0

    # Residual for i1:
    dot_1_negm = -tl.sum(x1 * m)
    num_1 = (1.0 + 2.0 * c * dot_1_negm + c * m_sq) * x1 - conf_1 * m
    den_1 = tl.maximum(1.0 + 2.0 * c * dot_1_negm + c * c * norm_sq_1 * m_sq, 1e-4)
    l1 = num_1 / den_1

    # Store residuals
    l0_ptr = L_resid_ptr + pid_b * stride_lb + i0 * stride_ln + d_offsets * stride_ld
    l1_ptr = L_resid_ptr + pid_b * stride_lb + i1 * stride_ln + d_offsets * stride_ld

    tl.store(l0_ptr, l0.to(tl.float16), mask=mask_d)
    tl.store(l1_ptr, l1.to(tl.float16), mask=mask_d)


def triton_poincare_laplacian_pyramid(x: torch.Tensor, c: float = 1.0):
    B, N, D = x.shape
    assert x.is_cuda and x.dtype == torch.float16
    assert N % 2 == 0, "Sequence length must be even"

    g_coarse = torch.empty((B, N // 2, D), device=x.device, dtype=torch.float16)
    l_resid = torch.empty((B, N, D), device=x.device, dtype=torch.float16)

    BLOCK_D = triton.next_power_of_2(D)
    grid = (B, N // 2)

    _poincare_laplacian_pyramid_kernel[grid](
        x, g_coarse, l_resid,
        B, N, D, c,
        x.stride(0), x.stride(1), x.stride(2),
        g_coarse.stride(0), g_coarse.stride(1), g_coarse.stride(2),
        l_resid.stride(0), l_resid.stride(1), l_resid.stride(2),
        BLOCK_D=BLOCK_D,
        num_warps=4,
    )
    return g_coarse, l_resid


def pytorch_poincare_laplacian_pyramid_ref(x: torch.Tensor, c: float = 1.0):
    B, N, D = x.shape
    x_f = x.float()

    x0 = x_f[:, 0::2, :] # [B, N/2, D]
    x1 = x_f[:, 1::2, :] # [B, N/2, D]

    dot_01 = torch.sum(x0 * x1, dim=-1, keepdim=True)
    norm_sq_0 = torch.sum(x0 * x0, dim=-1, keepdim=True)
    norm_sq_1 = torch.sum(x1 * x1, dim=-1, keepdim=True)

    conf_0 = torch.clamp(1.0 - c * norm_sq_0, min=1e-4)
    conf_1 = torch.clamp(1.0 - c * norm_sq_1, min=1e-4)
    denom_mid = torch.clamp(1.0 + torch.sqrt(conf_0 * conf_1) + c * dot_01, min=1e-4)
    m = (x0 + x1) / denom_mid

    m_sq = torch.sum(m * m, dim=-1, keepdim=True)
    max_sq = (1.0 / c) * 0.98
    m = torch.where(m_sq > max_sq, m * torch.sqrt(max_sq / torch.clamp(m_sq, min=1e-5)), m)

    # Residuals
    dot_0_negm = -torch.sum(x0 * m, dim=-1, keepdim=True)
    num_0 = (1.0 + 2.0 * c * dot_0_negm + c * m_sq) * x0 - conf_0 * m
    den_0 = torch.clamp(1.0 + 2.0 * c * dot_0_negm + c * c * norm_sq_0 * m_sq, min=1e-4)
    l0 = num_0 / den_0

    dot_1_negm = -torch.sum(x1 * m, dim=-1, keepdim=True)
    num_1 = (1.0 + 2.0 * c * dot_1_negm + c * m_sq) * x1 - conf_1 * m
    den_1 = torch.clamp(1.0 + 2.0 * c * dot_1_negm + c * c * norm_sq_1 * m_sq, min=1e-4)
    l1 = num_1 / den_1

    l_resid = torch.empty_like(x_f)
    l_resid[:, 0::2, :] = l0
    l_resid[:, 1::2, :] = l1

    return m.half(), l_resid.half()


def benchmark():
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    print(f"[*] Benchmarking on: {torch.cuda.get_device_name(device)}")

    B, N, D = 16, 512, 128
    x = torch.randn(B, N, D, device=device, dtype=torch.float16) * 0.1
    x = x / (torch.norm(x, dim=-1, keepdim=True) + 1.2)

    # Correctness check
    g_tri, l_tri = triton_poincare_laplacian_pyramid(x, c=1.0)
    g_ref, l_ref = pytorch_poincare_laplacian_pyramid_ref(x, c=1.0)

    g_err = torch.max(torch.abs(g_tri - g_ref)).item()
    l_err = torch.max(torch.abs(l_tri - l_ref)).item()

    print(f"[+] Max Absolute Coarse Token Error: {g_err:.6e}")
    print(f"[+] Max Absolute Residual Error:     {l_err:.6e}")
    assert g_err < 1e-4, f"Coarse error too high: {g_err}"
    assert l_err < 1e-4, f"Residual error too high: {l_err}"
    print("[✓] Poincaré Laplacian Pyramid Correctness test PASSED.")

    # Benchmark
    warmup, iters = 20, 200
    for _ in range(warmup):
        _ = triton_poincare_laplacian_pyramid(x, c=1.0)
        _ = pytorch_poincare_laplacian_pyramid_ref(x, c=1.0)
    torch.cuda.synchronize()

    start_pt = time.perf_counter()
    for _ in range(iters):
        _ = pytorch_poincare_laplacian_pyramid_ref(x, c=1.0)
    torch.cuda.synchronize()
    pt_time = (time.perf_counter() - start_pt) / iters

    start_tri = time.perf_counter()
    for _ in range(iters):
        _ = triton_poincare_laplacian_pyramid(x, c=1.0)
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
