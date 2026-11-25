"""
Cycle 277: Fused Poincaré Discrete Wadati-Konno-Ichikawa (WKI) Lattice Soliton Flow
Hardware Target: AMD Ryzen 5 7600X (6C/12T) | NVIDIA GeForce RTX 5060 Ti (Blackwell / SM 12.0 / 16GB) | CUDA 12.8, Triton 3.9
Author: Nicholas Charles Mynhardt (Stratum Research Group)

Evaluates the discrete WKI elastic loop flow:
    i dψ_n/dt + ( Q_{n+1} - 2 Q_n + Q_{n-1} ) = 0
where Q_n = ψ_n / sqrt(1 + |ψ_n|^2)
Projected to the Poincaré hyperbolic ball conformal factor:
    lambda_ψ = 2.0 / (1.0 - ||ψ_n||^2)
"""

import math
import time
import torch
import triton
import triton.language as tl

@triton.jit
def _poincare_discrete_wki_kernel(
    psi_r_ptr,       # [N] real part
    psi_i_ptr,       # [N] imag part
    out_dr_ptr,      # [N] d(psi_r)/dt
    out_di_ptr,      # [N] d(psi_i)/dt
    out_metric_ptr,  # [N] conformal factor
    N: tl.constexpr,
    BLOCK_SIZE: tl.constexpr,
):
    pid = tl.program_id(0)
    idx = pid * BLOCK_SIZE + tl.arange(0, BLOCK_SIZE)
    mask = idx < N

    idx_p1 = (idx + 1) % N
    idx_m1 = (idx - 1 + N) % N

    # Load 3-point stencil
    pr_curr = tl.load(psi_r_ptr + idx, mask=mask, other=0.0)
    pi_curr = tl.load(psi_i_ptr + idx, mask=mask, other=0.0)

    pr_p1 = tl.load(psi_r_ptr + idx_p1, mask=mask, other=0.0)
    pi_p1 = tl.load(psi_i_ptr + idx_p1, mask=mask, other=0.0)

    pr_m1 = tl.load(psi_r_ptr + idx_m1, mask=mask, other=0.0)
    pi_m1 = tl.load(psi_i_ptr + idx_m1, mask=mask, other=0.0)

    # Q_n = psi_n / sqrt(1 + |psi_n|^2)
    norm2_curr = pr_curr * pr_curr + pi_curr * pi_curr
    denom_curr = tl.sqrt(1.0 + norm2_curr)
    qr_curr = pr_curr / denom_curr
    qi_curr = pi_curr / denom_curr

    norm2_p1 = pr_p1 * pr_p1 + pi_p1 * pi_p1
    denom_p1 = tl.sqrt(1.0 + norm2_p1)
    qr_p1 = pr_p1 / denom_p1
    qi_p1 = pi_p1 / denom_p1

    norm2_m1 = pr_m1 * pr_m1 + pi_m1 * pi_m1
    denom_m1 = tl.sqrt(1.0 + norm2_m1)
    qr_m1 = pr_m1 / denom_m1
    qi_m1 = pi_m1 / denom_m1

    # Discrete Laplacian of Q: L_Q = Q_{n+1} - 2 Q_n + Q_{n-1}
    lr_Q = qr_p1 - 2.0 * qr_curr + qr_m1
    li_Q = qi_p1 - 2.0 * qi_curr + qi_m1

    # i dpsi/dt + L_Q = 0  =>  dpsi/dt = i L_Q
    # d(pr)/dt = - li_Q
    # d(pi)/dt =   lr_Q
    dpr = - li_Q
    dpi =   lr_Q

    # Poincaré hyperbolic metric conformal factor
    norm2_clamped = tl.minimum(norm2_curr, 0.99)
    lambda_psi = 2.0 / (1.0 - norm2_clamped)

    # Conformal hyperbolic scaling
    scale = 1.0 / (lambda_psi * lambda_psi)
    out_dr = dpr * scale
    out_di = dpi * scale

    tl.store(out_dr_ptr + idx, out_dr, mask=mask)
    tl.store(out_di_ptr + idx, out_di, mask=mask)
    tl.store(out_metric_ptr + idx, lambda_psi, mask=mask)


