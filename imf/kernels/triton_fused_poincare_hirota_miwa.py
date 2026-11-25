"""
Triton Fused Kernel: Poincaré Discrete Hirota-Miwa Bilinear System (SM 8.9)
Cycle 246 Capstone: Master Discrete KP Hirota Bilinear Soliton Dynamics,
3-Cocycle Bilinear Shifts, and Poincaré Hyperbolic Confinement.

Physical Model:
Discrete Hirota-Miwa (discrete KP) equation:
    \alpha_1 \tau(l+1, m, n) \tau(l, m+1, n+1) +
    \alpha_2 \tau(l, m+1, n) \tau(l+1, m, n+1) +
    \alpha_3 \tau(l, m, n+1) \tau(l+1, m+1, n) = 0
where \alpha_1 + \alpha_2 + \alpha_3 = 0.

Evaluation on spatial lattice in evolutionary gauge:
    \tau_{next}(l, m, n) = - [ \alpha_2 \tau(l, m+1, n) \tau(l+1, m, n+1) + \alpha_3 \tau(l, m, n+1) \tau(l+1, m+1, n) ] / [ \alpha_1 \tau(l, m+1, n+1) ]

Projected onto Poincaré disk manifold g(\tau) = 4 / (1 - \tau^2)^2.
"""

import torch
import triton
import triton.language as tl
import time

@triton.jit
def _poincare_hirota_miwa_kernel(
    tau_ptr, out_tau_ptr,
    alpha1, alpha2, alpha3,
    total_elements,
    L: tl.constexpr,
    M: tl.constexpr,
    N: tl.constexpr,
    BLOCK_SIZE: tl.constexpr
):
    pid = tl.program_id(0)
    offsets = pid * BLOCK_SIZE + tl.arange(0, BLOCK_SIZE)
    mask = offsets < total_elements

    # Decompose 1D linear index into (l, m, n)
    stride_m = N
    stride_l = M * N

    l_idx = offsets // stride_l
    rem = offsets % stride_l
    m_idx = rem // stride_m
    n_idx = rem % stride_m

    # Shifted indices with periodic wrap
    l_next = (l_idx + 1) % L
    m_next = (m_idx + 1) % M
    n_next = (n_idx + 1) % N

    idx_m1 = l_idx * stride_l + m_next * stride_m + n_idx
    idx_n1 = l_idx * stride_l + m_idx * stride_m + n_next
    idx_m1_n1 = l_idx * stride_l + m_next * stride_m + n_next

    idx_l1_m1 = l_next * stride_l + m_next * stride_m + n_idx
    idx_l1_n1 = l_next * stride_l + m_idx * stride_m + n_next

    t_m1 = tl.load(tau_ptr + idx_m1, mask=mask, other=1.0)
    t_n1 = tl.load(tau_ptr + idx_n1, mask=mask, other=1.0)
    t_m1_n1 = tl.load(tau_ptr + idx_m1_n1, mask=mask, other=1.0)

    t_l1_m1 = tl.load(tau_ptr + idx_l1_m1, mask=mask, other=1.0)
    t_l1_n1 = tl.load(tau_ptr + idx_l1_n1, mask=mask, other=1.0)

    denom = alpha1 * t_m1_n1
    denom_sign = tl.where(denom >= 0.0, 1.0, -1.0)
    safe_denom = tl.where(tl.abs(denom) < 1e-4, denom_sign * 1e-4, denom)

    num = - (alpha2 * t_m1 * t_l1_n1 + alpha3 * t_n1 * t_l1_m1)
    t_evolved = num / safe_denom

    t_sq = t_evolved * t_evolved
    scale = tl.where(t_sq >= 0.98, tl.sqrt(0.98 / t_sq), 1.0)
    out_val = t_evolved * scale

    tl.store(out_tau_ptr + offsets, out_val, mask=mask)

def poincare_hirota_miwa_triton(tau: torch.Tensor, alpha1=1.0, alpha2=-0.5, alpha3=-0.5):
    assert tau.is_cuda
    L, M, N = tau.shape
    total_elements = L * M * N
    out_tau = torch.empty_like(tau)

    BLOCK_SIZE = 1024
    grid = (triton.cdiv(total_elements, BLOCK_SIZE),)

    _poincare_hirota_miwa_kernel[grid](
        tau, out_tau,
        alpha1, alpha2, alpha3,
        total_elements,
        L, M, N,
        BLOCK_SIZE=BLOCK_SIZE
    )
    return out_tau

def poincare_hirota_miwa_pytorch(tau: torch.Tensor, alpha1=1.0, alpha2=-0.5, alpha3=-0.5):
    t_m1 = torch.roll(tau, shifts=-1, dims=1)
    t_n1 = torch.roll(tau, shifts=-1, dims=2)
    t_m1_n1 = torch.roll(torch.roll(tau, shifts=-1, dims=1), shifts=-1, dims=2)
    t_l1_m1 = torch.roll(torch.roll(tau, shifts=-1, dims=0), shifts=-1, dims=1)
    t_l1_n1 = torch.roll(torch.roll(tau, shifts=-1, dims=0), shifts=-1, dims=2)

    denom = alpha1 * t_m1_n1
    denom_sign = torch.where(denom >= 0.0, torch.tensor(1.0, device=tau.device), torch.tensor(-1.0, device=tau.device))
    safe_denom = torch.where(denom.abs() < 1e-4, denom_sign * 1e-4, denom)

    num = - (alpha2 * t_m1 * t_l1_n1 + alpha3 * t_n1 * t_l1_m1)
    t_evolved = num / safe_denom

    t_sq = t_evolved * t_evolved
    scale = torch.ones_like(t_sq)
    mask = t_sq >= 0.98
    scale[mask] = torch.sqrt(0.98 / t_sq[mask])
    return t_evolved * scale

def benchmark():
    device = torch.device('cuda:0' if torch.cuda.is_available() else 'cpu')
    print("=" * 70)
    print("  IMF TRITON POINCARÉ HIROTA-MIWA FLOW (RTX 5060 Ti SM 8.9)")
    print("=" * 70)

    L, M, N = 32, 64, 64  # 131,072 3D lattice points
    tau = torch.randn(L, M, N, device=device, dtype=torch.float32) * 0.3 + 0.5

    for _ in range(20):
        out_tri = poincare_hirota_miwa_triton(tau)
        out_pt = poincare_hirota_miwa_pytorch(tau)
    torch.cuda.synchronize()

    max_err = (out_tri - out_pt).abs().max().item()
    print(f"Max Absolute Error: {max_err:.2e}")
    assert max_err < 1e-4, "Numerical tolerance check failed!"

    iters = 100
    t0 = time.perf_counter()
    for _ in range(iters):
        out_pt = poincare_hirota_miwa_pytorch(tau)
    torch.cuda.synchronize()
    t_pt = (time.perf_counter() - t0) / iters * 1000.0

    t0 = time.perf_counter()
    for _ in range(iters):
        out_tri = poincare_hirota_miwa_triton(tau)
    torch.cuda.synchronize()
    t_tri = (time.perf_counter() - t0) / iters * 1000.0

    speedup = t_pt / t_tri
    throughput = ((L * M * N) / (t_tri / 1000.0)) / 1e6

    print(f"PyTorch Time:  {t_pt * 1000.0:.2f} µs")
    print(f"Triton Time:   {t_tri * 1000.0:.2f} µs")
    print(f"Speedup:       {speedup:.2f}x")
    print(f"Throughput:    {throughput:.2f} M lattice-points/s")
    print("=" * 70)

if __name__ == "__main__":
    benchmark()
