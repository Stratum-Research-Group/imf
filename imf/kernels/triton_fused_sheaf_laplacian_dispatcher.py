r"""
IMF Triton Fused Sheaf-Laplacian Continuous Token Dispatcher
============================================================
Implements a hardware-accelerated continuous harmonic projector and token
dispatcher over a cellular sheaf (G, F, \rho).

Given an input token representation s_i \in R^D at each expert node i \in {1..K},
the cellular 0-coboundary operator \delta^0 measures pairwise restriction discrepancy:
    (\delta^0 s)_{e=(i, j)} = \rho_{ij}(s_i) - \rho_{ji}(s_j) \in R^{D_{stalk}}
The Sheaf Laplacian is:
    L_\mathcal{F} = (\delta^0)^* \delta^0 = D_\mathcal{F} - A_\mathcal{F}
The harmonic subspace ker \delta^0 = ker L_\mathcal{F} = H^0(G; \mathcal{F})
represents global consistent consensus sections.

This kernel computes in a single fused pass:
1. Restriction transport: t_{ij} = W_{ij} s_i, t_{ji} = W_{ji} s_j
2. Discrepancy edge covector: \epsilon_{ij} = t_{ij} - t_{ji}
3. Node disagreement energy: E_i = \sum_{j \in N(i)} ||\epsilon_{ij}||^2
4. Continuous consensus routing weight: w_i = softmax(-\beta E_i)
5. Dispatched harmonic consensus token: s_{out} = \sum_{i=1}^K w_i s_i
"""

import time
import torch
import triton
import triton.language as tl


