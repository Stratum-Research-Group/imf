"""
IMF High-Performance Fused Poincare Berry Curvature Topological Router Kernel
=============================================================================
Physical Hardware Target: NVIDIA GeForce RTX 5060 Ti (SM 8.9 / Ada Lovelace)
Mathematical Foundation:
  Geometric Berry connection and topological curvature routing on the Poincaré ball (D^d_c, g_c).
  In quantum / non-Euclidean representation geometry, token trajectories moving in D^d_c
  generate an adiabatic Berry connection:
      A_\mu(x) = - (c / 2) * ( \epsilon_{\mu\nu} x^\nu / (1 - c ||x||^2) )
  The corresponding Berry curvature 2-form is:
      \Omega_{\mu\nu}(x) = \partial_\mu A_\nu - \partial_\nu A_\mu
                         = - c * \epsilon_{\mu\nu} / (1 - c ||x||^2)^2
  For an expert router with E experts having canonical topological charge vectors C_e in R^E:
      1. Local conformal factor: lambda_x = 2 / (1 - c ||x||^2).
      2. Berry curvature scalar density:
         B(x) = c / (1 - c ||x||^2)^2 = (c / 4) * lambda_x^2.
      3. Topological holonomy coupling between token x and expert centroids W_e:
         logit_e = <x, W_e>_R + \beta * B(x) * \omega(x, W_e),
         where \omega(x, W_e) is the symplectic coupling 2-form across coordinate pairs.
      4. Fused 2D grid kernel: grid = (B, E).
         Each thread block processes one token and one expert in parallel across SMs!
"""

import math
import time
import torch
import triton
import triton.language as tl


@triton.jit
def _poincare_berry_logits_kernel(
    X_ptr,          # [B, D] input tokens in D^d_c
    W_ptr,          # [E, D] expert centroid embeddings
    Logits_ptr,     # [B, E] intermediate unnormalized logits
    BerryDensity_ptr,# [B] Berry curvature scalar density
    B: tl.constexpr,
    E: tl.constexpr,
    D: tl.constexpr,
    c: tl.constexpr,
    beta: tl.constexpr,
    BLOCK_SIZE: tl.constexpr,
):
    pid_b = tl.program_id(0)
    pid_e = tl.program_id(1)
    if pid_b >= B or pid_e >= E:
        return

    offset_x = pid_b * D + tl.arange(0, BLOCK_SIZE)
    offset_w = pid_e * D + tl.arange(0, BLOCK_SIZE)
    mask = tl.arange(0, BLOCK_SIZE) < D

    x = tl.load(X_ptr + offset_x, mask=mask, other=0.0)
    w = tl.load(W_ptr + offset_w, mask=mask, other=0.0)

    # 1. Coordinate norm ||x||^2 and conformal metric factor
    x_sq = tl.sum(x * x, axis=0)
    max_sq = (1.0 - 1e-4) / c
    clamped_x_sq = tl.minimum(x_sq, max_sq)
    one_minus_cx2 = tl.maximum(1.0 - c * clamped_x_sq, 1e-6)

    # Berry curvature density: B(x) = c / (1 - c ||x||^2)^2
    berry_dens = c / (one_minus_cx2 * one_minus_cx2)
    if pid_e == 0:
        tl.store(BerryDensity_ptr + pid_b, berry_dens)

    # Conformal Riemannian factor: lambda_x = 2 / (1 - c ||x||^2)
    lambda_x = 2.0 / one_minus_cx2

    # Riemannian inner product: <x, w>_R = lambda_x * <x, w>_E
    dot_xw = tl.sum(x * w, axis=0)
    riem_dot = lambda_x * dot_xw

    # Symplectic cross-coupling omega(x, w)
    idx = tl.arange(0, BLOCK_SIZE)
    is_even = (idx % 2) == 0
    omega_elem = tl.where(is_even, x * w, -x * w)
    omega_val = tl.sum(omega_elem, axis=0)

    logit = riem_dot + beta * berry_dens * omega_val
    tl.store(Logits_ptr + pid_b * E + pid_e, logit)


@triton.jit
def _poincare_softmax_kernel(
    Logits_ptr,     # [B, E]
    OutProb_ptr,    # [B, E]
    B: tl.constexpr,
    E: tl.constexpr,
    BLOCK_E: tl.constexpr,
):
    pid = tl.program_id(0)
    if pid >= B:
        return

    offset = pid * E + tl.arange(0, BLOCK_E)
    mask = tl.arange(0, BLOCK_E) < E

    logits = tl.load(Logits_ptr + offset, mask=mask, other=-1e20)
    max_logit = tl.max(logits, axis=0)
    exp_logits = tl.exp(logits - max_logit)
    sum_exp = tl.sum(exp_logits, axis=0)
    probs = exp_logits / tl.maximum(sum_exp, 1e-7)

    tl.store(OutProb_ptr + offset, probs, mask=mask)


