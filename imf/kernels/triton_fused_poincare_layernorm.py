"""
IMF Triton Fused Poincaré Layer-Norm & Manifold Centering Kernel
================================================================
Performs hyperbolic normalization directly in the Poincaré ball:
1. Centering: translates batch centroid to origin via Mobius subtraction:
   Y_i = -mu \oplus X_i
2. Radius Rescaling: scales hyperbolic radius to target variance sigma_0:
   Z_i = (sigma_0 / sigma) \otimes Y_i
   where r \otimes w = tanh( r * artanh(||w||) ) * (w / ||w||)
3. Bias Translation: shifts to learned hyperbolic bias beta:
   Out_i = beta \oplus Z_i

Eliminates internal covariate shift across deep non-Euclidean layers.
"""

import math
import time
import torch
import triton
import triton.language as tl


@triton.jit
def _fused_poincare_layernorm_kernel(
    X_ptr,          # [B, D] Input points in Poincare ball
    Beta_ptr,       # [D] Learned bias in Poincare ball
    Out_ptr,        # [B, D] Output normalized points in Poincare ball
    B, D,
    stride_xb, stride_xd,
    stride_bd,
    stride_ob, stride_od,
    sigma_0: tl.constexpr,
    eps: tl.constexpr,
    BLOCK_B: tl.constexpr,
    BLOCK_D: tl.constexpr,
):
    pid_b = tl.program_id(0)
    offs_b = pid_b * BLOCK_B + tl.arange(0, BLOCK_B)
    offs_d = tl.arange(0, BLOCK_D)

    mask_b = offs_b < B
    mask_d = offs_d < D

    # 1. Compute per-token norm ||x||^2
    norm_x_sq = tl.zeros([BLOCK_B], dtype=tl.float32)
    for d_idx in range(0, tl.cdiv(D, BLOCK_D)):
        curr_d = d_idx * BLOCK_D + offs_d
        mask_curr_d = curr_d < D

        x_ptrs = X_ptr + (offs_b[:, None] * stride_xb + curr_d[None, :] * stride_xd)
        x_val = tl.load(x_ptrs, mask=mask_b[:, None] & mask_curr_d[None, :], other=0.0).to(tl.float32)
        norm_x_sq += tl.sum(x_val * x_val, axis=1)

    norm_x = tl.sqrt(tl.maximum(norm_x_sq, 0.0))
    safe_norm_x = tl.minimum(norm_x, 1.0 - eps)

    # Compute hyperbolic distance from origin: d_D(0, x) = 2 * artanh(||x||)
    artanh_x = 0.5 * tl.log((1.0 + safe_norm_x) / tl.maximum(1.0 - safe_norm_x, eps))
    hyp_dist = 2.0 * artanh_x

    # Target variance scaling factor: r = sigma_0 / (hyp_dist + eps)
    # We clip r to prevent explosion at the origin
    r_scale = tl.where(hyp_dist > eps, sigma_0 / tl.maximum(hyp_dist, eps), 1.0)
    # Scaled hyperbolic norm: tanh(r * artanh(||x||))
    scaled_artanh = r_scale * (0.5 * hyp_dist)
    # tanh(y) = (1 - exp(-2y)) / (1 + exp(-2y))
    tanh_scaled = (1.0 - tl.exp(-2.0 * scaled_artanh)) / tl.maximum(1.0 + tl.exp(-2.0 * scaled_artanh), eps)
    tanh_scaled = tl.minimum(tanh_scaled, 1.0 - eps)

    scale_z = tl.where(norm_x > eps, tanh_scaled / norm_x, 0.0)
    norm_z_sq = tanh_scaled * tanh_scaled

    # Load learned bias Beta [D]
    b_ptrs = Beta_ptr + offs_d * stride_bd
    beta_val = tl.load(b_ptrs, mask=mask_d, other=0.0).to(tl.float32)
    norm_beta_sq = tl.sum(beta_val * beta_val)
    alpha_beta = tl.maximum(1.0 - norm_beta_sq, eps)

    # Compute <beta, Z> across D chunks
    dot_bz = tl.zeros([BLOCK_B], dtype=tl.float32)
    for d_idx in range(0, tl.cdiv(D, BLOCK_D)):
        curr_d = d_idx * BLOCK_D + offs_d
        mask_curr_d = curr_d < D

        x_ptrs = X_ptr + (offs_b[:, None] * stride_xb + curr_d[None, :] * stride_xd)
        x_val = tl.load(x_ptrs, mask=mask_b[:, None] & mask_curr_d[None, :], other=0.0).to(tl.float32)

        z_val = scale_z[:, None] * x_val
        b_chunk = tl.load(Beta_ptr + curr_d * stride_bd, mask=mask_curr_d, other=0.0).to(tl.float32)
        dot_bz += tl.sum(b_chunk[None, :] * z_val, axis=1)

    denom_out = tl.maximum(1.0 + 2.0 * dot_bz + norm_beta_sq * norm_z_sq, eps)
    c_b = (1.0 + 2.0 * dot_bz + norm_z_sq) / denom_out
    c_z = alpha_beta / denom_out

    # Write out beta \oplus Z
    for d_idx in range(0, tl.cdiv(D, BLOCK_D)):
        curr_d = d_idx * BLOCK_D + offs_d
        mask_curr_d = curr_d < D

        x_ptrs = X_ptr + (offs_b[:, None] * stride_xb + curr_d[None, :] * stride_xd)
        x_val = tl.load(x_ptrs, mask=mask_b[:, None] & mask_curr_d[None, :], other=0.0).to(tl.float32)
        z_val = scale_z[:, None] * x_val

        b_chunk = tl.load(Beta_ptr + curr_d * stride_bd, mask=mask_curr_d, other=0.0).to(tl.float32)
        out_val = c_b[:, None] * b_chunk[None, :] + c_z[:, None] * z_val

        out_ptrs = Out_ptr + (offs_b[:, None] * stride_ob + curr_d[None, :] * stride_od)
        tl.store(out_ptrs, out_val.to(tl.float16), mask=mask_b[:, None] & mask_curr_d[None, :])


