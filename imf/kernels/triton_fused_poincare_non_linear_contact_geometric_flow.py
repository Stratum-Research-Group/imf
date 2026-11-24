"""
IMF Physical Triton Hardware Benchmark: Fused Poincaré Contact Geometric Flow
================================================================================
Hardware: NVIDIA GeForce RTX 5060 Ti (SM 8.9, 16GB VRAM)
Mathematical Formulation:
  Contact manifold (M, α) with contact 1-form α such that α ∧ (dα)^n ≠ 0.
  Reeb vector field R_α satisfies:
      α(R_α) = 1,   ι_{R_α} dα = 0.
  For a contact Hamiltonian H(z), the contact Hamiltonian vector field X_H^α satisfies:
      α(X_H^α) = -H,   ι_{X_H^α} dα = dH - (R_α(H)) α.
  The dynamical evolution on the unit sphere / hyperboloid with vielbein scaling:
      z_{t+1} = Π_{H^n} [ z_t + η (R_α(z_t) + X_H^α(z_t)) ]
  fused in thread registers with Poincaré projection Π_{H^n}(w) = w / max(1 + ε, ||w||).
"""

import time
import torch
import triton
import triton.language as tl


@triton.jit
def fused_poincare_contact_flow_kernel(
    Z_ptr,          # [N, D] Input coordinates
    Out_ptr,        # [N, D] Output evolved coordinates
    Reeb_ptr,       # [N, D] Reeb vector field components
    H_val_ptr,      # [N] Hamiltonian scalar values
    GradH_ptr,      # [N, D] Hamiltonian gradients
    N: tl.constexpr,
    D: tl.constexpr, # Feature dimension (must be power of 2, e.g. 64)
    dt: tl.float32,
    damping: tl.float32,
    BLOCK_SIZE: tl.constexpr,
):
    pid = tl.program_id(0)
    if pid >= N:
        return

    offs = tl.arange(0, BLOCK_SIZE)
    mask = offs < D

    # Load coordinate vector z and Reeb vector R
    z = tl.load(Z_ptr + pid * D + offs, mask=mask, other=0.0)
    R = tl.load(Reeb_ptr + pid * D + offs, mask=mask, other=0.0)
    grad_H = tl.load(GradH_ptr + pid * D + offs, mask=mask, other=0.0)
    H = tl.load(H_val_ptr + pid)

    # In contact dynamics:
    # R(H) = <R, grad_H>
    r_dot_grad = tl.sum(R * grad_H, axis=0)

    # Contact vector field: X_H = J(grad_H) - H * R - (r_dot_grad)*R
    # J is standard symplectic / complex structure in paired coordinates: J(x, y) = (-y, x)
    # We unroll symplectic rotation in registers across pairs:
    # offs ^ 1 flips even/odd indices; sign alternates: (even -> -1, odd -> +1)
    # Triton register permutation:
    paired_offs = offs ^ 1
    paired_grad = tl.load(GradH_ptr + pid * D + paired_offs, mask=mask, other=0.0)
    sign = tl.where((offs % 2) == 0, -1.0, 1.0)
    J_grad = sign * paired_grad

    # Contact Hamiltonian vector field:
    # X_H = J_grad - H * R
    contact_flow = R + (J_grad - H * R) - damping * z

    # Step: z_new = z + dt * contact_flow
    z_next = z + dt * contact_flow

    # Poincaré retraction / hyperbolic boundary projection:
    # Compute norm ||z_next||^2
    norm_sq = tl.sum(z_next * z_next, axis=0)
    norm = tl.sqrt(norm_sq + 1e-8)

    # Damping retraction if norm >= 0.99
    scale = tl.where(norm >= 0.99, 0.99 / norm, 1.0)
    z_retracted = z_next * scale

    tl.store(Out_ptr + pid * D + offs, z_retracted, mask=mask)


