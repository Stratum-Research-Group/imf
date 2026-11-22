import torch
import pytest
from imf.leech_lattice import generate_leech24_minimal_roots, LeechLinear

def test_leech24_minimal_roots_structure():
    roots = generate_leech24_minimal_roots()
    assert roots.shape == (196560, 24)
    assert roots.dtype == torch.float32
    norms = torch.norm(roots, p=2, dim=1)
    # Every minimal root has norm exactly sqrt(8) ~ 2.82842712
    assert torch.allclose(norms, torch.full_like(norms, 2.82842712), atol=1e-5)

def test_leech_linear_forward():
    roots = generate_leech24_minimal_roots()
    layer = LeechLinear(in_features=96, out_features=48, codebook=roots)
    x = torch.randn(2, 4, 96)
    out = layer(x)
    assert out.shape == (2, 4, 48)

@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA not available")
def test_leech_linear_cuda():
    roots = generate_leech24_minimal_roots()
    layer = LeechLinear(in_features=96, out_features=48, codebook=roots).cuda().half()
    x = torch.randn(1, 96, device='cuda', dtype=torch.float16)
    out = layer(x)
    assert out.shape == (1, 48)