def poincare_discrete_wki_triton(
    psi_r: torch.Tensor,
    psi_i: torch.Tensor
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    N = psi_r.numel()
    out_dr = torch.empty_like(psi_r)
    out_di = torch.empty_like(psi_i)
    out_metric = torch.empty_like(psi_r)

    BLOCK_SIZE = 256
    grid = (triton.cdiv(N, BLOCK_SIZE),)

    _poincare_discrete_wki_kernel[grid](
        psi_r, psi_i, out_dr, out_di, out_metric,
        N=N, BLOCK_SIZE=BLOCK_SIZE
    )
    return out_dr, out_di, out_metric


def poincare_discrete_wki_pytorch(
    psi_r: torch.Tensor,
    psi_i: torch.Tensor
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    norm2 = psi_r * psi_r + psi_i * psi_i
    denom = torch.sqrt(1.0 + norm2)
    qr = psi_r / denom
    qi = psi_i / denom

    qr_p1 = torch.roll(qr, -1, dims=0)
    qr_m1 = torch.roll(qr, 1, dims=0)
    qi_p1 = torch.roll(qi, -1, dims=0)
    qi_m1 = torch.roll(qi, 1, dims=0)

    lr_Q = qr_p1 - 2.0 * qr + qr_m1
    li_Q = qi_p1 - 2.0 * qi + qi_m1

    dpr = - li_Q
    dpi =   lr_Q

    norm2_clamped = torch.clamp(norm2, max=0.99)
    lambda_psi = 2.0 / (1.0 - norm2_clamped)
    scale = 1.0 / (lambda_psi * lambda_psi)

    return dpr * scale, dpi * scale, lambda_psi


def benchmark():
    if not torch.cuda.is_available():
        print("CUDA not available.")
        return

    device = torch.device("cuda:0")
    N = 131072
    psi_r = torch.randn(N, device=device, dtype=torch.float32) * 0.3
    psi_i = torch.randn(N, device=device, dtype=torch.float32) * 0.3

    for _ in range(20):
        dr_tri, di_tri, m_tri = poincare_discrete_wki_triton(psi_r, psi_i)
        dr_pt, di_pt, m_pt = poincare_discrete_wki_pytorch(psi_r, psi_i)
    torch.cuda.synchronize()

    max_err_r = torch.max(torch.abs(dr_tri - dr_pt)).item()
    max_err_i = torch.max(torch.abs(di_tri - di_pt)).item()
    max_err_m = torch.max(torch.abs(m_tri - m_pt)).item()

    assert max_err_r < 1e-4, f"Real error: {max_err_r}"
    assert max_err_i < 1e-4, f"Imag error: {max_err_i}"
    # Relative tolerance check for conformal factor near boundary
    rel_err_m = torch.max(torch.abs(m_tri - m_pt) / (m_pt + 1e-6)).item()
    assert rel_err_m < 1e-4, f"Relative metric error too high: {rel_err_m}"

    iters = 200
    torch.cuda.synchronize()
    t0 = time.perf_counter()
    for _ in range(iters):
        _ = poincare_discrete_wki_pytorch(psi_r, psi_i)
    torch.cuda.synchronize()
    t_pt = (time.perf_counter() - t0) / iters * 1e6

    torch.cuda.synchronize()
    t0 = time.perf_counter()
    for _ in range(iters):
        _ = poincare_discrete_wki_triton(psi_r, psi_i)
    torch.cuda.synchronize()
    t_tri = (time.perf_counter() - t0) / iters * 1e6

    speedup = t_pt / t_tri
    throughput = (N / (t_tri * 1e-6)) / 1e6

    print(f"=== Cycle 277: Poincaré Discrete Wadati-Konno-Ichikawa (WKI) Flow ===")
    print(f"Hardware Target: {torch.cuda.get_device_name(0)}")
    print(f"Lattice Size: {N:,} nodes")
    print(f"PyTorch Time: {t_pt:.2f} μs | Triton Time: {t_tri:.2f} μs")
    print(f"Speedup: {speedup:.2f}x | Throughput: {throughput:,.2f} M nodes/s")
    print(f"Max Abs Error: {max_err_r:.2e} (real), {max_err_i:.2e} (imag), {max_err_m:.2e} (metric)")
    print(f"Verification: PASSED (< 1e-4)")

if __name__ == "__main__":
    benchmark()
