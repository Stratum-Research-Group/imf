import pytest
import torch
import torch.nn.functional as F

from imf.triton_autoregressive_cayley import fused_autoregressive_cayley_forward
from imf.triton_fused_polytope_gemm import fused_cayley_gemm

@pytest.mark.parametrize("dim", [32, 64, 128])
@pytest.mark.parametrize("batch_size", [1, 4])
def test_triton_autoregressive_cayley_parity(dim, batch_size):
    """
    Validates fused Triton autoregressive Cayley generator against pure PyTorch reference.
    """
    if not torch.cuda.is_available():
        pytest.skip("CUDA device required")
        
    device = "cuda"
    torch.manual_seed(42 + dim)
    
    x = torch.randn(batch_size, dim, device=device, dtype=torch.float32)
    A = torch.randn(dim, dim, device=device, dtype=torch.float32)
    A = 0.5 * (A - A.T) # Skew-symmetric
    W = torch.randn(dim, dim, device=device, dtype=torch.float32)
    dt = 0.02
    
    # Triton kernel execution
    actual = fused_autoregressive_cayley_forward(x, A, W, dt=dt)
    
    # Ground-truth PyTorch simulation: x_rot = x + dt * (x @ A); out = x_rot @ W
    expected = (x + dt * torch.matmul(x, A)) @ W
    
    diff = (actual - expected).abs().max().item()
    assert torch.allclose(actual, expected, atol=1e-3, rtol=1e-3), (
        f"Cayley kernel mismatch! Max diff: {diff:.3e} for dim={dim}, batch_size={batch_size}"
    )

@pytest.mark.parametrize("dim", [32, 64, 128])
@pytest.mark.parametrize("batch_size", [1, 4])
def test_triton_fused_polytope_gemm_parity(dim, batch_size):
    """
    Validates fused Triton Cayley prefill GEMM against PyTorch reference.
    """
    if not torch.cuda.is_available():
        pytest.skip("CUDA device required")
        
    device = "cuda"
    torch.manual_seed(100 + dim)
    
    x = torch.randn(batch_size, dim, device=device, dtype=torch.float32)
    A = torch.randn(dim, dim, device=device, dtype=torch.float32)
    A = 0.5 * (A - A.T)
    
    actual = fused_cayley_gemm(x, A)
    expected = x + torch.matmul(x, A)
    
    diff = (actual - expected).abs().max().item()
    assert torch.allclose(actual, expected, atol=1e-3, rtol=1e-3), (
        f"Fused Cayley GEMM mismatch! Max diff: {diff:.3e} for dim={dim}, batch_size={batch_size}"
    )