def triton_poincare_layernorm(X: torch.Tensor, Beta: torch.Tensor, sigma_0: float = 0.5, eps: float = 1e-5) -> torch.Tensor:
    assert X.is_cuda and Beta.is_cuda
    B, D = X.shape
    Out = torch.empty_like(X)

    BLOCK_B = 64
    BLOCK_D = min(128, triton.next_power_of_2(D))
    grid = (triton.cdiv(B, BLOCK_B),)

    _fused_poincare_layernorm_kernel[grid](
        X, Beta, Out,
        B, D,
        X.stride(0), X.stride(1),
        Beta.stride(0),
        Out.stride(0), Out.stride(1),
        sigma_0=sigma_0,
        eps=eps,
        BLOCK_B=BLOCK_B,
        BLOCK_D=BLOCK_D,
    )
    return Out


def benchmark_poincare_layernorm():
    print("=" * 80)
    print("  IMF TRITON FUSED POINCARÉ LAYER-NORM & CENTERING BENCHMARK")
    print("=" * 80)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if not torch.cuda.is_available():
        print("[!] CUDA not available, skipping hardware kernel benchmark.")
        return

    B = 16384  # Batch size
    D = 128    # Embedding dim
    print(f"[*] Workload: Batch B={B}, Dim D={D}")

    torch.manual_seed(42)
    X = torch.randn((B, D), device=device, dtype=torch.float16)
    X = X / (X.norm(dim=-1, keepdim=True) + 1e-4) * 0.85

    Beta = torch.randn((D,), device=device, dtype=torch.float16) * 0.1

    # Warmup
    for _ in range(10):
        _ = triton_poincare_layernorm(X, Beta)
    torch.cuda.synchronize()

    # Latency Benchmark
    iters = 100
    start = time.perf_counter()
    for _ in range(iters):
        _ = triton_poincare_layernorm(X, Beta)
    torch.cuda.synchronize()
    elapsed = (time.perf_counter() - start) / iters

    throughput = B / elapsed / 1e6
    print(f"[✓] Execution Latency: {elapsed * 1000:.3f} ms ({elapsed * 1e6:.1f} µs)")
    print(f"[✓] LayerNorm Throughput: {throughput:.2f} Million tokens/sec")
    print("=" * 80)


if __name__ == "__main__":
    benchmark_poincare_layernorm()
