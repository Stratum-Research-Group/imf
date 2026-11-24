r"""
IMF Triton Fused Poincaré Gyro-Loss & Cross-Entropy Kernel
==========================================================
Hardware-accelerated hyperbolic cross-entropy loss with boundary horizon barrier regularization.
Optimized with block-tiled vocabulary processing.
"""

import time
import torch
import triton
import triton.language as tl


@torch.no_grad()
def poincare_loss_torch(
    x: torch.Tensor,        # [B, D]
    targets: torch.Tensor,  # [B] (long)
    vocab: torch.Tensor,    # [V, D]
    tau: float = 1.0,
    lambda_bound: float = 0.01,
    eps: float = 1e-5,
) -> tuple[torch.Tensor, torch.Tensor]:
    """
    Reference PyTorch implementation.
    """
    B, D = x.shape
    V, _ = vocab.shape

    x_sq = torch.sum(x ** 2, dim=-1, keepdim=True).clamp(max=1.0 - eps) # [B, 1]
    v_sq = torch.sum(vocab ** 2, dim=-1, keepdim=True).t().clamp(max=1.0 - eps) # [1, V]

    diff_sq = torch.cdist(x, vocab, p=2) ** 2 # [B, V]
    denom = (1.0 - x_sq) * (1.0 - v_sq)
    alpha = 1.0 + 2.0 * diff_sq / denom.clamp(min=eps)

    d_hyper = torch.acosh(alpha.clamp(min=1.0 + eps)) # [B, V]
    logits = -tau * d_hyper # [B, V]

    target_logits = logits.gather(1, targets.unsqueeze(1)).squeeze(1) # [B]
    lse = torch.logsumexp(logits, dim=-1) # [B]
    barrier = lambda_bound / (1.0 - x_sq.squeeze(1)) # [B]

    loss = -target_logits + lse + barrier
    return loss, logits


@triton.jit
def _poincare_loss_tiled_kernel(
    X_ptr,          # [B, D]
    Targets_ptr,    # [B]
    Vocab_ptr,      # [V, D]
    Loss_ptr,       # [B]
    tau,            # float
    lambda_bound,   # float
    eps,            # float
    B: tl.constexpr,
    V: tl.constexpr,
    D: tl.constexpr,
    BLOCK_V: tl.constexpr,
    BLOCK_D: tl.constexpr,
):
    pid = tl.program_id(0)
    if pid >= B:
        return

    offs_d = tl.arange(0, BLOCK_D)
    mask_d = offs_d < D

    x = tl.load(X_ptr + pid * D + offs_d, mask=mask_d, other=0.0)
    x_sq = tl.sum(tl.where(mask_d, x * x, 0.0))
    conf_x = 1.0 - tl.minimum(x_sq, 1.0 - eps)

    target_idx = tl.load(Targets_ptr + pid)

    m = -1e9
    d_sum = 0.0
    target_logit = 0.0

    # Vectorized loop over V in chunks of BLOCK_V
    offs_v = tl.arange(0, BLOCK_V)
    for v_start in range(0, V, BLOCK_V):
        v_idx = v_start + offs_v
        mask_v = v_idx < V

        # Load Vocab chunk: [BLOCK_V, BLOCK_D]
        vocab_ptrs = Vocab_ptr + tl.expand_dims(v_idx, 1) * D + tl.expand_dims(offs_d, 0)
        mask_2d = tl.expand_dims(mask_v, 1) & tl.expand_dims(mask_d, 0)
        c = tl.load(vocab_ptrs, mask=mask_2d, other=0.0)

        # c_sq: [BLOCK_V]
        c_sq = tl.sum(tl.where(mask_2d, c * c, 0.0), axis=1)
        conf_c = 1.0 - tl.minimum(c_sq, 1.0 - eps)

        # diff_sq: [BLOCK_V]
        diff = tl.expand_dims(x, 0) - c
        diff_sq = tl.sum(tl.where(mask_2d, diff * diff, 0.0), axis=1)

        denom = tl.maximum(conf_x * conf_c, eps)
        alpha = 1.0 + 2.0 * diff_sq / denom
        alpha_clamped = tl.maximum(alpha, 1.0 + eps)

        d_hyp = tl.log(alpha_clamped + tl.sqrt(alpha_clamped * alpha_clamped - 1.0))
        logits = tl.where(mask_v, -tau * d_hyp, -1e9)

        # Check target logit
        is_target = v_idx == target_idx
        target_logit += tl.sum(tl.where(is_target, logits, 0.0))

        # Online LSE across chunk
        chunk_max = tl.max(logits, axis=0)
        new_m = tl.maximum(m, chunk_max)
        chunk_sum = tl.sum(tl.where(mask_v, tl.exp(logits - new_m), 0.0), axis=0)
        d_sum = d_sum * tl.exp(m - new_m) + chunk_sum
        m = new_m

    lse = m + tl.log(d_sum)
    barrier = lambda_bound / conf_x
    loss = -target_logit + lse + barrier

    tl.store(Loss_ptr + pid, loss)