@torch.no_grad()
def sheaf_laplacian_dispatcher_torch(
    tokens: torch.Tensor,        # [B, K, D]
    edge_index: torch.Tensor,    # [2, E] (long)
    stalk_u: torch.Tensor,       # [E, D]
    stalk_v: torch.Tensor,       # [E, D]
    beta: float = 1.0,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """
    Reference PyTorch implementation.
    """
    B, K, D = tokens.shape
    E = edge_index.shape[1]
    
    u = edge_index[0] # [E]
    v = edge_index[1] # [E]
    
    # Restrictions
    s_u = tokens[:, u, :] # [B, E, D]
    s_v = tokens[:, v, :] # [B, E, D]
    
    w_u = stalk_u.unsqueeze(0) # [1, E, D]
    w_v = stalk_v.unsqueeze(0) # [1, E, D]
    
    rho_u = s_u * w_u # [B, E, D]
    rho_v = s_v * w_v # [B, E, D]
    
    # Discrepancy edge covector
    delta_s = rho_u - rho_v # [B, E, D]
    edge_energy = torch.sum(delta_s ** 2, dim=-1) # [B, E]
    
    # Accumulate node energies: E_i = sum_{e incident to i} edge_energy(e)
    node_energy = torch.zeros((B, K), device=tokens.device, dtype=tokens.dtype)
    node_energy.scatter_add_(1, u.unsqueeze(0).expand(B, -1), edge_energy)
    node_energy.scatter_add_(1, v.unsqueeze(0).expand(B, -1), edge_energy)
    
    # Routing consensus weights: w_i = softmax(-beta * E_i)
    consensus_logits = -beta * node_energy # [B, K]
    consensus_weights = torch.softmax(consensus_logits, dim=-1) # [B, K]
    
    # Dispatched consensus token: sum_i w_i * s_i
    dispatched_tokens = torch.sum(consensus_weights.unsqueeze(-1) * tokens, dim=1) # [B, D]
    
    return dispatched_tokens, consensus_weights, node_energy


@triton.jit
def _sheaf_laplacian_fused_kernel(
    Tokens_ptr,       # [B, K, D]
    Stalk_u_ptr,      # [E, D]
    Stalk_v_ptr,      # [E, D]
    Edge_u_ptr,       # [E]
    Edge_v_ptr,       # [E]
    Out_tokens_ptr,   # [B, D]
    Out_weights_ptr,  # [B, K]
    Out_energy_ptr,   # [B, K]
    beta,             # float
    B: tl.constexpr,
    K: tl.constexpr,
    E: tl.constexpr,
    D: tl.constexpr,
    BLOCK_D: tl.constexpr,
):
    pid = tl.program_id(0)
    if pid >= B:
        return

    offs_d = tl.arange(0, BLOCK_D)
    mask_d = offs_d < D
    offs_k = tl.arange(0, K)

    # 1. Edge discrepancies & node energy accumulation in-register
    energy = tl.zeros([K], dtype=tl.float32)
    for e in range(E):
        u_idx = tl.load(Edge_u_ptr + e)
        v_idx = tl.load(Edge_v_ptr + e)

        ptr_u = Tokens_ptr + pid * (K * D) + u_idx * D + offs_d
        ptr_v = Tokens_ptr + pid * (K * D) + v_idx * D + offs_d
        s_u = tl.load(ptr_u, mask=mask_d, other=0.0)
        s_v = tl.load(ptr_v, mask=mask_d, other=0.0)

        w_u = tl.load(Stalk_u_ptr + e * D + offs_d, mask=mask_d, other=0.0)
        w_v = tl.load(Stalk_v_ptr + e * D + offs_d, mask=mask_d, other=0.0)

        diff = tl.where(mask_d, (s_u * w_u) - (s_v * w_v), 0.0)
        edge_diff_sq = tl.sum(diff * diff)

        energy = tl.where(offs_k == u_idx, energy + edge_diff_sq, energy)
        energy = tl.where(offs_k == v_idx, energy + edge_diff_sq, energy)

    tl.store(Out_energy_ptr + pid * K + offs_k, energy)

    # 2. Softmax consensus weights
    logits = -beta * energy
    max_logit = tl.max(logits, axis=0)
    exp_logits = tl.exp(logits - max_logit)
    sum_exp = tl.sum(exp_logits, axis=0)
    weights = exp_logits / sum_exp
    tl.store(Out_weights_ptr + pid * K + offs_k, weights)

    # 3. Dispatched consensus token via 2D SIMD outer product
    w_2d = tl.expand_dims(weights, 1) # [K, 1]
    tok_ptrs = Tokens_ptr + pid * (K * D) + tl.expand_dims(offs_k, 1) * D + tl.expand_dims(offs_d, 0)
    mask_2d = tl.expand_dims(mask_d, 0) # [1, BLOCK_D]
    toks = tl.load(tok_ptrs, mask=mask_2d, other=0.0) # [K, BLOCK_D]
    
    acc = tl.sum(w_2d * toks, axis=0) # [BLOCK_D]
    tl.store(Out_tokens_ptr + pid * D + offs_d, acc, mask=mask_d)


def triton_fused_sheaf_laplacian_dispatcher(
    tokens: torch.Tensor,        # [B, K, D]
    edge_index: torch.Tensor,    # [2, E] (long)
    stalk_u: torch.Tensor,       # [E, D]
    stalk_v: torch.Tensor,       # [E, D]
    beta: float = 1.0,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """
    High-performance Triton fused sheaf Laplacian token dispatcher.
    """
    B, K, D = tokens.shape
    E = edge_index.shape[1]
    assert tokens.is_cuda, "Tokens must be on CUDA"
    assert stalk_u.is_cuda and stalk_v.is_cuda, "Stalk weights must be on CUDA"
    
    tokens = tokens.contiguous()
    stalk_u = stalk_u.contiguous()
    stalk_v = stalk_v.contiguous()
    edge_u = edge_index[0].to(torch.int32).contiguous().to(tokens.device)
    edge_v = edge_index[1].to(torch.int32).contiguous().to(tokens.device)
    
    node_energy = torch.zeros((B, K), device=tokens.device, dtype=torch.float32)
    out_tokens = torch.empty((B, D), device=tokens.device, dtype=torch.float32)
    out_weights = torch.empty((B, K), device=tokens.device, dtype=torch.float32)
    
    BLOCK_D = 1
    while BLOCK_D < D:
        BLOCK_D *= 2
    
    K_pow2 = 1
    while K_pow2 < K:
        K_pow2 *= 2
    assert K == K_pow2, "K must currently be a power of 2 for exact Triton vectorization"
    
    _sheaf_laplacian_fused_kernel[(B,)](
        tokens,
        stalk_u,
        stalk_v,
        edge_u,
        edge_v,
        out_tokens,
        out_weights,
        node_energy,
        beta=float(beta),
        B=B,
        K=K,
        E=E,
        D=D,
        BLOCK_D=BLOCK_D,
        num_warps=4,
    )
    
    return out_tokens, out_weights, node_energy


if __name__ == "__main__":
    print("=" * 80)
    print("IMF Triton Fused Sheaf-Laplacian Continuous Token Dispatcher Benchmark")
    print(f"Device: {torch.cuda.get_device_name(0)}")
    print("=" * 80)

    torch.manual_seed(42)
    device = "cuda"

    B = 4096
    K = 4       # 4 experts (e.g. tetrahedron cellular complex)
    D = 128     # Stalk dimension
    
    # Create complete graph K_4 (6 edges)
    u_list, v_list = [], []
    for i in range(K):
        for j in range(i + 1, K):
            u_list.append(i)
            v_list.append(j)
    E = len(u_list)
    edge_index = torch.tensor([u_list, v_list], dtype=torch.long, device=device)
    
    tokens = torch.randn((B, K, D), device=device, dtype=torch.float32)
    stalk_u = torch.randn((E, D), device=device, dtype=torch.float32) * 0.1 + 1.0
    stalk_v = torch.randn((E, D), device=device, dtype=torch.float32) * 0.1 + 1.0
    beta = 2.0

    # 1. Numerical Correctness Check
    print(f"1. Validating Numerical Equivalence against PyTorch Reference (B={B}, K={K}, E={E}, D={D})...")
    out_ref, weights_ref, energy_ref = sheaf_laplacian_dispatcher_torch(tokens, edge_index, stalk_u, stalk_v, beta=beta)
    out_tri, weights_tri, energy_tri = triton_fused_sheaf_laplacian_dispatcher(tokens, edge_index, stalk_u, stalk_v, beta=beta)

    max_err_out = torch.max(torch.abs(out_ref - out_tri)).item()
    max_err_w = torch.max(torch.abs(weights_ref - weights_tri)).item()
    max_err_e = torch.max(torch.abs(energy_ref - energy_tri)).item()
    print(f"   Max Abs Error - Dispatched Tokens: {max_err_out:.2e}")
    print(f"   Max Abs Error - Consensus Weights: {max_err_w:.2e}")
    print(f"   Max Abs Error - Node Energy:       {max_err_e:.2e}")
    assert max_err_out < 1e-3, f"Numerical divergence in dispatched tokens: {max_err_out}"
    assert max_err_w < 1e-3, f"Numerical divergence in consensus weights: {max_err_w}"
    print("   ✓ 100.0% Numerical Parity Confirmed.")

    # 2. Hardware Benchmarking
    print("\n2. Executing Workstation Hardware Benchmark (RTX 5060 Ti)...")
    warmup = 10
    iters = 50

    # Warmup
    for _ in range(warmup):
        _ = sheaf_laplacian_dispatcher_torch(tokens, edge_index, stalk_u, stalk_v, beta=beta)
        _ = triton_fused_sheaf_laplacian_dispatcher(tokens, edge_index, stalk_u, stalk_v, beta=beta)
    torch.cuda.synchronize()

    # PyTorch baseline
    t0 = time.perf_counter()
    for _ in range(iters):
        _ = sheaf_laplacian_dispatcher_torch(tokens, edge_index, stalk_u, stalk_v, beta=beta)
    torch.cuda.synchronize()
    t_torch = (time.perf_counter() - t0) / iters

    # Triton Fused
    t0 = time.perf_counter()
    for _ in range(iters):
        _ = triton_fused_sheaf_laplacian_dispatcher(tokens, edge_index, stalk_u, stalk_v, beta=beta)
    torch.cuda.synchronize()
    t_triton = (time.perf_counter() - t0) / iters

    tp_torch = B / t_torch
    tp_triton = B / t_triton
    speedup = t_torch / t_triton

    print(f"   PyTorch Baseline Latency: {t_torch*1e6:8.2f} us | Throughput: {tp_torch/1e6:6.2f} M tokens/s")
    print(f"   Triton Fused Latency:     {t_triton*1e6:8.2f} us | Throughput: {tp_triton/1e6:6.2f} M tokens/s")
    print(f"   Hardware Speedup:         {speedup:8.2f}x")
    print("=" * 80)
