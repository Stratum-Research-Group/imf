"""
IMF Triton Fused Poincaré Riemannian AdamW Optimizer Kernel
============================================================
Performs in-place Riemannian gradient descent with momentum and adaptive learning rate
for parameter tensors theta living inside the Poincaré ball:

1. Riemannian Gradient Scaling:
   grad_R = ((1 - ||theta||^2)^2 / 4) * grad_E

2. Exponential Moving Averages:
   m_t = beta1 * m_{t-1} + (1 - beta1) * grad_R
   v_t = beta2 * v_{t-1} + (1 - beta2) * (grad_R)^2

3. Bias-Corrected Step Direction:
   step = lr * (m_t / (1 - beta1^t)) / (sqrt(v_t / (1 - beta2^t)) + eps) + wd * theta

4. Geodesic Exponential Retraction:
   theta_{t+1} = exp_{theta_t}(-step)

Executes the entire Riemannian optimization step inside GPU register SRAM.
"""

import math
import time
import torch
import triton
import triton.language as tl


@triton.jit
def _fused_poincare_adamw_kernel(
    Theta_ptr,       # [B, D] Parameters in Poincare ball (in-place updated)
    Grad_ptr,        # [B, D] Euclidean gradients
    ExpAvg_ptr,      # [B, D] First moment m_t
    ExpAvgSq_ptr,    # [B, D] Second moment v_t
    B, D,
    stride_tb, stride_td,
    stride_gb, stride_gd,
    stride_mb, stride_md,
    stride_vb, stride_vd,
    lr: tl.constexpr,
    beta1: tl.constexpr,
    beta2: tl.constexpr,
    weight_decay: tl.constexpr,
    eps: tl.constexpr,
    step_count: tl.constexpr,
    BLOCK_B: tl.constexpr,
    BLOCK_D: tl.constexpr,
):
    pid_b = tl.program_id(0)
    offs_b = pid_b * BLOCK_B + tl.arange(0, BLOCK_B)
    offs_d = tl.arange(0, BLOCK_D)

    mask_b = offs_b < B
    mask_d = offs_d < D

    # Compute ||theta||^2 across D chunks
    norm_th_sq = tl.zeros([BLOCK_B], dtype=tl.float32)
    for d_idx in range(0, tl.cdiv(D, BLOCK_D)):
        curr_d = d_idx * BLOCK_D + offs_d
        mask_curr_d = curr_d < D

        th_ptrs = Theta_ptr + (offs_b[:, None] * stride_tb + curr_d[None, :] * stride_td)
        th_val = tl.load(th_ptrs, mask=mask_b[:, None] & mask_curr_d[None, :], other=0.0).to(tl.float32)
        norm_th_sq += tl.sum(th_val * th_val, axis=1)

    # Conformal scaling factor: lambda_theta = 2 / (1 - ||theta||^2)
    alpha_th = tl.maximum(1.0 - norm_th_sq, eps)
    # Riemannian metric inverse factor: 1 / lambda_theta^2 = (1 - ||theta||^2)^2 / 4
    riemann_scale = (alpha_th * alpha_th) / 4.0
    lambda_th = 2.0 / alpha_th

    bias_correction1 = 1.0 - tl.exp(step_count * tl.log(beta1))
    bias_correction2 = 1.0 - tl.exp(step_count * tl.log(beta2))

    # Pass 2: compute step direction v and accumulate ||step||^2
    norm_v_sq = tl.zeros([BLOCK_B], dtype=tl.float32)
    for d_idx in range(0, tl.cdiv(D, BLOCK_D)):
        curr_d = d_idx * BLOCK_D + offs_d
        mask_curr_d = curr_d < D

        th_ptrs = Theta_ptr + (offs_b[:, None] * stride_tb + curr_d[None, :] * stride_td)
        g_ptrs = Grad_ptr + (offs_b[:, None] * stride_gb + curr_d[None, :] * stride_gd)
        m_ptrs = ExpAvg_ptr + (offs_b[:, None] * stride_mb + curr_d[None, :] * stride_md)
        v_ptrs = ExpAvgSq_ptr + (offs_b[:, None] * stride_vb + curr_d[None, :] * stride_vd)

        th_val = tl.load(th_ptrs, mask=mask_b[:, None] & mask_curr_d[None, :], other=0.0).to(tl.float32)
        g_val = tl.load(g_ptrs, mask=mask_b[:, None] & mask_curr_d[None, :], other=0.0).to(tl.float32)
        m_val = tl.load(m_ptrs, mask=mask_b[:, None] & mask_curr_d[None, :], other=0.0).to(tl.float32)
        var_val = tl.load(v_ptrs, mask=mask_b[:, None] & mask_curr_d[None, :], other=0.0).to(tl.float32)

        # Rescale Euclidean gradient to Riemannian gradient
        g_riemann = riemann_scale[:, None] * g_val

        # Update moments
        m_new = beta1 * m_val + (1.0 - beta1) * g_riemann
        var_new = beta2 * var_val + (1.0 - beta2) * (g_riemann * g_riemann)

        # Store updated moments
        tl.store(m_ptrs, m_new, mask=mask_b[:, None] & mask_curr_d[None, :])
        tl.store(v_ptrs, var_new, mask=mask_b[:, None] & mask_curr_d[None, :])

        # Step direction in tangent space: step = - (lr * (m_hat / (sqrt(v_hat) + eps)) + wd * theta)
        m_hat = m_new / bias_correction1
        v_hat = var_new / bias_correction2
        step_dir = -(lr * (m_hat / (tl.sqrt(v_hat) + eps)) + weight_decay * th_val)

        norm_v_sq += tl.sum(step_dir * step_dir, axis=1)

    norm_v = tl.sqrt(tl.maximum(norm_v_sq, 0.0))
    arg_tanh = (lambda_th * norm_v) / 2.0
    tanh_val = (1.0 - tl.exp(-2.0 * arg_tanh)) / tl.maximum(1.0 + tl.exp(-2.0 * arg_tanh), eps)
    tanh_val = tl.minimum(tanh_val, 1.0 - eps)

    w_scale = tl.where(norm_v > eps, tanh_val / norm_v, 0.0)
    norm_w_sq = tanh_val * tanh_val

    # Pass 3: compute <theta, w>
    dot_th_w = tl.zeros([BLOCK_B], dtype=tl.float32)
    for d_idx in range(0, tl.cdiv(D, BLOCK_D)):
        curr_d = d_idx * BLOCK_D + offs_d
        mask_curr_d = curr_d < D

        th_ptrs = Theta_ptr + (offs_b[:, None] * stride_tb + curr_d[None, :] * stride_td)
        g_ptrs = Grad_ptr + (offs_b[:, None] * stride_gb + curr_d[None, :] * stride_gd)
        m_ptrs = ExpAvg_ptr + (offs_b[:, None] * stride_mb + curr_d[None, :] * stride_md)
        v_ptrs = ExpAvgSq_ptr + (offs_b[:, None] * stride_vb + curr_d[None, :] * stride_vd)

        th_val = tl.load(th_ptrs, mask=mask_b[:, None] & mask_curr_d[None, :], other=0.0).to(tl.float32)
        m_val = tl.load(m_ptrs, mask=mask_b[:, None] & mask_curr_d[None, :], other=0.0).to(tl.float32)
        var_val = tl.load(v_ptrs, mask=mask_b[:, None] & mask_curr_d[None, :], other=0.0).to(tl.float32)

        m_hat = m_val / bias_correction1
        v_hat = var_val / bias_correction2
        step_dir = -(lr * (m_hat / (tl.sqrt(v_hat) + eps)) + weight_decay * th_val)

        w_val = w_scale[:, None] * step_dir
        dot_th_w += tl.sum(th_val * w_val, axis=1)

    denom_out = tl.maximum(1.0 + 2.0 * dot_th_w + norm_th_sq * norm_w_sq, eps)
    c_th = (1.0 + 2.0 * dot_th_w + norm_w_sq) / denom_out
    c_w = alpha_th / denom_out

    # Pass 4: write updated theta_{t+1}
    for d_idx in range(0, tl.cdiv(D, BLOCK_D)):
        curr_d = d_idx * BLOCK_D + offs_d
        mask_curr_d = curr_d < D

        th_ptrs = Theta_ptr + (offs_b[:, None] * stride_tb + curr_d[None, :] * stride_td)
        m_ptrs = ExpAvg_ptr + (offs_b[:, None] * stride_mb + curr_d[None, :] * stride_md)
        v_ptrs = ExpAvgSq_ptr + (offs_b[:, None] * stride_vb + curr_d[None, :] * stride_vd)

        th_val = tl.load(th_ptrs, mask=mask_b[:, None] & mask_curr_d[None, :], other=0.0).to(tl.float32)
        m_val = tl.load(m_ptrs, mask=mask_b[:, None] & mask_curr_d[None, :], other=0.0).to(tl.float32)
        var_val = tl.load(v_ptrs, mask=mask_b[:, None] & mask_curr_d[None, :], other=0.0).to(tl.float32)

        m_hat = m_val / bias_correction1
        v_hat = var_val / bias_correction2
        step_dir = -(lr * (m_hat / (tl.sqrt(v_hat) + eps)) + weight_decay * th_val)

        w_val = w_scale[:, None] * step_dir
        theta_next = c_th[:, None] * th_val + c_w[:, None] * w_val

        tl.store(th_ptrs, theta_next.to(tl.float16), mask=mask_b[:, None] & mask_curr_d[None, :])