def triton_fused_poincare_loss(
    x: torch.Tensor,        # [B, D]
    targets: torch.Tensor,  # [B]
    vocab: torch.Tensor,    # [V, D]
    tau: float = 1.0,
    lambda_bound: float = 0.01,
    eps: float = 1e-5,
) -> torch.Tensor:
    B, D = x.shape
    V, _ = vocab.shape
    assert x.is_cuda and targets.is_cuda and vocab.is_cuda, "All tensors must be on CUDA"

    x = x.contiguous()
    targets = targets.to(torch.int32).contiguous()
    vocab = vocab.contiguous()
    loss = torch.empty((B,), device=x.device, dtype=torch.float32)

    BLOCK_D = 1
    while BLOCK_D < D:
        BLOCK_D *= 2

    BLOCK_V = 16 if V >= 16 else V

    _poincare_loss_tiled_kernel[(B,)](
        x,
        targets,
        vocab,
        loss,
        tau=float(tau),
        lambda_bound=float(lambda_bound),
        eps=float(eps),
        B=B,
        V=V,
        D=D,
        BLOCK_V=BLOCK_V,
        BLOCK_D=BLOCK_D,
        num_warps=4,
    )

    return loss


if __name__ == "__main__":
    print("=" * 80)
    print("IMF Triton Fused Poincaré Gyro-Loss & Cross-Entropy Benchmark (Tiled)")
    print(f"Device: {torch.cuda.get_device_name(0)}")
    print("=" * 80)

    torch.manual_seed(42)
    device = "cuda"

    B = 4096
    V = 128
    D = 128
    tau = 2.0
    lambda_bound = 0.01

    x = torch.randn((B, D), device=device, dtype=torch.float32)
    x = x / (torch.norm(x, dim=-1, keepdim=True) + 1e-5) * torch.rand((B, 1), device=device) * 0.90

    vocab = torch.randn((V, D), device=device, dtype=torch.float32)
    vocab = vocab / (torch.norm(vocab, dim=-1, keepdim=True) + 1e-5) * torch.rand((V, 1), device=device) * 0.90

    targets = torch.randint(0, V, (B,), device=device, dtype=torch.long)

    # 1. Numerical Correctness
    print(f"1. Validating Numerical Equivalence against PyTorch Reference (B={B}, V={V}, D={D})...")
    loss_ref, _ = poincare_loss_torch(x, targets, vocab, tau=tau, lambda_bound=lambda_bound)
    loss_tri = triton_fused_poincare_loss(x, targets, vocab, tau=tau, lambda_bound=lambda_bound)

    max_err = torch.max(torch.abs(loss_ref - loss_tri)).item()
    print(f"   Max Abs Error: {max_err:.2e}")
    assert max_err < 1e-4, f"Numerical divergence in loss: {max_err}"
    print("   ✓ 100.0% Numerical Parity Confirmed.")

    # 2. Hardware Benchmarking
    print("\n2. Executing Workstation Hardware Benchmark (RTX 5060 Ti)...")
    warmup = 10
    iters = 50

    for _ in range(warmup):
        _ = poincare_loss_torch(x, targets, vocab, tau=tau, lambda_bound=lambda_bound)
        _ = triton_fused_poincare_loss(x, targets, vocab, tau=tau, lambda_bound=lambda_bound)
    torch.cuda.synchronize()

    t0 = time.perf_counter()
    for _ in range(iters):
        _ = poincare_loss_torch(x, targets, vocab, tau=tau, lambda_bound=lambda_bound)
    torch.cuda.synchronize()
    t_torch = (time.perf_counter() - t0) / iters

    t0 = time.perf_counter()
    for _ in range(iters):
        _ = triton_fused_poincare_loss(x, targets, vocab, tau=tau, lambda_bound=lambda_bound)
    torch.cuda.synchronize()
    t_triton = (time.perf_counter() - t0) / iters

    tp_torch = B / t_torch
    tp_triton = B / t_triton
    speedup = t_torch / t_triton

    print(f"   PyTorch Baseline Latency: {t_torch*1e6:8.2f} us | Throughput: {tp_torch/1e6:6.2f} M tokens/s")
    print(f"   Triton Fused Latency:     {t_triton*1e6:8.2f} us | Throughput: {tp_triton/1e6:6.2f} M tokens/s")
    print(f"   Hardware Speedup:         {speedup:8.2f}x")
    print("=" * 80)