def triton_poincare_berry_curvature_router(
    x: torch.Tensor,
    weights: torch.Tensor,
    c: float = 1.0,
    beta: float = 0.05,
) -> tuple[torch.Tensor, torch.Tensor]:
    """
    Fused Poincaré Berry Curvature Topological Router.
    Args:
        x: [B, D] input tokens in Poincaré ball
        weights: [E, D] expert centroid representations
        c: manifold curvature
        beta: topological Berry coupling weight
    Returns:
        (routing_probs, berry_curvature_density)
    """
    assert x.is_cuda and weights.is_cuda
    B, D = x.shape
    E, _ = weights.shape
    BLOCK_SIZE = triton.next_power_of_2(D)
    BLOCK_E = triton.next_power_of_2(E)

    logits = torch.empty((B, E), device=x.device, dtype=torch.float32)
    out_prob = torch.empty((B, E), device=x.device, dtype=torch.float32)
    berry_dens = torch.empty((B,), device=x.device, dtype=torch.float32)

    grid_logits = (B, E)
    _poincare_berry_logits_kernel[grid_logits](
        x,
        weights,
        logits,
        berry_dens,
        B=B,
        E=E,
        D=D,
        c=c,
        beta=beta,
        BLOCK_SIZE=BLOCK_SIZE,
    )

    grid_softmax = (B,)
    _poincare_softmax_kernel[grid_softmax](
        logits,
        out_prob,
        B=B,
        E=E,
        BLOCK_E=BLOCK_E,
    )

    return out_prob, berry_dens


def reference_poincare_berry_curvature_router(
    x: torch.Tensor,
    weights: torch.Tensor,
    c: float = 1.0,
    beta: float = 0.05,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Reference PyTorch implementation of Berry Curvature Router."""
    B, D = x.shape
    E, _ = weights.shape

    x_sq = torch.sum(x * x, dim=-1, keepdim=True)
    max_sq = (1.0 - 1e-4) / c
    clamped_x_sq = torch.clamp(x_sq, max=max_sq)
    one_minus_cx2 = torch.clamp(1.0 - c * clamped_x_sq, min=1e-6)

    berry_dens = c / (one_minus_cx2 * one_minus_cx2)
    lambda_x = 2.0 / one_minus_cx2

    # Dot products [B, E]
    dot_xw = torch.matmul(x, weights.t())
    riem_dot = lambda_x * dot_xw

    # Symplectic coupling
    idx = torch.arange(D, device=x.device)
    is_even = (idx % 2) == 0
    sign = torch.where(is_even, 1.0, -1.0)
    w_signed = weights * sign
    omega = torch.matmul(x, w_signed.t())

    logits = riem_dot + beta * berry_dens * omega
    probs = torch.softmax(logits, dim=-1)
    return probs, berry_dens.squeeze(-1)


def benchmark_berry_router():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if not torch.cuda.is_available():
        print("[!] CUDA not available, skipping.")
        return

    prop = torch.cuda.get_device_properties(0)
    print(f"[*] Physical Device: {prop.name} (Compute Capability {prop.major}.{prop.minor})")

    B = 8192
    E = 16
    D = 128
    c = 1.0
    beta = 0.05

    x = torch.randn(B, D, device=device, dtype=torch.float32)
    x = x / (torch.norm(x, dim=-1, keepdim=True) + 1e-5) * 0.65
    weights = torch.randn(E, D, device=device, dtype=torch.float32) / math.sqrt(D)

    # 1. Numerical verification
    prob_tri, dens_tri = triton_poincare_berry_curvature_router(x, weights, c=c, beta=beta)
    prob_ref, dens_ref = reference_poincare_berry_curvature_router(x, weights, c=c, beta=beta)

    max_err_prob = torch.max(torch.abs(prob_tri - prob_ref)).item()
    max_err_dens = torch.max(torch.abs(dens_tri - dens_ref)).item()

    print(f"[✓] Numerical Verification:")
    print(f"    Max Routing Probability Error: {max_err_prob:.2e}")
    print(f"    Max Berry Density Error:       {max_err_dens:.2e}")
    assert max_err_prob < 1e-4, f"Probability error too high: {max_err_prob}"
    assert max_err_dens < 1e-4, f"Density error too high: {max_err_dens}"

    # 2. Timing benchmark
    for _ in range(20):
        _ = triton_poincare_berry_curvature_router(x, weights, c=c, beta=beta)
        _ = reference_poincare_berry_curvature_router(x, weights, c=c, beta=beta)
    torch.cuda.synchronize()

    iters = 200
    start = time.perf_counter()
    for _ in range(iters):
        _ = triton_poincare_berry_curvature_router(x, weights, c=c, beta=beta)
    torch.cuda.synchronize()
    triton_time = (time.perf_counter() - start) / iters

    start = time.perf_counter()
    for _ in range(iters):
        _ = reference_poincare_berry_curvature_router(x, weights, c=c, beta=beta)
    torch.cuda.synchronize()
    ref_time = (time.perf_counter() - start) / iters

    speedup = ref_time / triton_time
    throughput = (B * E * D) / (triton_time * 1e6)

    print(f"[✓] Performance Benchmark (B={B}, E={E}, D={D}):")
    print(f"    Reference PyTorch Latency: {ref_time * 1e6:.2f} µs")
    print(f"    Triton Fused Latency:     {triton_time * 1e6:.2f} µs")
    print(f"    Fused Speedup:             {speedup:.2f}x")
    print(f"    Throughput:                {throughput:.2f} M expert interactions/sec")


if __name__ == "__main__":
    benchmark_berry_router()
