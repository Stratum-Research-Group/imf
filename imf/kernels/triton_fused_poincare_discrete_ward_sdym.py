"""
Cycle 255: Fused Poincaré Discrete Self-Dual Yang-Mills (Ward Lattice) Flow Kernel
Hardware Target: Workstation NVIDIA GeForce RTX 5060 Ti (SM 12.0 GB206)

Evaluates the discrete Ward chiral integrable flow (2+2 dimensional reduction of SDYM)
on the Poincaré hyperbolic ball manifold:
    d^2 J_n / dt^2 = C * (J_{n+1} - 2 J_n + J_{n-1}) + [J_n, (J_{n+1} - J_{n-1})] - beta * J_n * ||J_n||^2
Where J_n is a 2x2 traceless anti-hermitian Lie algebra su(2) element:
    J_n = i * [ j1 * sigma_1 + j2 * sigma_2 + j3 * sigma_3 ]
Projected to the Poincaré hyperbolic ball conformal factor:
    lambda_J = 2.0 / (1.0 - ||J_n||^2)
"""

import math
import torch
import triton
import triton.language as tl

@triton.jit
def _poincare_discrete_ward_sdym_kernel(
    j1_ptr, j2_ptr, j3_ptr,        # [N] current su(2) components
    p1_ptr, p2_ptr, p3_ptr,        # [N] canonical momenta
    out_a1_ptr, out_a2_ptr, out_a3_ptr, # [N] output accelerations
    out_metric_ptr,                # [N] conformal metric
    coupling_c,                    # inter-site gauge coupling C
    beta,                          # quartic self-interaction beta
    N: tl.constexpr,
    BLOCK_SIZE: tl.constexpr,
):
    pid = tl.program_id(0)
    idx = pid * BLOCK_SIZE + tl.arange(0, BLOCK_SIZE)
    mask = idx < N

    idx_p1 = (idx + 1) % N
    idx_m1 = (idx - 1 + N) % N

    # Load current components
    j1_c = tl.load(j1_ptr + idx, mask=mask, other=0.0)
    j2_c = tl.load(j2_ptr + idx, mask=mask, other=0.0)
    j3_c = tl.load(j3_ptr + idx, mask=mask, other=0.0)

    # Load neighbor +1
    j1_p = tl.load(j1_ptr + idx_p1, mask=mask, other=0.0)
    j2_p = tl.load(j2_ptr + idx_p1, mask=mask, other=0.0)
    j3_p = tl.load(j3_ptr + idx_p1, mask=mask, other=0.0)

    # Load neighbor -1
    j1_m = tl.load(j1_ptr + idx_m1, mask=mask, other=0.0)
    j2_m = tl.load(j2_ptr + idx_m1, mask=mask, other=0.0)
    j3_m = tl.load(j3_ptr + idx_m1, mask=mask, other=0.0)

    # 1. Discrete spatial Laplacian for each component: C * (J_{n+1} - 2 J_n + J_{n-1})
    lap1 = j1_p - 2.0 * j1_c + j1_m
    lap2 = j2_p - 2.0 * j2_c + j2_m
    lap3 = j3_p - 2.0 * j3_c + j3_m

    # 2. Discrete chiral commutator term: [J_n, (J_{n+1} - J_{n-1})]
    # In su(2), [A, B] = A x B (vector cross product)
    diff1 = j1_p - j1_m
    diff2 = j2_p - j2_m
    diff3 = j3_p - j3_m

    comm1 = j2_c * diff3 - j3_c * diff2
    comm2 = j3_c * diff1 - j1_c * diff3
    comm3 = j1_c * diff2 - j2_c * diff1

    # 3. Norm squared: ||J_n||^2 = j1^2 + j2^2 + j3^2
    norm_sq = j1_c * j1_c + j2_c * j2_c + j3_c * j3_c

    # 4. Total acceleration: C * lap + comm - beta * J * norm_sq
    acc1 = coupling_c * lap1 + comm1 - beta * j1_c * norm_sq
    acc2 = coupling_c * lap2 + comm2 - beta * j2_c * norm_sq
    acc3 = coupling_c * lap3 + comm3 - beta * j3_c * norm_sq

    # 5. Poincaré hyperbolic conformal metric factor: lambda = 2 / (1 - norm_sq)
    clamped_norm = tl.minimum(norm_sq, 0.99)
    conf_metric = 2.0 / (1.0 - clamped_norm)

    tl.store(out_a1_ptr + idx, acc1 * conf_metric, mask=mask)
    tl.store(out_a2_ptr + idx, acc2 * conf_metric, mask=mask)
    tl.store(out_a3_ptr + idx, acc3 * conf_metric, mask=mask)
    tl.store(out_metric_ptr + idx, conf_metric, mask=mask)

