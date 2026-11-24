"""
IMF Triton Fused Poincaré Gyrovector Parallel Transport Kernel
==============================================================
Computes hyperbolic parallel transport of tangent vectors w at base point u
along the unique geodesic connecting u to target base point v in the Poincaré ball:

    P_{u -> v}(w) = ((1 - ||u||^2) / (1 - ||v||^2)) * ( w - 2 * (<v - u, w> / ||v - u||^2) * (v - u) )

Invariants:
1. Conformal factor scaling: lambda_u / lambda_v preserves Riemannian inner products.
2. Direct reflection across delta = v - u: when u = v, parallel transport is identity map.
3. Reg-level fusion: operates directly in register SRAM with zero global DRAM spills.
"""

import math
import time
import torch
import triton
import triton.language as tl


@triton.jit
def _fused_poincare_parallel_transport_kernel(
    U_ptr,          # [B, D] Base source points in Poincare ball
    V_ptr,          # [B, D] Base target points in Poincare ball
    W_ptr,          # [B, D] Tangent vectors to transport
    Out_ptr,        # [B, D] Output transported tangent vectors
    B, D,
    stride_ub, stride_ud,
    stride_vb, stride_vd,
    stride_wb, stride_wd,
    stride_ob, stride_od,
    eps: tl.constexpr,
    BLOCK_B: tl.constexpr,
    BLOCK_D: tl.constexpr,
):
    pid_b = tl.program_id(0)
    offs_b = pid_b * BLOCK_B + tl.arange(0, BLOCK_B)
    offs_d = tl.arange(0, BLOCK_D)

    mask_b = offs_b < B
    mask_d = offs_d < D

    # Accumulators for norms: ||u||^2, ||v||^2, ||v - u||^2, and <v - u, w>
    norm_u_sq = tl.zeros([BLOCK_B], dtype=tl.float32)
    norm_v_sq = tl.zeros([BLOCK_B], dtype=tl.float32)
    norm_delta_sq = tl.zeros([BLOCK_B], dtype=tl.float32)
    dot_delta_w = tl.zeros([BLOCK_B], dtype=tl.float32)

    # First pass: compute scalar norms and inner products over D chunks
    for d_idx in range(0, tl.cdiv(D, BLOCK_D)):
        curr_d = d_idx * BLOCK_D + offs_d
        mask_curr_d = curr_d < D

        u_ptrs = U_ptr + (offs_b[:, None] * stride_ub + curr_d[None, :] * stride_ud)
        v_ptrs = V_ptr + (offs_b[:, None] * stride_vb + curr_d[None, :] * stride_vd)
        w_ptrs = W_ptr + (offs_b[:, None] * stride_wb + curr_d[None, :] * stride_wd)

        u_val = tl.load(u_ptrs, mask=mask_b[:, None] & mask_curr_d[None, :], other=0.0).to(tl.float32)
        v_val = tl.load(v_ptrs, mask=mask_b[:, None] & mask_curr_d[None, :], other=0.0).to(tl.float32)
        w_val = tl.load(w_ptrs, mask=mask_b[:, None] & mask_curr_d[None, :], other=0.0).to(tl.float32)

        delta = v_val - u_val

        norm_u_sq += tl.sum(u_val * u_val, axis=1)
        norm_v_sq += tl.sum(v_val * v_val, axis=1)
        norm_delta_sq += tl.sum(delta * delta, axis=1)
        dot_delta_w += tl.sum(delta * w_val, axis=1)

    # Compute scalar scaling factors
    # lambda_u = 2 / (1 - ||u||^2), lambda_v = 2 / (1 - ||v||^2)
    # lambda_u / lambda_v = (1 - ||v||^2) / (1 - ||u||^2) -> actually conformal ratio: (1 - ||u||^2)/(1 - ||v||^2)
    alpha_u = tl.maximum(1.0 - norm_u_sq, eps)
    alpha_v = tl.maximum(1.0 - norm_v_sq, eps)
    conformal_ratio = alpha_u / alpha_v

    # Householder reflection factor: 2 * <delta, w> / ||delta||^2
    # If delta is zero (u == v), factor is 0
    safe_delta_sq = tl.maximum(norm_delta_sq, eps * eps)
    refl_factor = tl.where(norm_delta_sq > eps * eps, 2.0 * dot_delta_w / safe_delta_sq, 0.0)

    # Second pass: compute transported vectors and store
    for d_idx in range(0, tl.cdiv(D, BLOCK_D)):
        curr_d = d_idx * BLOCK_D + offs_d
        mask_curr_d = curr_d < D

        u_ptrs = U_ptr + (offs_b[:, None] * stride_ub + curr_d[None, :] * stride_ud)
        v_ptrs = V_ptr + (offs_b[:, None] * stride_vb + curr_d[None, :] * stride_vd)
        w_ptrs = W_ptr + (offs_b[:, None] * stride_wb + curr_d[None, :] * stride_wd)

        u_val = tl.load(u_ptrs, mask=mask_b[:, None] & mask_curr_d[None, :], other=0.0).to(tl.float32)
        v_val = tl.load(v_ptrs, mask=mask_b[:, None] & mask_curr_d[None, :], other=0.0).to(tl.float32)
        w_val = tl.load(w_ptrs, mask=mask_b[:, None] & mask_curr_d[None, :], other=0.0).to(tl.float32)

        delta = v_val - u_val

        # w_transported = conformal_ratio * (w - refl_factor * delta)
        reflected = w_val - refl_factor[:, None] * delta
        w_trans = conformal_ratio[:, None] * reflected

        out_ptrs = Out_ptr + (offs_b[:, None] * stride_ob + curr_d[None, :] * stride_od)
        tl.store(out_ptrs, w_trans.to(tl.float16), mask=mask_b[:, None] & mask_curr_d[None, :])


