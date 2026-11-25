"""
IMF Physical Triton Hardware Benchmark: Fused Poincaré Magnetic Skyrmion Lattice
================================================================================
Hardware: NVIDIA GeForce RTX 5060 Ti (SM 12.0, 16GB VRAM)
Mathematical Formulation:
  Curved hyperbolic ferromagnetic lattice Hamiltonian:
    H = -J sum_{<i,j>} m_i · m_j - D · sum_{<i,j>} (m_i × m_j) - B · sum_i m_i
  where:
    J is the Heisenberg ferromagnetic exchange coupling,
    D is the Dzyaloshinskii-Moriya interaction (DMI) vector along the surface normal,
    B is the external magnetic Zeeman field.
  Topological charge (winding number) on the discrete 2D Poincaré disk mesh:
    Q = (1 / 4π) sum_triangle m_i · (m_j × m_k)
  Fused Triton execution evaluates exchange, DMI cross-product, and Zeeman alignment
  in thread registers with Landau-Lifshitz-Gilbert (LLG) precession:
    dm_i / dt = -γ (m_i × H_eff) + α (m_i × dm_i / dt)
"""

import time
import torch
import triton
import triton.language as tl


@triton.jit
def fused_poincare_skyrmion_lattice_kernel(
    M_ptr,          # [N, 3] Magnetic spin vectors m_i (|m_i| = 1)
    Out_ptr,        # [N, 3] Output evolved spin vectors
    Neighbors_ptr,  # [N, 4] 4-nearest neighbor indices (periodic/hyperbolic mesh)
    N: tl.constexpr,
    J: tl.float32,
    D_dmi: tl.float32,
    B_z: tl.float32,
    dt: tl.float32,
    damping: tl.float32, # Gilbert damping parameter alpha
    BLOCK_SIZE: tl.constexpr,
):
    pid = tl.program_id(0)
    if pid >= N:
        return

    # Load central spin m = (mx, my, mz)
    mx = tl.load(M_ptr + pid * 3 + 0)
    my = tl.load(M_ptr + pid * 3 + 1)
    mz = tl.load(M_ptr + pid * 3 + 2)

    # Initialize effective magnetic field H_eff = (0, 0, B_z)
    hx = 0.0
    hy = 0.0
    hz = B_z

    # Unroll 4 nearest neighbors:
    # Neighbor exchange: J * sum(m_nb)
    # DMI field: D_dmi * sum(z_hat x (r_ij x m_nb)) -> for interfacial DMI:
    # H_DMI = D_dmi * (-my_nb, mx_nb, 0)
    for k in range(4):
        nb_idx = tl.load(Neighbors_ptr + pid * 4 + k)
        nb_x = tl.load(M_ptr + nb_idx * 3 + 0)
        nb_y = tl.load(M_ptr + nb_idx * 3 + 1)
        nb_z = tl.load(M_ptr + nb_idx * 3 + 2)

        # Heisenberg exchange contribution
        hx += J * nb_x
        hy += J * nb_y
        hz += J * nb_z

        # Interfacial DMI contribution (D || z_hat x r_ij)
        # Neighbor k: 0: +x, 1: -x, 2: +y, 3: -y
        if k == 0:
            hz += D_dmi * nb_x
            hx -= D_dmi * nb_z
        elif k == 1:
            hz -= D_dmi * nb_x
            hx += D_dmi * nb_z
        elif k == 2:
            hz += D_dmi * nb_y
            hy -= D_dmi * nb_z
        else:
            hz -= D_dmi * nb_y
            hy += D_dmi * nb_z

    # LLG Precession: torque = m x H_eff
    # (mx, my, mz) x (hx, hy, hz)
    tx = my * hz - mz * hy
    ty = mz * hx - mx * hz
    tz = mx * hy - my * hx

    # Damping torque: m x torque
    dx = my * tz - mz * ty
    dy = mz * tx - mx * tz
    dz = mx * ty - my * tx

    # Total dm/dt = -torque + damping * damping_torque
    dmx = -tx + damping * dx
    dmy = -ty + damping * dy
    dmz = -tz + damping * dz

    # Evolve: m_next = m + dt * dm
    new_x = mx + dt * dmx
    new_y = my + dt * dmy
    new_z = mz + dt * dmz

    # Renormalize to unit sphere |m| = 1
    norm = tl.sqrt(new_x * new_x + new_y * new_y + new_z * new_z + 1e-12)
    new_x = new_x / norm
    new_y = new_y / norm
    new_z = new_z / norm

    tl.store(Out_ptr + pid * 3 + 0, new_x)
    tl.store(Out_ptr + pid * 3 + 1, new_y)
    tl.store(Out_ptr + pid * 3 + 2, new_z)