def triton_poincare_discrete_ward_sdym(
    j: torch.Tensor, p: torch.Tensor, coupling_c: float = 1.0, beta: float = 0.5
):
    assert j.is_cuda and p.is_cuda
    assert j.shape == p.shape and j.shape[-1] == 3
    N = j.shape[0]

    j1, j2, j3 = j[:, 0].contiguous(), j[:, 1].contiguous(), j[:, 2].contiguous()
    p1, p2, p3 = p[:, 0].contiguous(), p[:, 1].contiguous(), p[:, 2].contiguous()

    out_a1 = torch.empty_like(j1)
    out_a2 = torch.empty_like(j2)
    out_a3 = torch.empty_like(j3)
    out_metric = torch.empty_like(j1)

    BLOCK_SIZE = 256
    grid = ((N + BLOCK_SIZE - 1) // BLOCK_SIZE,)

    _poincare_discrete_ward_sdym_kernel[grid](
        j1, j2, j3,
        p1, p2, p3,
        out_a1, out_a2, out_a3,
        out_metric,
        float(coupling_c), float(beta),
        N=N, BLOCK_SIZE=BLOCK_SIZE
    )
    out_acc = torch.stack([out_a1, out_a2, out_a3], dim=-1)
    return out_acc, out_metric

def torch_poincare_discrete_ward_sdym_ref(
    j: torch.Tensor, p: torch.Tensor, coupling_c: float = 1.0, beta: float = 0.5
):
    j_p1 = torch.roll(j, shifts=-1, dims=0)
    j_m1 = torch.roll(j, shifts=1, dims=0)

    lap = j_p1 - 2.0 * j + j_m1
    diff = j_p1 - j_m1
    comm = torch.cross(j, diff, dim=-1)

    norm_sq = (j ** 2).sum(dim=-1, keepdim=True)
    acc = coupling_c * lap + comm - beta * j * norm_sq

    clamped_norm = torch.clamp(norm_sq, max=0.99)
    conf_metric = 2.0 / (1.0 - clamped_norm)
    return acc * conf_metric, conf_metric.squeeze(-1)

if __name__ == "__main__":
    import time
    torch.manual_seed(42)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Executing Poincaré Discrete Ward SDYM Kernel Benchmark on: {torch.cuda.get_device_name(0)}")

    N = 131072 # 128K lattice nodes
    j = (torch.randn(N, 3, device=device, dtype=torch.float32) * 0.1).contiguous()
    p = (torch.randn(N, 3, device=device, dtype=torch.float32) * 0.05).contiguous()

    # Warmup
    for _ in range(20):
        out_acc, out_metric = triton_poincare_discrete_ward_sdym(j, p)
        ref_acc, ref_metric = torch_poincare_discrete_ward_sdym_ref(j, p)
    torch.cuda.synchronize()

    # Numerical verification
    max_err_acc = (out_acc - ref_acc).abs().max().item()
    max_err_metric = (out_metric - ref_metric).abs().max().item()
    print(f"Max Absolute Error (Acc): {max_err_acc:.3e}")
    print(f"Max Absolute Error (Metric): {max_err_metric:.3e}")
    assert max_err_acc < 1e-4, f"Numerical error too high: {max_err_acc}"
    assert max_err_metric < 1e-5, f"Metric error too high: {max_err_metric}"

    # Timing Triton
    iters = 200
    torch.cuda.synchronize()
    t0 = time.perf_counter()
    for _ in range(iters):
        out_acc, out_metric = triton_poincare_discrete_ward_sdym(j, p)
    torch.cuda.synchronize()
    t_triton = (time.perf_counter() - t0) / iters

    # Timing PyTorch
    torch.cuda.synchronize()
    t0 = time.perf_counter()
    for _ in range(iters):
        ref_acc, ref_metric = torch_poincare_discrete_ward_sdym_ref(j, p)
    torch.cuda.synchronize()
    t_torch = (time.perf_counter() - t0) / iters

    speedup = t_torch / t_triton
    throughput_m_nodes = (N / t_triton) / 1e6
    print(f"Triton Kernel Latency: {t_triton * 1e6:.2f} us")
    print(f"PyTorch Ref Latency:    {t_torch * 1e6:.2f} us")
    print(f"Hardware Speedup:       {speedup:.2f}x")
    print(f"Throughput:             {throughput_m_nodes:.2f} M nodes/s")
