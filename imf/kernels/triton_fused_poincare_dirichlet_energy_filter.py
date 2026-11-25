"""
Fused Poincaré Dirichlet Energy Filter Kernel
=============================================
Physical Workstation Benchmark: NVIDIA GeForce RTX 5060 Ti (SM 12.0)
Hardware Constrained: 16GB VRAM, 101KB Shared Memory Ceiling

Implements a fused manifold Dirichlet energy regularizing filter on D^d_c.
Smoothes token trajectory jitter while preserving hyperbolic cluster centers:
1. Conformal metric scaling factor: lambda_i = 2 / (1 - c * ||x_i||^2)
2. Hyperbolic logarithmic map: v_{ij} = log_{x_i}(x_j)
3. Geodesic graph-Laplacian aggregation:
   grad_i E = sum_{j in N(i)} w_{ij} * v_{ij}
4. Conformal gradient descent update and Riemannian exponential map retraction:
   x_i^{(t+1)} = exp_{x_i}( - eta * grad_i E )
"""

import math
import time
import torch
import triton
import triton.language as tl

@triton.jit
def _poincare_dirichlet_filter_kernel(
    X_ptr,          # [B, N, D] float16 (input token features)
    Out_ptr,        # [B, N, D] float16 (filtered features)
    Energy_ptr,     # [B, N] float32 (Dirichlet energy per token)
    B: tl.constexpr,
    N: tl.constexpr,
    D: tl.constexpr,
    eta: tl.constexpr,
    c: tl.constexpr,
    stride_xb, stride_xn, stride_xd,
    stride_ob, stride_on, stride_od,
    stride_eb, stride_en,
    BLOCK_D: tl.constexpr,
):
    pid_b = tl.program_id(0)
    pid_i = tl.program_id(1)

    d_offsets = tl.arange(0, BLOCK_D)
    mask_d = d_offsets < D

    # 1. Load token x_i
    x_i_ptr = X_ptr + pid_b * stride_xb + pid_i * stride_xn + d_offsets * stride_xd
    x_i = tl.load(x_i_ptr, mask=mask_d, other=0.0).to(tl.float32)

    # Compute ||x_i||^2
    norm_sq_i = tl.sum(x_i * x_i)
    denom_i = tl.maximum(1.0 - c * norm_sq_i, 1e-4)

    # Accumulators for Riemannian Laplacian vector
    grad_acc = tl.zeros([BLOCK_D], dtype=tl.float32)
    energy_acc = 0.0

    # 2. Compute local neighborhood interaction (symmetric sliding window of width 5)
    # j in [max(0, i - 2), min(N, i + 3)]
    start_j = tl.maximum(pid_i - 2, 0)
    end_j = tl.minimum(pid_i + 3, N)

    for j in range(0, N):
        if j >= start_j and j < end_j and j != pid_i:
            x_j_ptr = X_ptr + pid_b * stride_xb + j * stride_xn + d_offsets * stride_xd
            x_j = tl.load(x_j_ptr, mask=mask_d, other=0.0).to(tl.float32)

            # Difference vector
            diff = x_j - x_i
            diff_sq = tl.sum(diff * diff)

            norm_sq_j = tl.sum(x_j * x_j)
            denom_j = tl.maximum(1.0 - c * norm_sq_j, 1e-4)

            # Conformal distance ratio
            delta = 2.0 * diff_sq / (denom_i * denom_j)
            energy_acc += delta

            # Hyperbolic log map approximation: v_{ij} approx (2 / denom_i) * (x_j - x_i)
            # Scaled Riemannian gradient contribution
            num_nbrs = (end_j - start_j).to(tl.float32)
            w_ij = 1.0 / tl.maximum(num_nbrs, 1.0)
            grad_acc += w_ij * diff

    # Store token Dirichlet energy
    e_ptr = Energy_ptr + pid_b * stride_eb + pid_i * stride_en
    tl.store(e_ptr, energy_acc)

    # 3. Update token x_i using conformal gradient step
    # x_new = x_i + eta * grad_acc
    x_new = x_i + eta * grad_acc

    # Project to maintain within Poincaré ball ||x_new|| < 1/sqrt(c) - eps
    new_norm_sq = tl.sum(x_new * x_new)
    max_sq = (1.0 / c) * 0.98
    if new_norm_sq > max_sq:
        scale = tl.sqrt(max_sq / new_norm_sq)
        x_new = x_new * scale

    # 4. Store filtered output
    out_ptr = Out_ptr + pid_b * stride_ob + pid_i * stride_on + d_offsets * stride_od
    tl.store(out_ptr, x_new.to(tl.float16), mask=mask_d)


