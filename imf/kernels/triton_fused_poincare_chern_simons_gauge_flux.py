"""
IMF Physical Triton Hardware Benchmark: Fused Poincaré Chern-Simons Gauge Flux
================================================================================
Hardware: NVIDIA GeForce RTX 5060 Ti (SM 12.0, 16GB VRAM)
Mathematical Formulation:
  Non-Abelian SU(2) Chern-Simons gauge connection 1-form on hyperbolic 3-space:
    A = sum_{a=1}^3 A_i^a T_a dx^i
  where T_a = -i sigma_a / 2 are the standard su(2) Lie algebra generators with [T_a, T_b] = eps_{abc} T_c.
  The Chern-Simons field curvature (gauge flux) is:
    F = dA + A ^ A
  The topological Chern-Simons variation (gauge flux density):
    B_i^a = eps_{ijk} (partial_j A_k^a + (1/2) eps_{abc} A_j^b A_k^c)
  Fused Triton execution evaluates:
    1. Spatial finite difference exterior derivatives dA across nearest nodes.
    2. Register-unrolled non-linear Lie algebra cubic commutators [A, A].
    3. Poincaré metric vielbein scaling: lambda_z = 2 / (1 - ||z||^2).
    4. Gradient descent flow: A_{t+1} = A_t - dt * (lambda_z^2 * B_t + damping * A_t).
"""

import time
import torch
import triton
import triton.language as tl


