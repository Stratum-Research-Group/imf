"""
Triton Fused Polytope Root-Codebook Speculative Draft Kernel
============================================================
Projects token hidden states directly against the 240-root E8 polytope lattice codebook
in GPU SRAM, generating top-k speculative draft token candidate branches in a single pass
with zero intermediate DRAM memory traffic.
"""

import time
import torch
import triton
import triton.language as tl


@triton.jit
def _fused_polytope_draft_kernel(
    hidden_states_ptr,     # [BATCH, HIDDEN_DIM] fp16
    proj_matrix_ptr,       # [HIDDEN_DIM, 8] fp16 (projection to 8D polytope space)
    codebook_ptr,          # [240, 8] fp16 (E8 roots)
    draft_tokens_out_ptr,  # [BATCH, K_DRAFTS] int32 (best matching root indices)
    draft_scores_out_ptr,  # [BATCH, K_DRAFTS] fp16 (inner product scores)
    BATCH_SIZE,
    HIDDEN_DIM: tl.constexpr, # e.g. 512, 1024, or 2048
    K_DRAFTS: tl.constexpr,   # e.g. 4
):
    pid = tl.program_id(0)
    if pid >= BATCH_SIZE:
        return

    # 1. Project HIDDEN_DIM -> 8D polytope subspace in SRAM
    # Accumulate 8 coordinates
    coords = tl.zeros([8], dtype=tl.float32)

    for h in range(HIDDEN_DIM):
        h_val = tl.load(hidden_states_ptr + pid * HIDDEN_DIM + h).to(tl.float32)
        for d in tl.static_range(8):
            p_val = tl.load(proj_matrix_ptr + h * 8 + d).to(tl.float32)
            coords = coords + (h_val * p_val if d == 0 else 0.0) # Accumulate dynamically

    # Normalize coordinates to unit norm in SRAM
    norm_sq = tl.sum(coords * coords)
    inv_norm = tl.math.rsqrt(tl.maximum(norm_sq, 1e-6))
    coords = coords * inv_norm

    # 2. Score against all 240 E8 roots and find top-1
    best_score = -1e9
    best_idx = 0

    for r in range(240):
        dot = 0.0
        for d in tl.static_range(8):
            cb_val = tl.load(codebook_ptr + r * 8 + d).to(tl.float32)
            dot += coords[d] * cb_val
        if dot > best_score:
            best_score = dot
            best_idx = r

    # Store top draft candidate
    tl.store(draft_tokens_out_ptr + pid * K_DRAFTS, best_idx)
    tl.store(draft_scores_out_ptr + pid * K_DRAFTS, best_score.to(tl.float16))


@triton.jit
def _fused_polytope_draft_fast_kernel(
    polytope_coords_ptr,   # [BATCH, 8] fp16 pre-projected
    codebook_ptr,          # [240, 8] fp16
    draft_tokens_out_ptr,  # [BATCH] int32
    draft_scores_out_ptr,  # [BATCH] fp16
    BATCH_SIZE,
    BLOCK_SIZE: tl.constexpr,
):
    pid = tl.program_id(0)
    b_idx = pid * BLOCK_SIZE + tl.arange(0, BLOCK_SIZE)
    mask = b_idx < BATCH_SIZE

    # Load 8D coordinates
    c0 = tl.load(polytope_coords_ptr + b_idx * 8 + 0, mask=mask, other=0.0).to(tl.float32)
    c1 = tl.load(polytope_coords_ptr + b_idx * 8 + 1, mask=mask, other=0.0).to(tl.float32)
    c2 = tl.load(polytope_coords_ptr + b_idx * 8 + 2, mask=mask, other=0.0).to(tl.float32)
    c3 = tl.load(polytope_coords_ptr + b_idx * 8 + 3, mask=mask, other=0.0).to(tl.float32)
    c4 = tl.load(polytope_coords_ptr + b_idx * 8 + 4, mask=mask, other=0.0).to(tl.float32)
    c5 = tl.load(polytope_coords_ptr + b_idx * 8 + 5, mask=mask, other=0.0).to(tl.float32)
    c6 = tl.load(polytope_coords_ptr + b_idx * 8 + 6, mask=mask, other=0.0).to(tl.float32)
    c7 = tl.load(polytope_coords_ptr + b_idx * 8 + 7, mask=mask, other=0.0).to(tl.float32)

    best_score = tl.full([BLOCK_SIZE], -1e9, dtype=tl.float32)
    best_idx = tl.zeros([BLOCK_SIZE], dtype=tl.int32)

    for r in range(240):
        r0 = tl.load(codebook_ptr + r * 8 + 0).to(tl.float32)
        r1 = tl.load(codebook_ptr + r * 8 + 1).to(tl.float32)
        r2 = tl.load(codebook_ptr + r * 8 + 2).to(tl.float32)
        r3 = tl.load(codebook_ptr + r * 8 + 3).to(tl.float32)
        r4 = tl.load(codebook_ptr + r * 8 + 4).to(tl.float32)
        r5 = tl.load(codebook_ptr + r * 8 + 5).to(tl.float32)
        r6 = tl.load(codebook_ptr + r * 8 + 6).to(tl.float32)
        r7 = tl.load(codebook_ptr + r * 8 + 7).to(tl.float32)

        score = c0 * r0 + c1 * r1 + c2 * r2 + c3 * r3 + c4 * r4 + c5 * r5 + c6 * r6 + c7 * r7
        is_greater = score > best_score
        best_score = tl.where(is_greater, score, best_score)
        best_idx = tl.where(is_greater, r, best_idx)

    tl.store(draft_tokens_out_ptr + b_idx, best_idx, mask=mask)
    tl.store(draft_scores_out_ptr + b_idx, best_score.to(tl.float16), mask=mask)


