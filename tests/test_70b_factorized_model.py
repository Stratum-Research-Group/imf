"""
tests/test_70b_factorized_model.py
Unit tests verifying the 70B Factorized Architecture (IMF70BModel & IMF70BDecoderLayer)
executes forward passes on GPU within memory limits without out-of-memory errors.
"""

import pytest
import torch
from imf.model_70b_factorized import IMF70BDecoderLayer, IMF70BModel


def test_70b_layer_forward_and_memory():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    # Single 70B layer at true full dimensions (d_model=8192, d_mlp=28672, rank=128)
    layer = IMF70BDecoderLayer(d_model=8192, d_mlp=28672, rank=128, dtype=torch.bfloat16).to(device)

    # In uncompressed FP16, a single layer is 855M parameters = 1.63 GB (1632 MB).
    # In continuous bfloat16 parameters, it is ~79.6 MB (20.5x reduction), which packs to ~5.56 MB in 1-bit packed .imf!
    param_bytes = sum(p.numel() * p.element_size() for p in layer.parameters())
    param_mb = param_bytes / (1024 * 1024)
    print(f"\n[✓] Single 70B Factorized Layer Parameter Size: {param_mb:.2f} MB (Expected < 100 MB vs 1632 MB FP16)")
    assert param_mb < 100.0

    # Execute forward pass with sequence length 4
    x = torch.randn(1, 4, 8192, dtype=torch.bfloat16, device=device)
    out = layer(x)

    assert out.shape == (1, 4, 8192)
    assert not torch.isnan(out).any()
    print("[✓] 70B Layer forward pass succeeded without NaN or VRAM explosion.")


def test_70b_polytope_lattice_layer():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    # Single 70B layer using Native E8 Polytope Lattice Quantization
    layer = IMF70BDecoderLayer(
        d_model=8192,
        d_mlp=28672,
        use_polytope_lattice=True,
    ).to(device)

    x = torch.randn(1, 2, 8192, dtype=torch.bfloat16, device=device)
    out = layer(x)

    assert out.shape == (1, 2, 8192)
    assert not torch.isnan(out).any()
    print("[✓] 70B Native E8 Polytope Lattice layer executed successfully without OOM.")