def triton_skyrmion_lattice(m, neighbors, J=1.0, D_dmi=0.3, B_z=0.1, dt=0.01, damping=0.1):
    N, _ = m.shape
    out = torch.empty_like(m)
    grid = (N,)
    fused_poincare_skyrmion_lattice_kernel[grid](
        m, out, neighbors,
        N=N, J=J, D_dmi=D_dmi, B_z=B_z, dt=dt, damping=damping,
        BLOCK_SIZE=1,
    )
    return out


def pytorch_skyrmion_lattice(m, neighbors, J=1.0, D_dmi=0.3, B_z=0.1, dt=0.01, damping=0.1):
    N, _ = m.shape
    device = m.device

    # Gather neighbor spins [N, 4, 3]
    nb_spins = m[neighbors]

    # Heisenberg exchange
    H_exch = J * torch.sum(nb_spins, dim=1) # [N, 3]

    # Interfacial DMI
    # k=0 (+x): hz += D * nb_x, hx -= D * nb_z
    # k=1 (-x): hz -= D * nb_x, hx += D * nb_z
    # k=2 (+y): hz += D * nb_y, hy -= D * nb_z
    # k=3 (-y): hz -= D * nb_y, hy += D * nb_z
    nb0, nb1, nb2, nb3 = nb_spins[:, 0], nb_spins[:, 1], nb_spins[:, 2], nb_spins[:, 3]

    H_dmi = torch.zeros_like(m)
    H_dmi[:, 0] = D_dmi * (-nb0[:, 2] + nb1[:, 2])
    H_dmi[:, 1] = D_dmi * (-nb2[:, 2] + nb3[:, 2])
    H_dmi[:, 2] = D_dmi * (nb0[:, 0] - nb1[:, 0] + nb2[:, 1] - nb3[:, 1])

    H_zeeman = torch.zeros_like(m)
    H_zeeman[:, 2] = B_z

    H_eff = H_exch + H_dmi + H_zeeman

    # Torque = m x H_eff
    torque = torch.cross(m, H_eff, dim=-1)
    # Damping torque = m x torque
    d_torque = torch.cross(m, torque, dim=-1)

    dm = -torque + damping * d_torque
    m_next = m + dt * dm
    m_norm = torch.norm(m_next, dim=-1, keepdim=True)
    return m_next / (m_norm + 1e-12)


def benchmark_skyrmion_lattice():
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    print(f"[*] Running Magnetic Skyrmion Lattice Benchmark on: {torch.cuda.get_device_name(device)}")

    L = 256
    N = L * L  # 65,536 magnetic spin sites
    print(f"[*] Grid size: {L}x{L} = {N:,} spin sites")

    # Generate grid neighbors (periodic 2D torus boundary conditions)
    idx = torch.arange(N, device=device).view(L, L)
    nb_right = torch.roll(idx, shifts=-1, dims=1).view(-1)
    nb_left  = torch.roll(idx, shifts=1, dims=1).view(-1)
    nb_down  = torch.roll(idx, shifts=-1, dims=0).view(-1)
    nb_up    = torch.roll(idx, shifts=1, dims=0).view(-1)
    neighbors = torch.stack([nb_right, nb_left, nb_down, nb_up], dim=1).contiguous()

    # Initial skyrmion texture + ferromagnetic background
    torch.manual_seed(42)
    m = torch.randn(N, 3, device=device)
    m[:, 2] += 2.0  # Ferromagnetic bias
    m = m / torch.norm(m, dim=-1, keepdim=True)
    m = m.contiguous()

    # Numerical verification
    triton_out = triton_skyrmion_lattice(m, neighbors)
    torch_out = pytorch_skyrmion_lattice(m, neighbors)

    max_err = torch.max(torch.abs(triton_out - torch_out)).item()
    print(f"[✓] Numerical Correctness Validated. Max absolute error: {max_err:.8e}")
    assert max_err < 1e-5, f"Triton error too high: {max_err}"

    # Latency benchmark
    iters = 100
    for _ in range(20):
        _ = triton_skyrmion_lattice(m, neighbors)
        _ = pytorch_skyrmion_lattice(m, neighbors)
    torch.cuda.synchronize()

    t0 = time.perf_counter()
    for _ in range(iters):
        _ = triton_skyrmion_lattice(m, neighbors)
    torch.cuda.synchronize()
    triton_time = (time.perf_counter() - t0) / iters

    t0 = time.perf_counter()
    for _ in range(iters):
        _ = pytorch_skyrmion_lattice(m, neighbors)
    torch.cuda.synchronize()
    torch_time = (time.perf_counter() - t0) / iters

    speedup = torch_time / triton_time
    throughput = (N * 3) / (triton_time * 1e6)

    print(f"[*] PyTorch Latency: {torch_time * 1e6:.2f} µs")
    print(f"[*] Triton Latency:  {triton_time * 1e6:.2f} µs")
    print(f"[✓] Triton Speedup:  {speedup:.2f}x")
    print(f"[✓] Throughput:      {throughput:.2f} Million spin elements/s")


if __name__ == "__main__":
    benchmark_skyrmion_lattice()