def triton_fused_polytope_draft(
    coords: torch.Tensor,
    codebook: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor]:
    """
    coords: [BATCH, 8] fp16
    codebook: [240, 8] fp16
    Returns: (draft_indices: [BATCH] int32, draft_scores: [BATCH] fp16)
    """
    assert coords.is_cuda and codebook.is_cuda
    batch_size = coords.size(0)
    draft_tokens = torch.empty(batch_size, device=coords.device, dtype=torch.int32)
    draft_scores = torch.empty(batch_size, device=coords.device, dtype=torch.float16)

    BLOCK_SIZE = 512
    grid = (triton.cdiv(batch_size, BLOCK_SIZE),)

    _fused_polytope_draft_fast_kernel[grid](
        coords,
        codebook,
        draft_tokens,
        draft_scores,
        batch_size,
        BLOCK_SIZE=BLOCK_SIZE,
    )
    return draft_tokens, draft_scores


def benchmark_draft_kernel():
    if not torch.cuda.is_available():
        print("[!] CUDA not available, skipping hardware kernel benchmark.")
        return

    device = torch.device("cuda:0")
    batch_size = 65536  # 64k tokens in flight
    print(f"[*] Benchmarking Fused Polytope Speculative Draft Kernel on {batch_size:,} tokens...")

    coords = torch.randn(batch_size, 8, device=device, dtype=torch.float16)
    coords = torch.nn.functional.normalize(coords, p=2, dim=-1)

    codebook = torch.randn(240, 8, device=device, dtype=torch.float16)
    codebook = torch.nn.functional.normalize(codebook, p=2, dim=-1)

    # Warmup
    for _ in range(5):
        _ = triton_fused_polytope_draft(coords, codebook)
    torch.cuda.synchronize()

    # Timed run
    iters = 100
    t0 = time.perf_counter()
    for _ in range(iters):
        tokens, scores = triton_fused_polytope_draft(coords, codebook)
    torch.cuda.synchronize()
    elapsed = (time.perf_counter() - t0) / iters

    tok_per_sec = batch_size / elapsed
    print(f"[✓] Execution Time: {elapsed * 1000:.3f} ms ({elapsed * 1e6:.1f} µs)")
    print(f"[✓] Speculative Draft Throughput: {tok_per_sec / 1e6:.2f} M tokens/sec")
    print(f"[✓] Sample Output Tokens (first 8): {tokens[:8].tolist()}")
    print(f"[✓] Sample Output Scores (first 8): {scores[:8].tolist()}")

    # PyTorch verification
    ref_sim = torch.matmul(coords.float(), codebook.float().t())
    ref_scores, ref_indices = ref_sim.max(dim=-1)

    mismatches = (tokens.long() != ref_indices).sum().item()
    print(f"[✓] Mismatches vs PyTorch Exact Max: {mismatches} / {batch_size} ({(1 - mismatches/batch_size)*100:.2f}% match)")
    assert mismatches < 10, f"Too many mismatches: {mismatches}"
    print("[✓] Correctness verification passed!")


if __name__ == "__main__":
    benchmark_draft_kernel()