def triton_poincare_adamw(
    Theta: torch.Tensor,
    Grad: torch.Tensor,
    ExpAvg: torch.Tensor,
    ExpAvgSq: torch.Tensor,
    lr: float = 1e-3,
    beta1: float = 0.9,
    beta2: float = 0.999,
    weight_decay: float = 0.01,
    eps: float = 1e-8,
    step_count: int = 1,
):
    assert Theta.is_cuda and Grad.is_cuda
    B, D = Theta.shape

    BLOCK_B = 64
    BLOCK_D = min(128, triton.next_power_of_2(D))
    grid = (triton.cdiv(B, BLOCK_B),)

    _fused_poincare_adamw_kernel[grid](
        Theta, Grad, ExpAvg, ExpAvgSq,
        B, D,
        Theta.stride(0), Theta.stride(1),
        Grad.stride(0), Grad.stride(1),
        ExpAvg.stride(0), ExpAvg.stride(1),
        ExpAvgSq.stride(0), ExpAvgSq.stride(1),
        lr=lr,
        beta1=beta1,
        beta2=beta2,
        weight_decay=weight_decay,
        eps=eps,
        step_count=step_count,
        BLOCK_B=BLOCK_B,
        BLOCK_D=BLOCK_D,
    )
    return Theta


def benchmark_poincare_adamw():
    print("=" * 80)
    print("  IMF TRITON FUSED POINCARÉ RIEMANNIAN ADAMW OPTIMIZER BENCHMARK")
    print("=" * 80)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if not torch.cuda.is_available():
        print("[!] CUDA not available, skipping hardware kernel benchmark.")
        return

    B = 4096   # Number of parameter vectors
    D = 128    # Parameter dimension
    print(f"[*] Workload: Parameter Vectors B={B}, Dim D={D} ({B * D:,} hyperbolic weights)")

    torch.manual_seed(42)
    Theta = torch.randn((B, D), device=device, dtype=torch.float16)
    Theta = Theta / (Theta.norm(dim=-1, keepdim=True) + 1e-4) * 0.75

    Grad = torch.randn((B, D), device=device, dtype=torch.float16) * 0.01
    ExpAvg = torch.zeros((B, D), device=device, dtype=torch.float32)
    ExpAvgSq = torch.zeros((B, D), device=device, dtype=torch.float32)

    # Warmup
    for step in range(1, 3):
        _ = triton_poincare_adamw(Theta, Grad, ExpAvg, ExpAvgSq, step_count=step)
    torch.cuda.synchronize()

    # Latency Benchmark
    iters = 10
    start = time.perf_counter()
    for step in range(3, 3 + iters):
        _ = triton_poincare_adamw(Theta, Grad, ExpAvg, ExpAvgSq, step_count=step)
    torch.cuda.synchronize()
    elapsed = (time.perf_counter() - start) / iters

    total_params = B * D
    throughput = total_params / elapsed / 1e6
    print(f"[✓] Execution Latency: {elapsed * 1000:.3f} ms ({elapsed * 1e6:.1f} µs)")
    print(f"[✓] Optimizer Throughput: {throughput:.2f} Million weights updated/sec")
    print(f"[*] Post-Update Norm Check: Max ||theta|| = {Theta.norm(dim=-1).max().item():.4f} (Strictly < 1.0)")
    assert Theta.norm(dim=-1).max().item() < 1.0, "Riemannian parameter escaped Poincare ball!"
    print("=" * 80)


if __name__ == "__main__":
    benchmark_poincare_adamw()
