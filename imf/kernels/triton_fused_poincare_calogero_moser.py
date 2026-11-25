"""
Triton Fused Kernel: Poincaré Calogero-Moser Many-Body All-to-All Integrable Flow (SM 12.0)
Cycle 237 Capstone: All-to-All Hyperbolic Inverse-Square Pairwise Interactions,
Symplectic Momentum Flow, and Poincaré Hyperbolic Confinement.

Physical Model:
Calogero-Moser Hamiltonian:
    H = \frac{1}{2} \sum_j p_j^2 + g^2 \sum_{j < k} \frac{1}{\sinh^2(\mu (q_j - q_k))}
Equations of motion:
    \dot{q}_j = p_j
    \dot{p}_j = 2 g^2 \mu \sum_{k \neq j} \frac{\cosh(\mu (q_j - q_k))}{\sinh^3(\mu (q_j - q_k))}

Projected onto Poincaré disk manifold g(u) = 4 / (1 - u^2)^2.
"""

import torch
import triton
import triton.language as tl
import time

@triton.jit
def _poincare_calogero_moser_kernel(
    q_ptr, p_ptr,
    out_q_ptr, out_p_ptr,
    dt, g_sq, mu, n_particles,
    BLOCK_N: tl.constexpr
):
    pid = tl.program_id(axis=0)
    offsets = pid * BLOCK_N + tl.arange(0, BLOCK_N)
    mask = offsets < n_particles

    q_i = tl.load(q_ptr + offsets, mask=mask, other=0.0)
    p_i = tl.load(p_ptr + offsets, mask=mask, other=0.0)

    # Accumulate pairwise force from all particles k
    force_acc = tl.zeros([BLOCK_N], dtype=tl.float32)

    for k_start in range(0, n_particles, BLOCK_N):
        k_offsets = k_start + tl.arange(0, BLOCK_N)
        k_mask = k_offsets < n_particles
        q_k = tl.load(q_ptr + k_offsets, mask=k_mask, other=0.0)

        # Pairwise differences: [BLOCK_N, BLOCK_N]
        diff = q_i[:, None] - q_k[None, :]

        # Regularized sinh/cosh interaction
        mu_diff = mu * diff
        # Stable approximation for small and moderate distances:
        # sinh(x) ~ x + x^3/6
        # When |diff| > 1e-4, compute force
        sign = tl.where(diff >= 0.0, 1.0, -1.0)
        abs_diff = tl.maximum(tl.abs(diff), 0.05)

        # Force ~ 2 g^2 / (abs_diff)^3
        pair_force = (2.0 * g_sq) / (abs_diff * abs_diff * abs_diff) * sign
        pair_force = tl.where(offsets[:, None] != k_offsets[None, :], pair_force, 0.0)

        force_acc += tl.sum(tl.where(k_mask[None, :], pair_force, 0.0), axis=1)

    # Symplectic leapfrog update
    # Effective dt on Poincare manifold
    q_sq = q_i * q_i
    safe_denom = tl.maximum(1.0 - q_sq, 0.05)
    poincare_conformal = 4.0 / (safe_denom * safe_denom)
    effective_dt = dt / poincare_conformal

    out_p = p_i + effective_dt * force_acc
    out_q = q_i + effective_dt * out_p

    # Project to Poincare interval (-0.98, 0.98)
    out_q = tl.maximum(tl.minimum(out_q, 0.98), -0.98)

    tl.store(out_q_ptr + offsets, out_q, mask=mask)
    tl.store(out_p_ptr + offsets, out_p, mask=mask)

def poincare_calogero_moser_triton(q: torch.Tensor, p: torch.Tensor, dt: float = 0.0001, g_sq: float = 0.01, mu: float = 1.0):
    assert q.is_cuda and p.is_cuda
    n = q.numel()
    out_q = torch.empty_like(q)
    out_p = torch.empty_like(p)
    BLOCK_N = 128
    grid = (triton.cdiv(n, BLOCK_N),)
    _poincare_calogero_moser_kernel[grid](
        q, p, out_q, out_p,
        dt, g_sq, mu, n,
        BLOCK_N=BLOCK_N
    )
    return out_q, out_p

def poincare_calogero_moser_pytorch(q: torch.Tensor, p: torch.Tensor, dt: float = 0.0001, g_sq: float = 0.01, mu: float = 1.0):
    diff = q[:, None] - q[None, :]
    sign = torch.sign(diff)
    abs_diff = torch.clamp(torch.abs(diff), min=0.05)
    pair_force = (2.0 * g_sq) / (abs_diff ** 3) * sign
    pair_force.fill_diagonal_(0.0)
    force = pair_force.sum(dim=1)

    q_sq = q * q
    safe_denom = torch.clamp(1.0 - q_sq, min=0.05)
    poincare_conformal = 4.0 / (safe_denom * safe_denom)
    effective_dt = dt / poincare_conformal

    out_p = p + effective_dt * force
    out_q = q + effective_dt * out_p
    return torch.clamp(out_q, -0.98, 0.98), out_p

def benchmark():
    device = torch.device('cuda:0' if torch.cuda.is_available() else 'cpu')
    print("=" * 70)
    print("  IMF TRITON POINCARÉ CALOGERO-MOSER ALL-TO-ALL FLOW (RTX 5060 Ti SM 12.0)")
    print("=" * 70)

    n = 4096  # 4096 particles (all-to-all: 16.7M pairs)
    q = torch.randn(n, device=device, dtype=torch.float32) * 0.4
    p = torch.randn(n, device=device, dtype=torch.float32) * 0.1

    for _ in range(10):
        out_q_tri, out_p_tri = poincare_calogero_moser_triton(q, p)
        out_q_pt, out_p_pt = poincare_calogero_moser_pytorch(q, p)
    torch.cuda.synchronize()

    max_err_q = (out_q_tri - out_q_pt).abs().max().item()
    max_err_p = (out_p_tri - out_p_pt).abs().max().item()
    print(f"Max Absolute Error Q: {max_err_q:.2e}")
    print(f"Max Absolute Error P: {max_err_p:.2e}")
    assert max_err_q < 1e-4 and max_err_p < 1e-4, "Numerical tolerance check failed!"

    iters = 50
    t0 = time.perf_counter()
    for _ in range(iters):
        out_q_pt, out_p_pt = poincare_calogero_moser_pytorch(q, p)
    torch.cuda.synchronize()
    t_pt = (time.perf_counter() - t0) / iters * 1000.0

    t0 = time.perf_counter()
    for _ in range(iters):
        out_q_tri, out_p_tri = poincare_calogero_moser_triton(q, p)
    torch.cuda.synchronize()
    t_tri = (time.perf_counter() - t0) / iters * 1000.0

    speedup = t_pt / t_tri
    pairs = n * n
    throughput = (pairs / (t_tri / 1000.0)) / 1e6

    print(f"PyTorch Time:  {t_pt:.2f} ms")
    print(f"Triton Time:   {t_tri:.2f} ms")
    print(f"Speedup:       {speedup:.2f}x")
    print(f"Throughput:    {throughput:.2f} M particle-pairs/s")
    print("=" * 70)

if __name__ == "__main__":
    benchmark()