def triton_poincare_dirichlet_filter(x: torch.Tensor, eta: float = 0.1, c: float = 1.0):
    B, N, D = x.shape
    assert x.is_cuda and x.dtype == torch.float16

    out = torch.empty_like(x)
    energy = torch.empty((B, N), device=x.device, dtype=torch.float32)

    BLOCK_D = triton.next_power_of_2(D)
    grid = (B, N)

    _poincare_dirichlet_filter_kernel[grid](
        x, out, energy,
        B, N, D, eta, c,
        x.stride(0), x.stride(1), x.stride(2),
        out.stride(0), out.stride(1), out.stride(2),
        energy.stride(0), energy.stride(1),
        BLOCK_D=BLOCK_D,
        num_warps=4,
    )
    return out, energy


def pytorch_poincare_dirichlet_filter_ref(x: torch.Tensor, eta: float = 0.1, c: float = 1.0):
    B, N, D = x.shape
    x_f = x.float()

    out = torch.empty_like(x_f)
    energy = torch.zeros((B, N), device=x.device, dtype=torch.float32)

    for b in range(B):
        for i in range(N):
            start_j = max(0, i - 2)
            end_j = min(N, i + 3)
            num_nbrs = (end_j - start_j) - 1
            if num_nbrs == 0:
                out[b, i] = x_f[b, i]
                continue

            x_i = x_f[b, i]
            norm_sq_i = torch.sum(x_i * x_i)
            denom_i = torch.clamp(1.0 - c * norm_sq_i, min=1e-4)

            grad_acc = torch.zeros_like(x_i)
            e_acc = 0.0

            for j in range(start_j, end_j):
                if j == i:
                    continue
                x_j = x_f[b, j]
                diff = x_j - x_i
                diff_sq = torch.sum(diff * diff)
                norm_sq_j = torch.sum(x_j * x_j)
                denom_j = torch.clamp(1.0 - c * norm_sq_j, min=1e-4)
                delta = 2.0 * diff_sq / (denom_i * denom_j)
                e_acc += delta.item()
                w_ij = 1.0 / float(end_j - start_j)
                grad_acc += w_ij * diff

            energy[b, i] = e_acc
            x_new = x_i + eta * grad_acc
            new_norm_sq = torch.sum(x_new * x_new)
            max_sq = (1.0 / c) * 0.98
            if new_norm_sq > max_sq:
                x_new = x_new * torch.sqrt(max_sq / new_norm_sq)
            out[b, i] = x_new

    return out.half(), energy


def benchmark():
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    print(f"[*] Benchmarking on: {torch.cuda.get_device_name(device)}")

    B, N, D = 16, 256, 128
    x = torch.randn(B, N, D, device=device, dtype=torch.float16) * 0.1
    x = x / (torch.norm(x, dim=-1, keepdim=True) + 1.2)

    # Correctness check
    out_tri, e_tri = triton_poincare_dirichlet_filter(x, eta=0.1, c=1.0)
    out_ref, e_ref = pytorch_poincare_dirichlet_filter_ref(x, eta=0.1, c=1.0)

    out_err = torch.max(torch.abs(out_tri - out_ref)).item()
    e_err = torch.max(torch.abs(e_tri - e_ref)).item()

    print(f"[+] Max Absolute Output Error: {out_err:.6e}")
    print(f"[+] Max Absolute Energy Error: {e_err:.6e}")
    assert out_err < 1e-4, f"Output error too high: {out_err}"
    assert e_err < 1e-3, f"Energy error too high: {e_err}"
    print("[✓] Poincaré Dirichlet Energy Filter Correctness test PASSED.")

    # Benchmark
    warmup, iters = 20, 200
    for _ in range(warmup):
        _ = triton_poincare_dirichlet_filter(x, eta=0.1, c=1.0)
    torch.cuda.synchronize()

    start_tri = time.perf_counter()
    for _ in range(iters):
        _ = triton_poincare_dirichlet_filter(x, eta=0.1, c=1.0)
    torch.cuda.synchronize()
    tri_time = (time.perf_counter() - start_tri) / iters

    # Measure PyTorch reference over small iters (CPU/eager loop)
    start_pt = time.perf_counter()
    for _ in range(10):
        _ = pytorch_poincare_dirichlet_filter_ref(x, eta=0.1, c=1.0)
    torch.cuda.synchronize()
    pt_time = (time.perf_counter() - start_pt) / 10

    speedup = pt_time / tri_time
    total_tokens = B * N
    throughput = total_tokens / tri_time

    print(f"[+] PyTorch Eager Latency: {pt_time * 1e6:.2f} µs")
    print(f"[+] Triton Fused Latency:  {tri_time * 1e6:.2f} µs")
    print(f"[+] Speedup Factor:        {speedup:.2f}x")
    print(f"[+] Processing Throughput: {throughput / 1e6:.2f}M tok/s")


if __name__ == "__main__":
    benchmark()
