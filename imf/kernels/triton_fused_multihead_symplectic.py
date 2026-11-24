"""
Triton Fused Polytope Multi-Head Symplectic Projection Kernel
=============================================================
Computes multi-head symplectic form projections across H attention heads in parallel:
    \\Omega_h(Q_h, K_h) = Q_h^\\top J K_h = \\sum_{i=1}^{D/2} (Q_{h, 2i} K_{h, 2i+1} - Q_{h, 2i+1} K_{h, 2i})
directly in GPU vector registers with online skew-symmetric matrix multiplication.
Eliminates intermediate HBM tensor transpositions during multi-head attention.
"""

import time
import torch
import triton
import triton.language as tl


@triton.jit
def _fused_multihead_symplectic_kernel(
    q_ptr,                 # [BATCH, NUM_HEADS, SEQ_LEN, HEAD_DIM] fp16 (HEAD_DIM % 2 == 0)
    k_ptr,                 # [BATCH, NUM_HEADS, SEQ_LEN, HEAD_DIM] fp16
    omega_out_ptr,         # [BATCH, NUM_HEADS, SEQ_LEN] fp16 (symplectic inner product)
    stride_qb, stride_qh, stride_qm, stride_qd,
    stride_kb, stride_kh, stride_km, stride_kd,
    stride_ob, stride_oh, stride_om,
    BATCH_SIZE, NUM_HEADS, SEQ_LEN,
    HEAD_DIM: tl.constexpr, # e.g. 32, 64
    BLOCK_M: tl.constexpr,  # tokens per program
):
    pid_m = tl.program_id(0)
    pid_h = tl.program_id(1)
    pid_b = tl.program_id(2)

    offs_m = pid_m * BLOCK_M + tl.arange(0, BLOCK_M)
    mask_m = offs_m < SEQ_LEN

    # Accumulator for symplectic area across HEAD_DIM
    omega = tl.zeros([BLOCK_M], dtype=tl.float32)

    # Stride through coordinate pairs: (2i, 2i+1)
    for d in range(0, HEAD_DIM, 2):
        q_even_ptr = q_ptr + pid_b * stride_qb + pid_h * stride_qh + offs_m * stride_qm + d * stride_qd
        q_odd_ptr  = q_ptr + pid_b * stride_qb + pid_h * stride_qh + offs_m * stride_qm + (d + 1) * stride_qd

        k_even_ptr = k_ptr + pid_b * stride_kb + pid_h * stride_kh + offs_m * stride_km + d * stride_kd
        k_odd_ptr  = k_ptr + pid_b * stride_kb + pid_h * stride_kh + offs_m * stride_km + (d + 1) * stride_kd

        q_even = tl.load(q_even_ptr, mask=mask_m, other=0.0).to(tl.float32)
        q_odd  = tl.load(q_odd_ptr, mask=mask_m, other=0.0).to(tl.float32)

        k_even = tl.load(k_even_ptr, mask=mask_m, other=0.0).to(tl.float32)
        k_odd  = tl.load(k_odd_ptr, mask=mask_m, other=0.0).to(tl.float32)

        # Canonical symplectic pairing: q_even * k_odd - q_odd * k_even
        omega += (q_even * k_odd - q_odd * k_even)

    # Store result directly to HBM
    out_ptrs = omega_out_ptr + pid_b * stride_ob + pid_h * stride_oh + offs_m * stride_om
    tl.store(out_ptrs, omega.to(tl.float16), mask=mask_m)


def triton_fused_multihead_symplectic(
    q: torch.Tensor,
    k: torch.Tensor,
) -> torch.Tensor:
    """
    Computes per-head symplectic pairing.
    q, k: [BATCH, NUM_HEADS, SEQ_LEN, HEAD_DIM] fp16
    Returns: [BATCH, NUM_HEADS, SEQ_LEN] fp16
    """
    assert q.is_cuda and k.is_cuda
    assert q.size(-1) % 2 == 0
    batch, num_heads, seq_len, head_dim = q.shape

    omega_out = torch.empty((batch, num_heads, seq_len), device=q.device, dtype=torch.float16)

    BLOCK_M = 64
    grid = (
        triton.cdiv(seq_len, BLOCK_M),
        num_heads,
        batch,
    )

    _fused_multihead_symplectic_kernel[grid](
        q, k, omega_out,
        q.stride(0), q.stride(1), q.stride(2), q.stride(3),
        k.stride(0), k.stride(1), k.stride(2), k.stride(3),
        omega_out.stride(0), omega_out.stride(1), omega_out.stride(2),
        batch, num_heads, seq_len,
        HEAD_DIM=head_dim,
        BLOCK_M=BLOCK_M,
    )
    return omega_out


def benchmark_multihead_symplectic():
    if not torch.cuda.is_available():
        print("[!] CUDA not available, skipping hardware kernel benchmark.")
        return

    device = torch.device("cuda:0")
    batch = 4
    num_heads = 16
    seq_len = 2048
    head_dim = 64

    print(f"[*] Benchmarking Fused Multi-Head Symplectic Kernel (B={batch}, H={num_heads}, S={seq_len}, D={head_dim})...")

    q = torch.randn(batch, num_heads, seq_len, head_dim, device=device, dtype=torch.float16)
    k = torch.randn(batch, num_heads, seq_len, head_dim, device=device, dtype=torch.float16)

    # Warmup
    for _ in range(5):
        _ = triton_fused_multihead_symplectic(q, k)
    torch.cuda.synchronize()

    # Timed run
    iters = 100
    t0 = time.perf_counter()
    for _ in range(iters):
        omega = triton_fused_multihead_symplectic(q, k)
    torch.cuda.synchronize()
    elapsed = (time.perf_counter() - t0) / iters

    total_elements = batch * num_heads * seq_len
    tok_sec = (batch * seq_len) / elapsed
    bandwidth_gb_s = (q.nbytes + k.nbytes + omega.nbytes) / elapsed / 1e9

    print(f"[✓] Execution Time: {elapsed * 1000:.3f} ms ({elapsed * 1e6:.1f} µs)")
    print(f"[✓] Throughput: {tok_sec / 1e6:.2f} M tokens/sec ({total_elements / elapsed / 1e6:.2f} M head-tokens/sec)")
    print(f"[✓] Effective Memory Bandwidth: {bandwidth_gb_s:.2f} GB/s")

    # PyTorch analytical reference validation
    q_even = q[:, :, :, 0::2].float()
    q_odd  = q[:, :, :, 1::2].float()
    k_even = k[:, :, :, 0::2].float()
    k_odd  = k[:, :, :, 1::2].float()

    ref_omega = torch.sum(q_even * k_odd - q_odd * k_even, dim=-1).half()
    max_err = (omega - ref_omega).abs().max().item()
    print(f"[✓] Max Absolute Difference vs Analytical Symplectic Ref: {max_err:.6e}")
    assert max_err <= 2e-2, f"Numerical deviation too high: {max_err}"
    print("[✓] Correctness verification passed!")


if __name__ == "__main__":
    benchmark_multihead_symplectic()
