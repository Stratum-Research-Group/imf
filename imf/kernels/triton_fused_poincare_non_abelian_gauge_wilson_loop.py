"""
IMF High-Performance Fused Poincare Non-Abelian Gauge Wilson Loop Kernel
========================================================================
Physical Hardware Target: NVIDIA GeForce RTX 5060 Ti (SM 8.9 / Ada Lovelace)
Mathematical Foundation:
  Non-Abelian gauge connection and Wilson loop holonomy on the Poincaré ball (D^d_c, g_c).
  Let a closed loop sequence in D^d_c be represented by tokens (x_0, x_1, ..., x_{T-1})
  with periodic boundary condition x_T = x_0.
  Under an SU(2) gauge group, the non-Abelian gauge connection 1-form is:
      A_\mu(x) = \sum_{a=1}^3 \tau_a A_\mu^a(x),
  where \tau_a = \sigma_a / (2i) are the SU(2) Lie algebra generators.
  For adjacent tokens x_t, x_{t+1}, the discrete parallel transporter link variable is:
      U_t = \exp\left( \frac{1}{2} \lambda_{x_t} (x_t^\top J x_{t+1}) \cdot \tau_3 + \Delta x_t \cdot \tau_1 \right) \in \mathrm{SU}(2).
  In quaternion / SU(2) representation:
      U_t = \cos(\theta_t) I + \sin(\theta_t) ( n_1 \sigma_1 + n_2 \sigma_2 + n_3 \sigma_3 ).
  The path-ordered Wilson loop holonomy is:
      W = \prod_{t=0}^{T-1} U_t \in \mathrm{SU}(2).
  The gauge-invariant Wilson loop observable is the normalized trace:
      Tr(W) / 2 = \operatorname{Re}(w_0) \in [-1, 1].
  The fused kernel accumulates the quaternion product across the entire closed loop trajectory
  directly in GPU thread registers in a single pass without intermediate DRAM allocations.
"""

import math
import time
import torch
import triton
import triton.language as tl


@triton.jit
def _poincare_wilson_loop_kernel(
    X_ptr,          # [B, T, D] closed loop coordinates in D^d_c
    Trace_ptr,      # [B] output Wilson loop trace (scalar observable)
    Holonomy_ptr,   # [B, 4] output final SU(2) quaternion (w0, w1, w2, w3)
    B: tl.constexpr,
    T: tl.constexpr,
    D: tl.constexpr,
    c: tl.constexpr,
    BLOCK_SIZE: tl.constexpr,
):
    pid = tl.program_id(0)
    if pid >= B:
        return

    # Initialize quaternion identity W = (1, 0, 0, 0)
    w0 = 1.0
    w1 = 0.0
    w2 = 0.0
    w3 = 0.0

    mask = tl.arange(0, BLOCK_SIZE) < D
    idx = tl.arange(0, BLOCK_SIZE)
    is_even = (idx % 2) == 0

    # Sequential path-ordering along trajectory T
    for t in range(T):
        t_next = (t + 1) % T

        offset_curr = pid * (T * D) + t * D + tl.arange(0, BLOCK_SIZE)
        offset_next = pid * (T * D) + t_next * D + tl.arange(0, BLOCK_SIZE)

        x_curr = tl.load(X_ptr + offset_curr, mask=mask, other=0.0)
        x_next = tl.load(X_ptr + offset_next, mask=mask, other=0.0)

        # 1. Local conformal factor lambda_x
        x_sq = tl.sum(x_curr * x_curr, axis=0)
        max_sq = (1.0 - 1e-4) / c
        clamped_x_sq = tl.minimum(x_sq, max_sq)
        one_minus_cx2 = tl.maximum(1.0 - c * clamped_x_sq, 1e-6)
        lambda_x = 2.0 / one_minus_cx2

        # 2. Symplectic coupling cross-term (tau_3 rotation generator)
        symp_elem = tl.where(is_even, x_curr * x_next, -x_curr * x_next)
        theta_3 = 0.25 * lambda_x * tl.sum(symp_elem, axis=0)

        # 3. Tangent displacement norm (tau_1 rotation generator)
        diff = x_next - x_curr
        theta_1 = 0.1 * lambda_x * tl.sqrt(tl.maximum(tl.sum(diff * diff, axis=0), 1e-8))

        # Effective SU(2) rotation angle
        theta = tl.sqrt(theta_1 * theta_1 + theta_3 * theta_3)
        theta = tl.maximum(theta, 1e-6)

        cos_half = tl.cos(0.5 * theta)
        sin_half = tl.sin(0.5 * theta)

        u0 = cos_half
        u1 = sin_half * (theta_1 / theta)
        u2 = 0.0
        u3 = sin_half * (theta_3 / theta)

        # 4. Quaternion multiplication: W_new = W * U
        # (w0 + w1 i + w2 j + w3 k) * (u0 + u1 i + u2 j + u3 k)
        nw0 = w0 * u0 - w1 * u1 - w2 * u2 - w3 * u3
        nw1 = w0 * u1 + w1 * u0 + w2 * u3 - w3 * u2
        nw2 = w0 * u2 - w1 * u3 + w2 * u0 + w3 * u1
        nw3 = w0 * u3 + w1 * u2 - w2 * u1 + w3 * u0

        # Normalization to preserve unit quaternion
        q_norm = tl.sqrt(tl.maximum(nw0 * nw0 + nw1 * nw1 + nw2 * nw2 + nw3 * nw3, 1e-8))
        w0 = nw0 / q_norm
        w1 = nw1 / q_norm
        w2 = nw2 / q_norm
        w3 = nw3 / q_norm

    # Wilson loop normalized trace: Tr(W) / 2 = w0
    tl.store(Trace_ptr + pid, w0)

    # Store full SU(2) holonomy quaternion
    tl.store(Holonomy_ptr + pid * 4 + 0, w0)
    tl.store(Holonomy_ptr + pid * 4 + 1, w1)
    tl.store(Holonomy_ptr + pid * 4 + 2, w2)
    tl.store(Holonomy_ptr + pid * 4 + 3, w3)


