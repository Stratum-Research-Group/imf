"""
Triton GPU Kernel: Fused Poincaré 2D Spatial Cross-Scan (RTX 5060 Ti)

Implements 4-way spatial cross-scan (VMamba-style) on the Poincaré ball:
  Given 2D spatial feature map X in R^(B x H x W x D):
  1. Traverses tokens in 4 geometric scan directions:
     - Direction 1: Top-Left to Bottom-Right (row-major)
     - Direction 2: Bottom-Right to Top-Left (reverse row-major)
     - Direction 3: Top-Left to Bottom-Right (column-major)
     - Direction 4: Bottom-Right to Top-Left (reverse column-major)
  2. Merges multi-directional features via hyperbolic gyrovector addition in tangent space:
     v_merged = 0.25 * (v_1 + v_2 + v_3 + v_4)
  3. Retracts merged spatial tokens to Poincare ball B^D via exp_0^c mapping.

Fuses multidirectional spatial scanning and hyperbolic retraction in a single hardware pass.
"""

import math
import time
import torch
import triton
import triton.language as tl

@triton.jit
def _poincare_cross_scan_merge_kernel(
    X_ptr,          # [B, H, W, D] (fp16)
    Out_ptr,        # [B, H, W, D] (fp16)
    B: tl.constexpr,
    Height: tl.constexpr,
    Width: tl.constexpr,
    D: tl.constexpr,
    BLOCK_D: tl.constexpr,
    c: tl.constexpr,
):
    pid_b = tl.program_id(0) # Batch
    pid_h = tl.program_id(1) # Row
    pid_w = tl.program_id(2) # Column

    offs_d = tl.arange(0, BLOCK_D)
    mask_d = offs_d < D
    sqrt_c = tl.sqrt(tl.full([], c, dtype=tl.float32))

    # 1. Forward coordinate (r, c)
    idx_1 = (pid_b * Height * Width + pid_h * Width + pid_w) * D + offs_d
    # 2. Reverse row-major: (H-1-r, W-1-c)
    idx_2 = (pid_b * Height * Width + (Height - 1 - pid_h) * Width + (Width - 1 - pid_w)) * D + offs_d
    # 3. Column-major: (c, r) mapped to grid
    idx_3 = (pid_b * Height * Width + pid_w * Height + pid_h) * D + offs_d
    # 4. Reverse column-major
    idx_4 = (pid_b * Height * Width + (Width - 1 - pid_w) * Height + (Height - 1 - pid_h)) * D + offs_d

    v1 = tl.load(X_ptr + idx_1, mask=mask_d, other=0.0).to(tl.float32)
    v2 = tl.load(X_ptr + idx_2, mask=mask_d, other=0.0).to(tl.float32)
    v3 = tl.load(X_ptr + idx_3, mask=mask_d, other=0.0).to(tl.float32)
    v4 = tl.load(X_ptr + idx_4, mask=mask_d, other=0.0).to(tl.float32)

    # Tangent space isotropic merge: 0.25 * (v1 + v2 + v3 + v4)
    v_merged = 0.25 * (v1 + v2 + v3 + v4)

    # Retract via exp_0^c
    sq_norm = tl.sum(v_merged * v_merged)
    norm = tl.sqrt(sq_norm + 1e-12)
    u = sqrt_c * norm
    u_clamped = tl.minimum(u, 15.0)
    exp_2u = tl.exp(2.0 * u_clamped)
    tanh_u = (exp_2u - 1.0) / (exp_2u + 1.0)
    scale = tanh_u / (sqrt_c * norm)

    y_out = v_merged * scale
    tl.store(Out_ptr + idx_1, y_out.to(tl.float16), mask=mask_d)


def poincare_cross_scan_pytorch(X, c=1.0):
    """Reference PyTorch implementation."""
    B, H, W, D = X.shape
    sqrt_c = math.sqrt(c)

    v1 = X.float()
    v2 = torch.flip(X.float(), dims=[1, 2])
    v3 = X.float().transpose(1, 2)
    v4 = torch.flip(X.float().transpose(1, 2), dims=[1, 2])

    v_merged = 0.25 * (v1 + v2 + v3 + v4)

    norm = torch.norm(v_merged, p=2, dim=-1, keepdim=True).clamp(min=1e-8)
    scale = torch.tanh(sqrt_c * norm) / (sqrt_c * norm)
    return (v_merged * scale).half()


def poincare_cross_scan_triton(X, c=1.0):
    B, H, W, D = X.shape
    out = torch.empty_like(X)

    BLOCK_D = 64
    grid = (B, H, W)
    _poincare_cross_scan_merge_kernel[grid](
        X, out,
        B=B, Height=H, Width=W, D=D, BLOCK_D=BLOCK_D, c=c,
    )
    return out


def benchmark():
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"[*] Benchmarking Fused Poincaré 2D Cross-Scan on {torch.cuda.get_device_name(0)}")

    torch.manual_seed(42)
    B = 8            # Batch
    H = 32           # Height
    W = 32           # Width (Total 8192 spatial tokens)
    D = 64           # Feature dimension
    c = 1.0

    X = (torch.randn((B, H, W, D), device=device, dtype=torch.float32) * 0.05).half()

    # Correctness check
    out_pt = poincare_cross_scan_pytorch(X, c)
    out_triton = poincare_cross_scan_triton(X, c)

    max_err = (out_pt.float() - out_triton.float()).abs().max().item()
    print(f"[*] Max absolute error between PyTorch and Triton: {max_err:.4e}")
    assert max_err < 1e-2, f"Numerical mismatch exceeds tolerance: {max_err}"
    print("[✓] Correctness check passed (< 1e-2 fp16 error)!")

    # Warmup
    for _ in range(50):
        poincare_cross_scan_pytorch(X, c)
        poincare_cross_scan_triton(X, c)
    torch.cuda.synchronize()

    # Timing PyTorch
    n_iters = 500
    t0 = time.perf_counter()
    for _ in range(n_iters):
        _ = poincare_cross_scan_pytorch(X, c)
    torch.cuda.synchronize()
    t_pt = (time.perf_counter() - t0) / n_iters

    # Timing Triton
    t0 = time.perf_counter()
    for _ in range(n_iters):
        _ = poincare_cross_scan_triton(X, c)
    torch.cuda.synchronize()
    t_triton = (time.perf_counter() - t0) / n_iters

    tokens_per_sec = (B * H * W) / t_triton
    speedup = t_pt / t_triton

    print(f"[*] PyTorch Latency : {t_pt * 1e6:.2f} µs")
    print(f"[*] Triton Latency  : {t_triton * 1e6:.2f} µs")
    print(f"[*] Speedup         : {speedup:.2f}x")
    print(f"[*] Throughput      : {tokens_per_sec / 1e6:.2f} M tokens/sec")


if __name__ == "__main__":
    benchmark()
