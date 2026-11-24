"""
IMF Triton Fused Poincaré Logarithmic Map Kernel
================================================
Computes the Riemannian logarithmic map log_u(v) in the Poincaré ball:
    log_u(v) = (2 / lambda_u) * artanh(|| -u \oplus v ||) * ((-u \oplus v) / || -u \oplus v ||)

where:
    lambda_u = 2 / (1 - ||u||^2)
    -u \oplus v = ((1 + 2<u, v> + ||v||^2) * (-u) + (1 - ||u||^2) * v) / (1 + 2<u, v> + ||u||^2 ||v||^2)

Maps points v on the Poincaré manifold back to the tangent space T_u D^D
at base point u for Euclidean gradient backpropagation and AdamW updates.
"""

import math
import time
import torch
import triton
import triton.language as tl


@triton.jit
def _fused_poincare_log_map_kernel(
    U_ptr,          # [B, D] Base points in Poincare ball
    V_ptr,          # [B, D] Target manifold points in Poincare ball
    Out_ptr,        # [B, D] Output tangent vectors in T_u D^D
    B, D,
    stride_ub, stride_ud,
    stride_vb, stride_vd,
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

    # Accumulators for norms: ||u||^2, ||v||^2, <u, v>
    norm_u_sq = tl.zeros([BLOCK_B], dtype=tl.float32)
    norm_v_sq = tl.zeros([BLOCK_B], dtype=tl.float32)
    dot_uv = tl.zeros([BLOCK_B], dtype=tl.float32)

    # First pass: compute scalar inner products over D chunks
    for d_idx in range(0, tl.cdiv(D, BLOCK_D)):
        curr_d = d_idx * BLOCK_D + offs_d
        mask_curr_d = curr_d < D

        u_ptrs = U_ptr + (offs_b[:, None] * stride_ub + curr_d[None, :] * stride_ud)
        v_ptrs = V_ptr + (offs_b[:, None] * stride_vb + curr_d[None, :] * stride_vd)

        u_val = tl.load(u_ptrs, mask=mask_b[:, None] & mask_curr_d[None, :], other=0.0).to(tl.float32)
        v_val = tl.load(v_ptrs, mask=mask_b[:, None] & mask_curr_d[None, :], other=0.0).to(tl.float32)

        norm_u_sq += tl.sum(u_val * u_val, axis=1)
        norm_v_sq += tl.sum(v_val * v_val, axis=1)
        dot_uv += tl.sum(u_val * v_val, axis=1)

    # Conformal factors
    alpha_u = tl.maximum(1.0 - norm_u_sq, eps)
    # Gyroaddition denominator: D_add = 1 + 2<u, v> + ||u||^2 ||v||^2
    denom_add = tl.maximum(1.0 + 2.0 * dot_uv + norm_u_sq * norm_v_sq, eps)

    # Scalar coefficients for -u \oplus v:
    # coeff_neg_u = (1 + 2<u, v> + ||v||^2) / denom_add
    # coeff_v = (1 - ||u||^2) / denom_add
    c_u = (1.0 + 2.0 * dot_uv + norm_v_sq) / denom_add
    c_v = alpha_u / denom_add

    # Pass 2: compute the norm of delta = -u \oplus v
    norm_delta_sq = tl.zeros([BLOCK_B], dtype=tl.float32)
    for d_idx in range(0, tl.cdiv(D, BLOCK_D)):
        curr_d = d_idx * BLOCK_D + offs_d
        mask_curr_d = curr_d < D

        u_ptrs = U_ptr + (offs_b[:, None] * stride_ub + curr_d[None, :] * stride_ud)
        v_ptrs = V_ptr + (offs_b[:, None] * stride_vb + curr_d[None, :] * stride_vd)

        u_val = tl.load(u_ptrs, mask=mask_b[:, None] & mask_curr_d[None, :], other=0.0).to(tl.float32)
        v_val = tl.load(v_ptrs, mask=mask_b[:, None] & mask_curr_d[None, :], other=0.0).to(tl.float32)

        delta = -c_u[:, None] * u_val + c_v[:, None] * v_val
        norm_delta_sq += tl.sum(delta * delta, axis=1)

    norm_delta = tl.sqrt(tl.maximum(norm_delta_sq, 0.0))
    # artanh(x) = 0.5 * ln((1 + x) / (1 - x))
    safe_norm = tl.minimum(norm_delta, 1.0 - eps)
    artanh_val = 0.5 * tl.log((1.0 + safe_norm) / tl.maximum(1.0 - safe_norm, eps))

    # Scale factor = (2 / lambda_u) * (artanh(||delta||) / ||delta||)
    # lambda_u = 2 / alpha_u => 2 / lambda_u = alpha_u
    # scale = alpha_u * artanh(||delta||) / ||delta||
    scale = tl.where(norm_delta > eps, alpha_u * artanh_val / norm_delta, alpha_u)

    # Pass 3: write out scaled delta
    for d_idx in range(0, tl.cdiv(D, BLOCK_D)):
        curr_d = d_idx * BLOCK_D + offs_d
        mask_curr_d = curr_d < D

        u_ptrs = U_ptr + (offs_b[:, None] * stride_ub + curr_d[None, :] * stride_ud)
        v_ptrs = V_ptr + (offs_b[:, None] * stride_vb + curr_d[None, :] * stride_vd)

        u_val = tl.load(u_ptrs, mask=mask_b[:, None] & mask_curr_d[None, :], other=0.0).to(tl.float32)
        v_val = tl.load(v_ptrs, mask=mask_b[:, None] & mask_curr_d[None, :], other=0.0).to(tl.float32)

        delta = -c_u[:, None] * u_val + c_v[:, None] * v_val
        tangent_vec = scale[:, None] * delta

        out_ptrs = Out_ptr + (offs_b[:, None] * stride_ob + curr_d[None, :] * stride_od)
        tl.store(out_ptrs, tangent_vec.to(tl.float16), mask=mask_b[:, None] & mask_curr_d[None, :])


def triton_poincare_log_map(U: torch.Tensor, V: torch.Tensor, eps: float = 1e-5) -> torch.Tensor:
    """
    U: [B, D] Base points in Poincare ball
    V: [B, D] Target points in Poincare ball
    Returns: [B, D] Tangent vectors in T_u D^D
    """
    assert U.is_cuda and V.is_cuda
    B, D = U.shape
    Out = torch.empty_like(U)

    BLOCK_B = 64
    BLOCK_D = min(128, triton.next_power_of_2(D))
    grid = (triton.cdiv(B, BLOCK_B),)

    _fused_poincare_log_map_kernel[grid](
        U, V, Out,
        B, D,
        U.stride(0), U.stride(1),
        V.stride(0), V.stride(1),
        Out.stride(0), Out.stride(1),
        eps=eps,
        BLOCK_B=BLOCK_B,
        BLOCK_D=BLOCK_D,
    )
    return Out


def benchmark_poincare_log_map():
    print("=" * 80)
    print("  IMF TRITON FUSED POINCARÉ LOGARITHMIC MAP BENCHMARK")
    print("=" * 80)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if not torch.cuda.is_available():
        print("[!] CUDA not available, skipping hardware kernel benchmark.")
        return

    B = 16384  # Batch size
    D = 128    # Embedding dim
    print(f"[*] Workload: Batch B={B}, Dim D={D}")

    torch.manual_seed(42)
    U = torch.randn((B, D), device=device, dtype=torch.float16)
    U = U / (U.norm(dim=-1, keepdim=True) + 1e-4) * 0.85

    V = torch.randn((B, D), device=device, dtype=torch.float16)
    V = V / (V.norm(dim=-1, keepdim=True) + 1e-4) * 0.85

    # Warmup
    for _ in range(10):
        _ = triton_poincare_log_map(U, V)
    torch.cuda.synchronize()

    # PyTorch Reference Verification
    def torch_log_ref(u, v, eps=1e-5):
        u_f = u.float()
        v_f = v.float()
        u_sq = torch.sum(u_f * u_f, dim=-1, keepdim=True)
        v_sq = torch.sum(v_f * v_f, dim=-1, keepdim=True)
        dot_uv = torch.sum(u_f * v_f, dim=-1, keepdim=True)

        alpha_u = torch.clamp(1.0 - u_sq, min=eps)
        denom = torch.clamp(1.0 + 2.0 * dot_uv + u_sq * v_sq, min=eps)

        c_u = (1.0 + 2.0 * dot_uv + v_sq) / denom
        c_v = alpha_u / denom

        delta = -c_u * u_f + c_v * v_f
        norm_delta = torch.norm(delta, dim=-1, keepdim=True)
        safe_norm = torch.clamp(norm_delta, max=1.0 - eps)
        artanh = 0.5 * torch.log((1.0 + safe_norm) / torch.clamp(1.0 - safe_norm, min=eps))

        scale = torch.where(norm_delta > eps, alpha_u * artanh / norm_delta, alpha_u)
        return (scale * delta).half()

    ref_out = torch_log_ref(U, V)
    tri_out = triton_poincare_log_map(U, V)

    max_diff = torch.max(torch.abs(ref_out - tri_out)).item()
    mean_diff = torch.mean(torch.abs(ref_out - tri_out)).item()
    print(f"[*] Numerical Fidelity: Max Diff = {max_diff:.4e}, Mean Diff = {mean_diff:.4e}")
    assert max_diff < 0.05, f"Numerical error too high: {max_diff}"

    # Latency Benchmark
    iters = 100
    start = time.perf_counter()
    for _ in range(iters):
        _ = triton_poincare_log_map(U, V)
    torch.cuda.synchronize()
    elapsed = (time.perf_counter() - start) / iters

    throughput = B / elapsed / 1e6
    print(f"[✓] Execution Latency: {elapsed * 1000:.3f} ms ({elapsed * 1e6:.1f} µs)")
    print(f"[✓] Log Map Throughput: {throughput:.2f} Million tangent projections/sec")
    print("=" * 80)


if __name__ == "__main__":
    benchmark_poincare_log_map()