def triton_poincare_non_abelian_gauge_wilson_loop(
    x: torch.Tensor,
    c: float = 1.0,
) -> tuple[torch.Tensor, torch.Tensor]:
    """
    Fused Poincaré Non-Abelian Gauge Wilson Loop Kernel.
    Args:
        x: [B, T, D] closed loop coordinates in Poincaré ball
        c: hyperbolic curvature
    Returns:
        (wilson_trace, holonomy_quaternions)
    """
    assert x.is_cuda
    B, T, D = x.shape
    BLOCK_SIZE = triton.next_power_of_2(D)

    trace = torch.empty((B,), device=x.device, dtype=torch.float32)
    holonomy = torch.empty((B, 4), device=x.device, dtype=torch.float32)

    grid = (B,)
    _poincare_wilson_loop_kernel[grid](
        x,
        trace,
        holonomy,
        B=B,
        T=T,
        D=D,
        c=c,
        BLOCK_SIZE=BLOCK_SIZE,
    )
    return trace, holonomy


def reference_poincare_wilson_loop(
    x: torch.Tensor,
    c: float = 1.0,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Reference PyTorch implementation of Wilson Loop Holonomy."""
    B, T, D = x.shape
    idx = torch.arange(D, device=x.device)
    is_even = (idx % 2) == 0
    sign = torch.where(is_even, 1.0, -1.0)

    w0 = torch.ones(B, device=x.device)
    w1 = torch.zeros(B, device=x.device)
    w2 = torch.zeros(B, device=x.device)
    w3 = torch.zeros(B, device=x.device)

    for t in range(T):
        t_next = (t + 1) % T
        xc = x[:, t, :]
        xn = x[:, t_next, :]

        xc_sq = torch.sum(xc * xc, dim=-1)
        max_sq = (1.0 - 1e-4) / c
        clamped_xc_sq = torch.clamp(xc_sq, max=max_sq)
        one_minus_cx2 = torch.clamp(1.0 - c * clamped_xc_sq, min=1e-6)
        lambda_x = 2.0 / one_minus_cx2

        symp = torch.sum((xc * xn) * sign, dim=-1)
        theta_3 = 0.25 * lambda_x * symp

        diff = xn - xc
        theta_1 = 0.1 * lambda_x * torch.sqrt(torch.clamp(torch.sum(diff * diff, dim=-1), min=1e-8))

        theta = torch.sqrt(theta_1 ** 2 + theta_3 ** 2)
        theta = torch.clamp(theta, min=1e-6)

        cos_half = torch.cos(0.5 * theta)
        sin_half = torch.sin(0.5 * theta)

        u0 = cos_half
        u1 = sin_half * (theta_1 / theta)
        u2 = torch.zeros_like(u0)
        u3 = sin_half * (theta_3 / theta)

        nw0 = w0 * u0 - w1 * u1 - w2 * u2 - w3 * u3
        nw1 = w0 * u1 + w1 * u0 + w2 * u3 - w3 * u2
        nw2 = w0 * u2 - w1 * u3 + w2 * u0 + w3 * u1
        nw3 = w0 * u3 + w1 * u2 - w2 * u1 + w3 * u0

        q_norm = torch.sqrt(torch.clamp(nw0 ** 2 + nw1 ** 2 + nw2 ** 2 + nw3 ** 2, min=1e-8))
        w0 = nw0 / q_norm
        w1 = nw1 / q_norm
        w2 = nw2 / q_norm
        w3 = nw3 / q_norm

    holonomy = torch.stack([w0, w1, w2, w3], dim=-1)
    return w0, holonomy


def benchmark_wilson_loop():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if not torch.cuda.is_available():
        print("[!] CUDA not available, skipping.")
        return

    prop = torch.cuda.get_device_properties(0)
    print(f"[*] Physical Device: {prop.name} (Compute Capability {prop.major}.{prop.minor})")

    B = 8192
    T = 16
    D = 128
    c = 1.0

    x = torch.randn(B, T, D, device=device, dtype=torch.float32)
    x = x / (torch.norm(x, dim=-1, keepdim=True) + 1e-5) * 0.65

    # 1. Numerical verification
    tr_tri, hol_tri = triton_poincare_non_abelian_gauge_wilson_loop(x, c=c)
    tr_ref, hol_ref = reference_poincare_wilson_loop(x, c=c)

    max_err_tr = torch.max(torch.abs(tr_tri - tr_ref)).item()
    max_err_hol = torch.max(torch.abs(hol_tri - hol_ref)).item()

    print(f"[✓] Numerical Verification:")
    print(f"    Max Wilson Trace Error:     {max_err_tr:.2e}")
    print(f"    Max Holonomy Vector Error: {max_err_hol:.2e}")
    assert max_err_tr < 1e-4, f"Trace error too high: {max_err_tr}"
    assert max_err_hol < 1e-4, f"Holonomy error too high: {max_err_hol}"

    # 2. Timing benchmark
    for _ in range(20):
        _ = triton_poincare_non_abelian_gauge_wilson_loop(x, c=c)
        _ = reference_poincare_wilson_loop(x, c=c)
    torch.cuda.synchronize()

    iters = 200
    start = time.perf_counter()
    for _ in range(iters):
        _ = triton_poincare_non_abelian_gauge_wilson_loop(x, c=c)
    torch.cuda.synchronize()
    triton_time = (time.perf_counter() - start) / iters

    start = time.perf_counter()
    for _ in range(iters):
        _ = reference_poincare_wilson_loop(x, c=c)
    torch.cuda.synchronize()
    ref_time = (time.perf_counter() - start) / iters

    speedup = ref_time / triton_time
    throughput = (B * T * D) / (triton_time * 1e6)

    print(f"[✓] Performance Benchmark (B={B}, T={T}, D={D}):")
    print(f"    Reference PyTorch Latency: {ref_time * 1e6:.2f} µs")
    print(f"    Triton Fused Latency:     {triton_time * 1e6:.2f} µs")
    print(f"    Fused Speedup:             {speedup:.2f}x")
    print(f"    Throughput:                {throughput:.2f} M trajectory elements/sec")


if __name__ == "__main__":
    benchmark_wilson_loop()