@triton.jit
def fused_poincare_chern_simons_gauge_kernel(
    A_ptr,          # [N, 3, 3] Gauge connection A_i^a (i in {x,y,z}, a in {1,2,3})
    Out_ptr,        # [N, 3, 3] Output evolved gauge field
    Neighbors_ptr,  # [N, 6] 6 nearest spatial neighbors (+x, -x, +y, -y, +z, -z)
    Z_ptr,          # [N, 3] Hyperbolic coordinates for vielbein scaling
    N: tl.constexpr,
    k_level: tl.float32,
    dt: tl.float32,
    damping: tl.float32,
    dx: tl.float32,
    BLOCK_SIZE: tl.constexpr,
):
    pid = tl.program_id(0)
    if pid >= N:
        return

    # Load Poincaré coordinate z and compute vielbein lambda_z = 2 / (1 - ||z||^2)
    zx = tl.load(Z_ptr + pid * 3 + 0)
    zy = tl.load(Z_ptr + pid * 3 + 1)
    zz = tl.load(Z_ptr + pid * 3 + 2)
    norm_sq = zx * zx + zy * zy + zz * zz
    lambda_z = 2.0 / (1.0 - norm_sq + 1e-6)
    conf_factor = lambda_z * lambda_z

    # Load current node A_i^a: 9 components
    # We unroll: A[i, a] where i is direction (0:x, 1:y, 2:z), a is color (0, 1, 2)
    # A_00, A_01, A_02, A_10, A_11, A_12, A_20, A_21, A_22
    A_00 = tl.load(A_ptr + pid * 9 + 0)
    A_01 = tl.load(A_ptr + pid * 9 + 1)
    A_02 = tl.load(A_ptr + pid * 9 + 2)

    A_10 = tl.load(A_ptr + pid * 9 + 3)
    A_11 = tl.load(A_ptr + pid * 9 + 4)
    A_12 = tl.load(A_ptr + pid * 9 + 5)

    A_20 = tl.load(A_ptr + pid * 9 + 6)
    A_21 = tl.load(A_ptr + pid * 9 + 7)
    A_22 = tl.load(A_ptr + pid * 9 + 8)

    # Load spatial neighbors for finite-difference curl:
    # 0: +x, 1: -x, 2: +y, 3: -y, 4: +z, 5: -z
    nb_px = tl.load(Neighbors_ptr + pid * 6 + 0)
    nb_mx = tl.load(Neighbors_ptr + pid * 6 + 1)
    nb_py = tl.load(Neighbors_ptr + pid * 6 + 2)
    nb_my = tl.load(Neighbors_ptr + pid * 6 + 3)
    nb_pz = tl.load(Neighbors_ptr + pid * 6 + 4)
    nb_mz = tl.load(Neighbors_ptr + pid * 6 + 5)

    inv_2dx = 0.5 / dx

    # Exterior derivative dA:
    # (curl A)_x^a = partial_y A_z^a - partial_z A_y^a
    # (curl A)_y^a = partial_z A_x^a - partial_x A_z^a
    # (curl A)_z^a = partial_x A_y^a - partial_y A_x^a

    # We evaluate for a=0, 1, 2:
    # Curl component X:
    dAy_pz_0 = tl.load(A_ptr + nb_py * 9 + 6) # A_z at +y
    dAy_mz_0 = tl.load(A_ptr + nb_my * 9 + 6) # A_z at -y
    dAz_py_0 = tl.load(A_ptr + nb_pz * 9 + 3) # A_y at +z
    dAz_my_0 = tl.load(A_ptr + nb_mz * 9 + 3) # A_y at -z
    curl_x_0 = (dAy_pz_0 - dAy_mz_0 - (dAz_py_0 - dAz_my_0)) * inv_2dx

    dAy_pz_1 = tl.load(A_ptr + nb_py * 9 + 7)
    dAy_mz_1 = tl.load(A_ptr + nb_my * 9 + 7)
    dAz_py_1 = tl.load(A_ptr + nb_pz * 9 + 4)
    dAz_my_1 = tl.load(A_ptr + nb_mz * 9 + 4)
    curl_x_1 = (dAy_pz_1 - dAy_mz_1 - (dAz_py_1 - dAz_my_1)) * inv_2dx

    dAy_pz_2 = tl.load(A_ptr + nb_py * 9 + 8)
    dAy_mz_2 = tl.load(A_ptr + nb_my * 9 + 8)
    dAz_py_2 = tl.load(A_ptr + nb_pz * 9 + 5)
    dAz_my_2 = tl.load(A_ptr + nb_mz * 9 + 5)
    curl_x_2 = (dAy_pz_2 - dAy_mz_2 - (dAz_py_2 - dAz_my_2)) * inv_2dx

    # Non-linear commutator [A_y, A_z]^a = eps_{abc} A_y^b A_z^c
    comm_x_0 = A_11 * A_22 - A_12 * A_21
    comm_x_1 = A_12 * A_20 - A_10 * A_22
    comm_x_2 = A_10 * A_21 - A_11 * A_20

    # Total flux B_x:
    Bx_0 = curl_x_0 + comm_x_0
    Bx_1 = curl_x_1 + comm_x_1
    Bx_2 = curl_x_2 + comm_x_2

    # Repeat for Curl component Y:
    # (curl A)_y = partial_z A_x - partial_x A_z
    dAz_px_0 = tl.load(A_ptr + nb_pz * 9 + 0)
    dAz_mx_0 = tl.load(A_ptr + nb_mz * 9 + 0)
    dAx_pz_0 = tl.load(A_ptr + nb_px * 9 + 6)
    dAx_mz_0 = tl.load(A_ptr + nb_mx * 9 + 6)
    curl_y_0 = (dAz_px_0 - dAz_mx_0 - (dAx_pz_0 - dAx_mz_0)) * inv_2dx

    dAz_px_1 = tl.load(A_ptr + nb_pz * 9 + 1)
    dAz_mx_1 = tl.load(A_ptr + nb_mz * 9 + 1)
    dAx_pz_1 = tl.load(A_ptr + nb_px * 9 + 7)
    dAx_mz_1 = tl.load(A_ptr + nb_mx * 9 + 7)
    curl_y_1 = (dAz_px_1 - dAz_mx_1 - (dAx_pz_1 - dAx_mz_1)) * inv_2dx

    dAz_px_2 = tl.load(A_ptr + nb_pz * 9 + 2)
    dAz_mx_2 = tl.load(A_ptr + nb_mz * 9 + 2)
    dAx_pz_2 = tl.load(A_ptr + nb_px * 9 + 8)
    dAx_mz_2 = tl.load(A_ptr + nb_mx * 9 + 8)
    curl_y_2 = (dAz_px_2 - dAz_mx_2 - (dAx_pz_2 - dAx_mz_2)) * inv_2dx

    comm_y_0 = A_21 * A_02 - A_22 * A_01
    comm_y_1 = A_22 * A_00 - A_20 * A_02
    comm_y_2 = A_20 * A_01 - A_21 * A_00

    By_0 = curl_y_0 + comm_y_0
    By_1 = curl_y_1 + comm_y_1
    By_2 = curl_y_2 + comm_y_2

    # Repeat for Curl component Z:
    # (curl A)_z = partial_x A_y - partial_y A_x
    dAx_py_0 = tl.load(A_ptr + nb_px * 9 + 3)
    dAx_my_0 = tl.load(A_ptr + nb_mx * 9 + 3)
    dAy_px_0 = tl.load(A_ptr + nb_py * 9 + 0)
    dAy_mx_0 = tl.load(A_ptr + nb_my * 9 + 0)
    curl_z_0 = (dAx_py_0 - dAx_my_0 - (dAy_px_0 - dAy_mx_0)) * inv_2dx

    dAx_py_1 = tl.load(A_ptr + nb_px * 9 + 4)
    dAx_my_1 = tl.load(A_ptr + nb_mx * 9 + 4)
    dAy_px_1 = tl.load(A_ptr + nb_py * 9 + 1)
    dAy_mx_1 = tl.load(A_ptr + nb_my * 9 + 1)
    curl_z_1 = (dAx_py_1 - dAx_my_1 - (dAy_px_1 - dAy_mx_1)) * inv_2dx

    dAx_py_2 = tl.load(A_ptr + nb_px * 9 + 5)
    dAx_my_2 = tl.load(A_ptr + nb_mx * 9 + 5)
    dAy_px_2 = tl.load(A_ptr + nb_py * 9 + 2)
    dAy_mx_2 = tl.load(A_ptr + nb_my * 9 + 2)
    curl_z_2 = (dAx_py_2 - dAx_my_2 - (dAy_px_2 - dAy_mx_2)) * inv_2dx

    comm_z_0 = A_01 * A_12 - A_02 * A_11
    comm_z_1 = A_02 * A_10 - A_00 * A_12
    comm_z_2 = A_00 * A_11 - A_01 * A_10

    Bz_0 = curl_z_0 + comm_z_0
    Bz_1 = curl_z_1 + comm_z_1
    Bz_2 = curl_z_2 + comm_z_2

    # Chern-Simons gradient flow update:
    scale_cs = (k_level / 12.56637061) * conf_factor

    new_A_00 = A_00 - dt * (scale_cs * Bx_0 + damping * A_00)
    new_A_01 = A_01 - dt * (scale_cs * Bx_1 + damping * A_01)
    new_A_02 = A_02 - dt * (scale_cs * Bx_2 + damping * A_02)

    new_A_10 = A_10 - dt * (scale_cs * By_0 + damping * A_10)
    new_A_11 = A_11 - dt * (scale_cs * By_1 + damping * A_11)
    new_A_12 = A_12 - dt * (scale_cs * By_2 + damping * A_12)

    new_A_20 = A_20 - dt * (scale_cs * Bz_0 + damping * A_20)
    new_A_21 = A_21 - dt * (scale_cs * Bz_1 + damping * A_21)
    new_A_22 = A_22 - dt * (scale_cs * Bz_2 + damping * A_22)

    tl.store(Out_ptr + pid * 9 + 0, new_A_00)
    tl.store(Out_ptr + pid * 9 + 1, new_A_01)
    tl.store(Out_ptr + pid * 9 + 2, new_A_02)
    tl.store(Out_ptr + pid * 9 + 3, new_A_10)
    tl.store(Out_ptr + pid * 9 + 4, new_A_11)
    tl.store(Out_ptr + pid * 9 + 5, new_A_12)
    tl.store(Out_ptr + pid * 9 + 6, new_A_20)
    tl.store(Out_ptr + pid * 9 + 7, new_A_21)
    tl.store(Out_ptr + pid * 9 + 8, new_A_22)


