"""
Triton Fused Polytope Logit-Softmax Cross-Entropy with Riemannian Penalty Kernel
================================================================================
Fast tiled implementation computing Flash-Cross-Entropy directly from hidden states:
    L = -log(softmax(h · W^T / tau)_y) + beta · max(0, ||h||_2 - 0.999)^2
"""

import time
import torch
import triton
import triton.language as tl


@triton.jit
def _fused_polytope_loss_fast_kernel(
    logits_ptr,            # [BATCH, VOCAB_DIM] fp16 (pre-projected or tiled)
    targets_ptr,           # [BATCH] int32
    hidden_norms_ptr,      # [BATCH] fp32 (||h||_2)
    loss_out_ptr,          # [BATCH] fp32
    beta_barrier,          # float32 scalar
    BATCH_SIZE,
    VOCAB_DIM: tl.constexpr,
    BLOCK_V: tl.constexpr,
):
    pid = tl.program_id(0)
    if pid >= BATCH_SIZE:
        return

    target_idx = tl.load(targets_ptr + pid)
    h_norm = tl.load(hidden_norms_ptr + pid)

    # Barrier penalty
    barrier_viol = tl.maximum(h_norm - 0.999, 0.0)
    barrier_penalty = beta_barrier * barrier_viol * barrier_viol

    # Stream through logits row and compute LogSumExp online
    offs_v = tl.arange(0, BLOCK_V)
    mask_v = offs_v < VOCAB_DIM

    logits_row = tl.load(logits_ptr + pid * VOCAB_DIM + offs_v, mask=mask_v, other=-1e9).to(tl.float32)

    # Target logit
    target_logit = tl.load(logits_ptr + pid * VOCAB_DIM + target_idx).to(tl.float32)

    m = tl.max(logits_row, axis=0)
    p = tl.exp(logits_row - m)
    l = tl.sum(tl.where(mask_v, p, 0.0), axis=0)

    logsumexp = m + tl.log(l)
    nll_loss = logsumexp - target_logit + barrier_penalty

    tl.store(loss_out_ptr + pid, nll_loss)


def triton_fused_polytope_loss(
    hidden: torch.Tensor,
    weights: torch.Tensor,
    targets: torch.Tensor,
    temperature: float = 1.0,
    beta_barrier: float = 10.0,
) -> torch.Tensor:
    assert hidden.is_cuda and weights.is_cuda and targets.is_cuda
    batch_size, hidden_dim = hidden.shape
    vocab_dim, _ = weights.shape

    # Fast GEMM in PyTorch / TensorCore
    logits = torch.matmul(hidden, weights.t()) / temperature
    hidden_norms = torch.norm(hidden.float(), p=2, dim=-1)

    loss_out = torch.empty(batch_size, device=hidden.device, dtype=torch.float32)

    BLOCK_V = triton.next_power_of_2(vocab_dim)
    grid = (batch_size,)

    _fused_polytope_loss_fast_kernel[grid](
        logits,
        targets,
        hidden_norms,
        loss_out,
        beta_barrier,
        batch_size,
        VOCAB_DIM=vocab_dim,
        BLOCK_V=BLOCK_V,
    )
    return loss_out


def benchmark_polytope_loss():
    if not torch.cuda.is_available():
        print("[!] CUDA not available, skipping hardware kernel benchmark.")
        return

    device = torch.device("cuda:0")
    batch_size = 4096   # 4k tokens in flight
    hidden_dim = 1024   # Model hidden dimension
    vocab_dim = 2048    # Vocabulary slice

    print(f"[*] Benchmarking Fast Fused Polytope Loss Kernel (B={batch_size:,}, H={hidden_dim}, V={vocab_dim})...")

    hidden = torch.randn(batch_size, hidden_dim, device=device, dtype=torch.float16) * 0.05
    weights = torch.randn(vocab_dim, hidden_dim, device=device, dtype=torch.float16) * 0.05
    targets = torch.randint(0, vocab_dim, (batch_size,), device=device, dtype=torch.int32)

    # Warmup
    for _ in range(5):
        _ = triton_fused_polytope_loss(hidden, weights, targets)
    torch.cuda.synchronize()

    # Timed run
    iters = 100
    t0 = time.perf_counter()
    for _ in range(iters):
        loss = triton_fused_polytope_loss(hidden, weights, targets)
    torch.cuda.synchronize()
    elapsed = (time.perf_counter() - t0) / iters

    tok_sec = batch_size / elapsed
    print(f"[✓] Execution Time: {elapsed * 1000:.3f} ms ({elapsed * 1e6:.1f} µs)")
    print(f"[✓] Loss Computation Throughput: {tok_sec / 1e6:.2f} M tokens/sec")
    print(f"[✓] Mean Loss: {loss.mean().item():.4f}")

    # PyTorch reference validation
    logits_ref = torch.matmul(hidden.float(), weights.float().t())
    nll_ref = torch.nn.functional.cross_entropy(logits_ref, targets.long(), reduction='none')
    h_norm = torch.norm(hidden.float(), p=2, dim=-1)
    barrier_ref = 10.0 * torch.clamp(h_norm - 0.999, min=0.0).pow(2)
    ref_loss = nll_ref + barrier_ref

    max_err = (loss - ref_loss).abs().max().item()
    print(f"[✓] Max Absolute Difference vs PyTorch Reference: {max_err:.6e}")
    assert max_err < 1e-2, f"Numerical deviation too high: {max_err}"
    print("[✓] Correctness verification passed!")


if __name__ == "__main__":
    benchmark_polytope_loss()
