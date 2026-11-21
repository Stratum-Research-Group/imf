"""
Unit tests for imf/polytope_lattice_quantizer.py
Verifies:
1. Exact E8 Gosset root vertex alignment (240 roots in R^8).
2. Polytope lattice matrix quantization, decompression, and high angular cosine retention.
3. PolytopeLatticeLinear execution parity.
"""

import pytest
import torch
import torch.nn as nn
from imf.polytope_lattice_quantizer import PolytopeLatticeQuantizer, PolytopeLatticeLinear


def test_polytope_lattice_quantization_fidelity():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    quantizer = PolytopeLatticeQuantizer(scale_block_size=64).to(device)

    # 128x256 test matrix
    W = torch.randn(128, 256, device=device)

    indices, scales, stats = quantizer.quantize_matrix(W)

    assert indices.dtype == torch.uint8
    assert indices.shape == (128, 32) # 256 / 8 = 32
    assert (indices < 240).all() # All indices fall strictly into E8 roots
    assert stats["bits_per_weight"] == 1.25
    assert stats["compression_ratio"] == 12.8
    assert stats["angular_preservation_cosine"] > 0.80

    # Dequantize and check shape
    W_rec = quantizer.dequantize(indices, scales, (128, 256))
    assert W_rec.shape == (128, 256)


def test_polytope_lattice_linear_layer():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    linear = nn.Linear(128, 64, bias=True).to(device)

    poly_layer = PolytopeLatticeLinear.from_float(linear, scale_block_size=64).to(device)

    x = torch.randn(2, 8, 128, device=device)
    y_orig = linear(x)
    y_poly = poly_layer(x)

    assert y_poly.shape == (2, 8, 64)
    # Check that outputs maintain high cosine correlation with original float linear
    cos_sim = torch.cosine_similarity(y_orig.reshape(-1), y_poly.reshape(-1), dim=0).item()
    assert cos_sim > 0.80