def triton_poincare_chern_simons_flow(A, neighbors, z, k_level=2.0, dt=0.01, damping=0.05, dx=0.1):
    N = A.shape[0]
    out = torch.empty_like(A)
    grid = (N,)
    fused_poincare_chern_simons_gauge_kernel[grid](
        A, out, neighbors, z,
        N=N, k_level=k_level, dt=dt, damping=damping, dx=dx,
        BLOCK_SIZE=1,
    )
    return out


def pytorch_poincare_chern_simons_flow(A, neighbors, z, k_level=2.0, dt=0.01, damping=0.05, dx=0.1):
    N = A.shape[0]
    norm_sq = torch.sum(z * z, dim=-1, keepdim=True)
    lambda_z = 2.0 / (1.0 - norm_sq + 1e-6)
    conf_factor = (lambda_z * lambda_z).unsqueeze(-1) # [N, 1, 1]

    # Reshape A to [N, 3, 3]: A[:, i, a]
    A_mat = A.view(N, 3, 3)

    nb_px, nb_mx = neighbors[:, 0], neighbors[:, 1]
    nb_py, nb_my = neighbors[:, 2], neighbors[:, 3]
    nb_pz, nb_mz = neighbors[:, 4], neighbors[:, 5]

    inv_2dx = 0.5 / dx

    # Curl A
    curl = torch.zeros_like(A_mat)
    # (curl A)_x = d_y A_z - d_z A_y
    curl[:, 0, :] = (A_mat[nb_py, 2, :] - A_mat[nb_my, 2, :] - (A_mat[nb_pz, 1, :] - A_mat[nb_mz, 1, :])) * inv_2dx
    # (curl A)_y = d_z A_x - d_x A_z
    curl[:, 1, :] = (A_mat[nb_pz, 0, :] - A_mat[nb_mz, 0, :] - (A_mat[nb_px, 2, :] - A_mat[nb_mx, 2, :])) * inv_2dx
    # (curl A)_z = d_x A_y - d_y A_x
    curl[:, 2, :] = (A_mat[nb_px, 1, :] - A_mat[nb_mx, 1, :] - (A_mat[nb_py, 0, :] - A_mat[nb_my, 0, :])) * inv_2dx

    # Non-linear commutator [A_j, A_k]
    comm = torch.zeros_like(A_mat)
    # x: A_y x A_z
    comm[:, 0, :] = torch.cross(A_mat[:, 1, :], A_mat[:, 2, :], dim=-1)
    # y: A_z x A_x
    comm[:, 1, :] = torch.cross(A_mat[:, 2, :], A_mat[:, 0, :], dim=-1)
    # z: A_x x A_y
    comm[:, 2, :] = torch.cross(A_mat[:, 0, :], A_mat[:, 1, :], dim=-1)

    flux = curl + comm
    scale_cs = (k_level / 12.56637061) * conf_factor

    new_A = A_mat - dt * (scale_cs * flux + damping * A_mat)
    return new_A.view(N, 9)


