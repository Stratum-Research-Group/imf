"""
Fused Poincaré Conformal Geodesic Metric Flow Kernel
=====================================================
Physical Workstation Benchmark: NVIDIA GeForce RTX 5060 Ti (SM 8.9)
Hardware Constrained: 16GB VRAM, 101KB Shared Memory Ceiling

Implements a continuous conformal Ricci-type metric flow on D^d_c.
Under Riemannian metric flow, the conformal factor evolves via:
  d lambda_x / dt = - R(x) * lambda_x
where R(x) = -4c / (1 - c ||x||^2)^2 is the scalar curvature.

The kernel fuses:
1. Conformal metric curvature evaluation:
   lambda_i = 2 / (1 - c * ||x_i||^2)
   R_i = -4c * (lambda_i / 2)^2
2. Metric scaling velocity integration:
   v_flow = - 0.5 * dt * R_i * x_i
3. Möbius retraction update:
   x_new = x_i (+) v_flow
"""

import math
import time
import torch
import triton
import triton.language as tl

@triton.jit
def _poincare_conformal_metric_flow_kernel(
    X_ptr,          # [B, N, D] float16 (manifold coordinate x)
    Out_ptr,        # [B, N, D] float16 (updated coordinates)
    Curvature_ptr,  # [B, N] float32 (scalar curvature R_i)
    B: tl.constexpr,
    N: tl.constexpr,
    D: tl.constexpr,
    dt: tl.constexpr,
    c: tl.constexpr,
    stride_xb, stride_xn, stride_xd,
    stride_ob, stride_on, stride_od,
    stride_cb, stride_cn,
    BLOCK_D: tl.constexpr,
):
    pid_b = tl.program_id(0)
    pid_n = tl.program_id(1)

    d_offsets = tl.arange(0, BLOCK_D)
    mask_d = d_offsets < D

    # 1. Load x_i
    x_offset = pid_b * stride_xb + pid_n * stride_xn + d_offsets * stride_xd
    x_val = tl.load(X_ptr + x_offset, mask=mask_d, other=0.0).to(tl.float32)

    # 2. Compute conformal factor lambda_x = 2 / (1 - c * ||x||^2)
    x_norm_sq = tl.sum(x_val * x_val)
    denom_x = tl.maximum(1.0 - c * x_norm_sq, 1e-4)
    # lambda_x = 2.0 / denom_x
    inv_denom_sq = 1.0 / (denom_x * denom_x)
    # Scalar curvature R_i = -4.0 * c * inv_denom_sq
    r_val = -4.0 * c * inv_denom_sq

    # Store scalar curvature
    c_offset = pid_b * stride_cb + pid_n * stride_cn
    tl.store(Curvature_ptr + c_offset, r_val)

    # 3. Flow velocity vector v_flow = - 0.5 * dt * r_val * x_val
    # (Since R < 0, this drives controlled inward geodesic contraction)
    v_flow = -0.5 * dt * r_val * x_val

    # 4. Möbius addition x (+) v_flow:
    # ( (1 + 2c <x, v> + c ||v||^2) x + (1 - c ||x||^2) v ) / ( 1 + 2c <x, v> + c^2 ||x||^2 ||v||^2 )
    v_norm_sq = tl.sum(v_flow * v_flow)
    dot_xv = tl.sum(x_val * v_flow)

    mob_num = (1.0 + 2.0 * c * dot_xv + c * v_norm_sq) * x_val + denom_x * v_flow
    mob_den = tl.maximum(1.0 + 2.0 * c * dot_xv + c * c * x_norm_sq * v_norm_sq, 1e-4)
    x_next = mob_num / mob_den

    # Project within Poincaré ball
    x_next_sq = tl.sum(x_next * x_next)
    max_sq = (1.0 / c) * 0.98
    if x_next_sq > max_sq:
        scale = tl.sqrt(max_sq / x_next_sq)
        x_next = x_next * scale

    # 5. Store updated coordinates
    out_offset = pid_b * stride_ob + pid_n * stride_on + d_offsets * stride_od
    tl.store(Out_ptr + out_offset, x_next.to(tl.float16), mask=mask_d)


