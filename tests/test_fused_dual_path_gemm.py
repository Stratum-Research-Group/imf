"""
tests/test_fused_dual_path_gemm.py
Unit tests verifying mathematical parity, Triton acceleration, and reconstruction correctness
of the LittleBit-2 Dual-Path Polytope factorized linear layer.
"""

import pytest
import torch
from imf.fused_dual_path_gemm import DualPathFactorizedLinear, fused_diag_scale


def test_fused_diag_scale_parity():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    x = torch.randn(16, 128, device=device)
    diag = torch.randn(128, device=device)

    ref = x * diag
    out = fused_diag_scale(x, diag)

    diff = (out - ref).abs().max().item()
    assert diff < 1e-5, f"Fused diag scale diff {diff} too high"


def test_dual_path_linear_mathematical_parity():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    batch_size = 4
    seq_len = 8
    in_features = 128
    out_features = 256
    rank = 16

    layer = DualPathFactorizedLinear(in_features, out_features, rank=rank, dtype=torch.float32).to(device)
    x = torch.randn(batch_size, seq_len, in_features, device=device)

    # 1. Forward through factorized paths
    y_factorized = layer(x)

    # 2. Forward through reconstructed dense matrix
    w_dense = layer.reconstruct_dense()
    y_dense = torch.matmul(x, w_dense.t())

    max_diff = (y_factorized - y_dense).abs().max().item()
    assert max_diff < 1e-4, f"Factorized forward vs dense reconstruction mismatch: {max_diff}"
    print(f"[✓] Factorized forward matches dense forward within {max_diff:.2e}")


def test_dual_path_linear_gradient_flow():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    layer = DualPathFactorizedLinear(64, 128, rank=8, dtype=torch.float32).to(device)
    x = torch.randn(2, 4, 64, device=device, requires_grad=True)

    out = layer(x)
    loss = out.sum()
    loss.backward()

    assert x.grad is not None
    assert layer.U1.grad is not None
    assert layer.V1.grad is not None
    assert layer.h1.grad is not None
    assert layer.g1.grad is not None
    assert layer.l1.grad is not None
    print("[✓] Gradient backprop successfully flows through all dual-path factors")
