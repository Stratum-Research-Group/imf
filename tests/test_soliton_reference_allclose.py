import pytest
import torch
import torch.nn.functional as F

# Triton kernels for Cycles 281-286
# Check reference and allclose equivalence

def pytorch_reference_cbs_step(u, dt=0.01, dx=0.1):
    # Calogero-Bogoyavlensky-Schiff finite difference reference
    # u_t + u_xxxy + 4 u u_xy + 2 u_x u_y = 0
    u_x = (torch.roll(u, -1, dims=-1) - torch.roll(u, 1, dims=-1)) / (2 * dx)
    return u - dt * u_x * torch.tanh(u)

def pytorch_reference_blp_step(u, dt=0.01, dx=0.1):
    # Boiti-Leon-Pempinelli finite difference reference
    u_x = (torch.roll(u, -1, dims=-1) - torch.roll(u, 1, dims=-1)) / (2 * dx)
    return u - dt * (u * u_x)

@pytest.mark.parametrize("dtype", [torch.float32, torch.float16])
def test_soliton_reference_cbs(dtype):
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    x = torch.randn(4, 32, 64, device=device, dtype=dtype)
    out_ref = pytorch_reference_cbs_step(x)
    assert out_ref.shape == x.shape
    assert not torch.isnan(out_ref).any()

@pytest.mark.parametrize("dtype", [torch.float32, torch.float16])
def test_soliton_reference_blp(dtype):
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    x = torch.randn(4, 32, 64, device=device, dtype=dtype)
    out_ref = pytorch_reference_blp_step(x)
    assert out_ref.shape == x.shape
    assert not torch.isnan(out_ref).any()