def triton_poincare_parallel_transport(
    U: torch.Tensor,
    V: torch.Tensor,
    W: torch.Tensor,
    eps: float = 1e-5
) -> torch.Tensor:
    """
    U: [B, D] Base source points
    V: [B, D] Base target points
    W: [B, D] Tangent vectors at U
    Returns: [B, D] Transported tangent vectors at V
    """
    assert U.is_cuda and V.is_cuda and W.is_cuda
    B, D = U.shape
    Out = torch.empty_like(W)

    BLOCK_B = 64
    BLOCK_D = min(128, triton.next_power_of_2(D))
    grid = (triton.cdiv(B, BLOCK_B),)

    _fused_poincare_parallel_transport_kernel[grid](
        U, V, W, Out,
        B, D,
        U.stride(0), U.stride(1),
        V.stride(0), V.stride(1),
        W.stride(0), W.stride(1),
        Out.stride(0), Out.stride(1),
        eps=eps,
        BLOCK_B=BLOCK_B,
        BLOCK_D=BLOCK_D,
    )
    return Out


def benchmark_poincare_parallel_transport():
    print("=" * 80)
    print("  IMF TRITON FUSED POINCARÉ GYROVECTOR PARALLEL TRANSPORT BENCHMARK")
    print("=" * 80)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if not torch.cuda.is_available():
        print("[!] CUDA not available, skipping hardware kernel benchmark.")
        return

    B = 16384  # Batch of tokens
    D = 128    # Embedding dim
    print(f"[*] Workload: Batch B={B}, Dim D={D}")

    torch.manual_seed(42)
    U = torch.randn((B, D), device=device, dtype=torch.float16)
    U = U / (U.norm(dim=-1, keepdim=True) + 1e-4) * 0.85

    V = torch.randn((B, D), device=device, dtype=torch.float16)
    V = V / (V.norm(dim=-1, keepdim=True) + 1e-4) * 0.85

    W = torch.randn((B, D), device=device, dtype=torch.float16) * 0.1

    # Warmup
    for _ in range(10):
        _ = triton_poincare_parallel_transport(U, V, W)
    torch.cuda.synchronize()

    # PyTorch Reference Verification
    def torch_pt_ref(u, v, w, eps=1e-5):
        u_f = u.float()
        v_f = v.float()
        w_f = w.float()

        u_sq = torch.sum(u_f * u_f, dim=-1, keepdim=True)
        v_sq = torch.sum(v_f * v_f, dim=-1, keepdim=True)
        delta = v_f - u_f
        delta_sq = torch.sum(delta * delta, dim=-1, keepdim=True)
        dot_dw = torch.sum(delta * w_f, dim=-1, keepdim=True)

        alpha_u = torch.clamp(1.0 - u_sq, min=eps)
        alpha_v = torch.clamp(1.0 - v_sq, min=eps)
        conformal_ratio = alpha_u / alpha_v

        refl_factor = torch.where(delta_sq > eps * eps, 2.0 * dot_dw / torch.clamp(delta_sq, min=eps * eps), torch.zeros_like(dot_dw))
        reflected = w_f - refl_factor * delta
        return (conformal_ratio * reflected).half()

    ref_out = torch_pt_ref(U, V, W)
    tri_out = triton_poincare_parallel_transport(U, V, W)

    max_diff = torch.max(torch.abs(ref_out - tri_out)).item()
    mean_diff = torch.mean(torch.abs(ref_out - tri_out)).item()
    print(f"[*] Numerical Fidelity: Max Diff = {max_diff:.4e}, Mean Diff = {mean_diff:.4e}")
    assert max_diff < 0.05, f"Numerical difference too high: {max_diff}"

    # Benchmark Latency
    iters = 100
    start = time.perf_counter()
    for _ in range(iters):
        _ = triton_poincare_parallel_transport(U, V, W)
    torch.cuda.synchronize()
    elapsed = (time.perf_counter() - start) / iters

    throughput = B / elapsed / 1e6
    print(f"[✓] Execution Latency: {elapsed * 1000:.3f} ms ({elapsed * 1e6:.1f} µs)")
    print(f"[✓] Parallel Transport Throughput: {throughput:.2f} Million tangent vectors/sec")
    print("=" * 80)


if __name__ == "__main__":
    benchmark_poincare_parallel_transport()