def triton_poincare_conformal_metric_flow(x: torch.Tensor, dt: float = 0.001, c: float = 1.0):
    B, N, D = x.shape
    assert x.is_cuda and x.dtype == torch.float16

    out = torch.empty_like(x)
    curvature = torch.empty((B, N), device=x.device, dtype=torch.float32)

    BLOCK_D = triton.next_power_of_2(D)
    grid = (B, N)

    _poincare_conformal_metric_flow_kernel[grid](
        x, out, curvature,
        B, N, D, dt, c,
        x.stride(0), x.stride(1), x.stride(2),
        out.stride(0), out.stride(1), out.stride(2),
        curvature.stride(0), curvature.stride(1),
        BLOCK_D=BLOCK_D,
        num_warps=4,
    )
    return out, curvature


def pytorch_poincare_conformal_metric_flow_ref(x: torch.Tensor, dt: float = 0.001, c: float = 1.0):
    x_f = x.float()

    x_norm_sq = torch.sum(x_f * x_f, dim=-1, keepdim=True)
    denom_x = torch.clamp(1.0 - c * x_norm_sq, min=1e-4)
    inv_denom_sq = 1.0 / (denom_x * denom_x)
    r_val = -4.0 * c * inv_denom_sq

    v_flow = -0.5 * dt * r_val * x_f
    v_norm_sq = torch.sum(v_flow * v_flow, dim=-1, keepdim=True)
    dot_xv = torch.sum(x_f * v_flow, dim=-1, keepdim=True)

    mob_num = (1.0 + 2.0 * c * dot_xv + c * v_norm_sq) * x_f + denom_x * v_flow
    mob_den = torch.clamp(1.0 + 2.0 * c * dot_xv + c * c * x_norm_sq * v_norm_sq, min=1e-4)
    x_next = mob_num / mob_den

    x_next_sq = torch.sum(x_next * x_next, dim=-1, keepdim=True)
    max_sq = (1.0 / c) * 0.98
    x_next = torch.where(x_next_sq > max_sq, x_next * torch.sqrt(max_sq / torch.clamp(x_next_sq, min=1e-5)), x_next)

    return x_next.half(), r_val.squeeze(-1)


def benchmark():
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    print(f"[*] Benchmarking on: {torch.cuda.get_device_name(device)}")

    B, N, D = 16, 512, 128
    x = torch.randn(B, N, D, device=device, dtype=torch.float16) * 0.1
    x = x / (torch.norm(x, dim=-1, keepdim=True) + 1.2)

    # Correctness check
    out_tri, c_tri = triton_poincare_conformal_metric_flow(x, dt=0.001, c=1.0)
    out_ref, c_ref = pytorch_poincare_conformal_metric_flow_ref(x, dt=0.001, c=1.0)

    out_err = torch.max(torch.abs(out_tri - out_ref)).item()
    c_err = torch.max(torch.abs(c_tri - c_ref)).item()

    print(f"[+] Max Absolute Output Error:    {out_err:.6e}")
    print(f"[+] Max Absolute Curvature Error: {c_err:.6e}")
    assert out_err < 1e-4, f"Output error too high: {out_err}"
    assert c_err < 1e-3, f"Curvature error too high: {c_err}"
    print("[✓] Poincaré Conformal Metric Flow Correctness test PASSED.")

    # Benchmark
    warmup, iters = 20, 200
    for _ in range(warmup):
        _ = triton_poincare_conformal_metric_flow(x, dt=0.001, c=1.0)
        _ = pytorch_poincare_conformal_metric_flow_ref(x, dt=0.001, c=1.0)
    torch.cuda.synchronize()

    start_pt = time.perf_counter()
    for _ in range(iters):
        _ = pytorch_poincare_conformal_metric_flow_ref(x, dt=0.001, c=1.0)
    torch.cuda.synchronize()
    pt_time = (time.perf_counter() - start_pt) / iters

    start_tri = time.perf_counter()
    for _ in range(iters):
        _ = triton_poincare_conformal_metric_flow(x, dt=0.001, c=1.0)
    torch.cuda.synchronize()
    tri_time = (time.perf_counter() - start_tri) / iters

    speedup = pt_time / tri_time
    total_tokens = B * N
    throughput = total_tokens / tri_time

    print(f"[+] PyTorch Eager Latency: {pt_time * 1e6:.2f} µs")
    print(f"[+] Triton Fused Latency:  {tri_time * 1e6:.2f} µs")
    print(f"[+] Speedup Factor:        {speedup:.2f}x")
    print(f"[+] Processing Throughput: {throughput / 1e6:.2f}M tok/s")


if __name__ == "__main__":
    benchmark()