def benchmark_chern_simons():
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    print(f"[*] Running Poincaré Chern-Simons Gauge Benchmark on: {torch.cuda.get_device_name(device)}")

    # 3D Grid: 32 x 32 x 32 = 32,768 nodes
    L = 32
    N = L * L * L
    print(f"[*] 3D Lattice Size: {L}^3 = {N:,} gauge nodes (294,912 field components)")

    # Build 3D periodic neighbor indices
    coords = torch.arange(N, device=device).view(L, L, L)
    nb_px = torch.roll(coords, shifts=-1, dims=0).view(-1)
    nb_mx = torch.roll(coords, shifts=1, dims=0).view(-1)
    nb_py = torch.roll(coords, shifts=-1, dims=1).view(-1)
    nb_my = torch.roll(coords, shifts=1, dims=1).view(-1)
    nb_pz = torch.roll(coords, shifts=-1, dims=2).view(-1)
    nb_mz = torch.roll(coords, shifts=1, dims=2).view(-1)
    neighbors = torch.stack([nb_px, nb_mx, nb_py, nb_my, nb_pz, nb_mz], dim=1).contiguous()

    torch.manual_seed(42)
    A = (torch.randn(N, 9, device=device) * 0.1).contiguous()
    z = (torch.randn(N, 3, device=device) * 0.15).contiguous()

    # Numerical correctness check
    triton_out = triton_poincare_chern_simons_flow(A, neighbors, z)
    torch_out = pytorch_poincare_chern_simons_flow(A, neighbors, z)

    max_err = torch.max(torch.abs(triton_out - torch_out)).item()
    print(f"[✓] Numerical Correctness Validated. Max absolute error: {max_err:.8e}")
    assert max_err < 1e-5, f"Triton error too high: {max_err}"

    # Latency benchmark
    iters = 100
    for _ in range(20):
        _ = triton_poincare_chern_simons_flow(A, neighbors, z)
        _ = pytorch_poincare_chern_simons_flow(A, neighbors, z)
    torch.cuda.synchronize()

    t0 = time.perf_counter()
    for _ in range(iters):
        _ = triton_poincare_chern_simons_flow(A, neighbors, z)
    torch.cuda.synchronize()
    triton_time = (time.perf_counter() - t0) / iters

    t0 = time.perf_counter()
    for _ in range(iters):
        _ = pytorch_poincare_chern_simons_flow(A, neighbors, z)
    torch.cuda.synchronize()
    torch_time = (time.perf_counter() - t0) / iters

    speedup = torch_time / triton_time
    throughput = (N * 9) / (triton_time * 1e6)

    print(f"[*] PyTorch Latency: {torch_time * 1e6:.2f} µs")
    print(f"[*] Triton Latency:  {triton_time * 1e6:.2f} µs")
    print(f"[✓] Triton Speedup:  {speedup:.2f}x")
    print(f"[✓] Throughput:      {throughput:.2f} Million field elements/s")


if __name__ == "__main__":
    benchmark_chern_simons()
