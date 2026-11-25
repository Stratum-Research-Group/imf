import pytest
import torch
import torch.nn.functional as F

from imf.triton_unitary_ssm_kernel import fused_unitary_ssm_forward

@pytest.mark.parametrize("d_head", [16, 32, 64])
@pytest.mark.parametrize("seq_len", [8, 32])
def test_triton_ssm_kernel_vs_pytorch_reference(d_head, seq_len):
    """
    Validates fused Triton unitary SSM kernel against pure PyTorch double-precision / float32
    reference simulation across multiple head dimensions and sequence lengths.
    """
    if not torch.cuda.is_available():
        pytest.skip("CUDA device required for Triton kernel tests")
        
    device = "cuda"
    batch_size = 2
    num_heads = 4
    
    torch.manual_seed(42 + d_head)
    q = torch.randn(batch_size, num_heads, seq_len, d_head, device=device, dtype=torch.float32)
    k = torch.randn(batch_size, num_heads, seq_len, d_head, device=device, dtype=torch.float32)
    v = torch.randn(batch_size, num_heads, seq_len, d_head, device=device, dtype=torch.float32)
    
    # Generate random orthogonal rotation matrices U in SO(d_head)
    U_raw = torch.randn(num_heads, d_head, d_head, device=device, dtype=torch.float32)
    U, _ = torch.linalg.qr(U_raw)
    
    # 1. Sequential ground-truth reference simulation
    out_ref = []
    for b in range(batch_size):
        head_outs = []
        for h in range(num_heads):
            M = torch.zeros(d_head, d_head, device=device, dtype=torch.float32)
            u_h = U[h]
            u_h_T = u_h.T
            t_outs = []
            for t in range(seq_len):
                q_t = q[b, h, t].unsqueeze(-1)
                k_t = k[b, h, t].unsqueeze(-1)
                v_t = v[b, h, t].unsqueeze(-1)
                W_t = torch.matmul(v_t, k_t.T) - torch.matmul(k_t, v_t.T)
                M = u_h @ M @ u_h_T + W_t
                y_t = M @ q_t
                t_outs.append(y_t.squeeze(-1))
            head_outs.append(torch.stack(t_outs, dim=0))
        out_ref.append(torch.stack(head_outs, dim=0))
    expected = torch.stack(out_ref, dim=0)
    
    # 2. Triton fused execution
    actual = fused_unitary_ssm_forward(q, k, v, U)
    
    # 3. Allclose verification
    max_diff = (actual - expected).abs().max().item()
    assert torch.allclose(actual, expected, atol=1e-3, rtol=1e-3), (
        f"Triton SSM kernel diverged from PyTorch reference! Max diff: {max_diff:.3e} for d_head={d_head}, seq_len={seq_len}"
    )