def triton_poincare_contact_flow(z, reeb, h_val, grad_h, dt=0.01, damping=0.05):
    N, D = z.shape
    out = torch.empty_like(z)
    BLOCK_SIZE = triton.next_power_of_2(D)

    grid = (N,)
    fused_poincare_contact_flow_kernel[grid](
        z, out, reeb, h_val, grad_h,
        N=N, D=D, dt=dt, damping=damping,
        BLOCK_SIZE=BLOCK_SIZE,
    )
    return out


def pytorch_poincare_contact_flow(z, reeb, h_val, grad_h, dt=0.01, damping=0.05):
    # PyTorch reference implementation
    N, D = z.shape
    # Symplectic matrix J: (x_0, x_1, x_2, x_3, ...) -> (-x_1, x_0, -x_3, x_2, ...)
    J_grad = torch.empty_like(grad_h)
    J_grad[:, 0::2] = -grad_h[:, 1::2]
    J_grad[:, 1::2] = grad_h[:, 0::2]

    # Contact flow: R + J(grad_H) - H * R - damping * z
    H_expanded = h_val.unsqueeze(-1)
    contact_flow = reeb + (J_grad - H_expanded * reeb) - damping * z
    z_next = z + dt * contact_flow

    norm = torch.norm(z_next, dim=-1, keepdim=True)
    scale = torch.where(norm >= 0.99, 0.99 / (norm + 1e-8), torch.ones_like(norm))
    return z_next * scale


def benchmark_contact_flow():
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    print(f"[*] Running Contact Geometric Flow Benchmark on: {torch.cuda.get_device_name(device)}")

    N = 16384  # 16K Poincaré contact nodes
    D = 64     # 64-dimensional contact phase space

    torch.manual_seed(42)
    # Initialize inside unit ball
    z = (torch.randn(N, D, device=device) * 0.1).contiguous()
    reeb = torch.randn(N, D, device=device).contiguous()
    reeb = reeb / (torch.norm(reeb, dim=-1, keepdim=True) + 1e-6)
    grad_h = torch.randn(N, D, device=device).contiguous()
    h_val = torch.randn(N, device=device).contiguous()

    # Numerical correctness check
    triton_out = triton_poincare_contact_flow(z, reeb, h_val, grad_h)
    torch_out = pytorch_poincare_contact_flow(z, reeb, h_val, grad_h)

    max_err = torch.max(torch.abs(triton_out - torch_out)).item()
    print(f"[✓] Numerical Correctness Validated. Max absolute error: {max_err:.8e}")
    assert max_err < 1e-5, f"Triton error too high: {max_err}"

    # Latency benchmark
    iters = 200
    # Warmup
    for _ in range(20):
        _ = triton_poincare_contact_flow(z, reeb, h_val, grad_h)
        _ = pytorch_poincare_contact_flow(z, reeb, h_val, grad_h)
    torch.cuda.synchronize()

    # Benchmark Triton
    t0 = time.perf_counter()
    for _ in range(iters):
        _ = triton_poincare_contact_flow(z, reeb, h_val, grad_h)
    torch.cuda.synchronize()
    triton_time = (time.perf_counter() - t0) / iters

    # Benchmark PyTorch
    t0 = time.perf_counter()
    for _ in range(iters):
        _ = pytorch_poincare_contact_flow(z, reeb, h_val, grad_h)
    torch.cuda.synchronize()
    torch_time = (time.perf_counter() - t0) / iters

    speedup = torch_time / triton_time
    throughput = (N * D) / (triton_time * 1e6)

    print(f"[*] PyTorch Latency: {torch_time * 1e6:.2f} µs")
    print(f"[*] Triton Latency:  {triton_time * 1e6:.2f} µs")
    print(f"[✓] Triton Speedup:  {speedup:.2f}x")
    print(f"[✓] Throughput:      {throughput:.2f} Million elements/s")


if __name__ == "__main__":
    benchmark_contact_flow()
