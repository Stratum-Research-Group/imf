"""
Triton Fused Polytope Gated Linear Unit (P-GLU) Activation Kernel
================================================================
Computes non-Euclidean Gated Linear Units directly in GPU SRAM registers:
    y = (gate) ⊙ silu(up) · \\lambda(z)
with online hyperbolic Poincaré metric retraction:
    \\lambda(z) = \\frac{2}{1 - \\min(\\|z\\|^2, 0.998)}
Eliminates intermediate HBM allocations during feed-forward MoE expert layer execution.
"""

import time
import torch
import triton
import triton.language as tl


@triton.jit
def _fused_polytope_glu_kernel(
    gate_ptr,              # [BATCH, DIM] fp16
    up_ptr,                # [BATCH, DIM] fp16
    out_ptr,               # [BATCH, DIM] fp16
    poincare_coords_ptr,   # [BATCH, 2] fp16 (Poincaré embedding)
    BATCH_SIZE,
    DIM: tl.constexpr,     # e.g. 512, 1024, or 2048
    BLOCK_SIZE: tl.constexpr,
):
    pid_b = tl.program_id(0)
    pid_d = tl.program_id(1)

    offs_d = pid_d * BLOCK_SIZE + tl.arange(0, BLOCK_SIZE)
    mask_d = offs_d < DIM

    # Load Poincaré coordinates for this token to compute Riemannian scale
    px = tl.load(poincare_coords_ptr + pid_b * 2 + 0).to(tl.float32)
    py = tl.load(poincare_coords_ptr + pid_b * 2 + 1).to(tl.float32)
    norm_sq = tl.minimum(px * px + py * py, 0.998)
    # Conformal metric scale factor: 2 / (1 - ||z||^2)
    riemannian_scale = 2.0 / (1.0 - norm_sq)

    # Load gate and up projection chunks
    offs_elem = pid_b * DIM + offs_d
    gate = tl.load(gate_ptr + offs_elem, mask=mask_d, other=0.0).to(tl.float32)
    up   = tl.load(up_ptr + offs_elem, mask=mask_d, other=0.0).to(tl.float32)

    # SiLU(up) = up * sigmoid(up) = up / (1 + exp(-up))
    sigmoid_up = tl.sigmoid(up)
    silu_up = up * sigmoid_up

    # SwiGLU modulated by Riemannian hyperbolic curvature
    # y = gate * SiLU(up) * (riemannian_scale * 0.5)
    y = gate * silu_up * (riemannian_scale * 0.5)

    # Store directly to output buffer
    tl.store(out_ptr + offs_elem, y.to(tl.float16), mask=mask_d)


def triton_fused_polytope_glu(
    gate: torch.Tensor,
    up: torch.Tensor,
    poincare_coords: torch.Tensor,
) -> torch.Tensor:
    """
    Computes fused non-Euclidean SwiGLU activation.
    gate, up: [BATCH, DIM] fp16
    poincare_coords: [BATCH, 2] fp16
    Returns: [BATCH, DIM] fp16
    """
    assert gate.is_cuda and up.is_cuda and poincare_coords.is_cuda
    batch_size, dim = gate.shape
    out = torch.empty_like(gate)

    BLOCK_SIZE = 512
    grid = (
        batch_size,
        triton.cdiv(dim, BLOCK_SIZE),
    )

    _fused_polytope_glu_kernel[grid](
        gate,
        up,
        out,
        poincare_coords,
        batch_size,
        DIM=dim,
        BLOCK_SIZE=BLOCK_SIZE,
    )
    return out


def benchmark_polytope_glu():
    if not torch.cuda.is_available():
        print("[!] CUDA not available, skipping hardware kernel benchmark.")
        return

    device = torch.device("cuda:0")
    batch_size = 16384  # 16k tokens in flight
    dim = 2048          # MoE expert intermediate dimension

    print(f"[*] Benchmarking Fused Polytope-GLU Kernel (B={batch_size:,}, D={dim})...")

    gate = torch.randn(batch_size, dim, device=device, dtype=torch.float16)
    up   = torch.randn(batch_size, dim, device=device, dtype=torch.float16)
    coords = torch.rand(batch_size, 2, device=device, dtype=torch.float16) * 0.8 - 0.4

    # Warmup
    for _ in range(5):
        _ = triton_fused_polytope_glu(gate, up, coords)
    torch.cuda.synchronize()

    # Timed run
    iters = 100
    t0 = time.perf_counter()
    for _ in range(iters):
        out = triton_fused_polytope_glu(gate, up, coords)
    torch.cuda.synchronize()
    elapsed = (time.perf_counter() - t0) / iters

    total_elements = batch_size * dim
    throughput_gb_s = (gate.nbytes + up.nbytes + out.nbytes) / elapsed / 1e9
    tok_sec = batch_size / elapsed

    print(f"[✓] Execution Time: {elapsed * 1000:.3f} ms ({elapsed * 1e6:.1f} µs)")
    print(f"[✓] Activation Throughput: {tok_sec / 1e6:.2f} M tokens/sec ({total_elements / elapsed / 1e9:.2f} B elements/sec)")
    print(f"[✓] Effective Memory Bandwidth: {throughput_gb_s:.2f} GB/s")

    # PyTorch reference validation
    norm_sq = torch.clamp((coords[:, 0]**2 + coords[:, 1]**2), max=0.998)
    r_scale = (2.0 / (1.0 - norm_sq)).unsqueeze(-1)
    silu_up = up.float() * torch.sigmoid(up.float())
    ref_out = (gate.float() * silu_up * (r_scale * 0.5)).half()

    max_err = (out - ref_out).abs().max().item()
    print(f"[✓] Max Absolute Difference vs PyTorch Analytical Ref: {max_err:.6e}")
    assert max_err <= 2e-2, f"Numerical error too high: {max_err}"
    print("[✓] Correctness verification passed!")


if __name__ == "__main__":
    benchmark_polytope_glu()
