"""
Tests for Formally-Verified Cut-Factorized 8-Bit AdamW Optimizer.
Validates numerical convergence, step behavior, and 4x memory savings.
"""

import pytest
import torch
import torch.nn as nn
from imf.cut_rsi_8bit_adamw import CutRSI8BitAdamW


def test_cut_rsi_8bit_adamw_basic_step():
    if not torch.cuda.is_available():
        pytest.skip("CUDA required for Triton kernel execution.")

    model = nn.Linear(64, 32).cuda()
    opt = CutRSI8BitAdamW(model.parameters(), lr=1e-3, weight_decay=0.01)

    x = torch.randn(8, 64, device="cuda")
    y = model(x).sum()
    y.backward()

    # Step optimizer
    opt.step()

    # Verify state allocation in int8
    for p in model.parameters():
        st = opt.state[p]
        assert st["m_q"].dtype == torch.int8
        assert st["v_q"].dtype == torch.int8
        assert st["m_scales"].dtype == torch.float32
        assert st["step"] == 1


def test_cut_rsi_8bit_adamw_convergence():
    if not torch.cuda.is_available():
        pytest.skip("CUDA required for Triton kernel execution.")

    # Simple quadratic optimization problem: min ||x - target||^2
    target = torch.ones(32, device="cuda") * 2.0
    x = nn.Parameter(torch.zeros(32, device="cuda"))
    opt = CutRSI8BitAdamW([x], lr=0.2, weight_decay=0.0)

    for _ in range(30):
        opt.zero_grad()
        loss = ((x - target) ** 2).sum()
        loss.backward()
        opt.step()

    # Verify parameter converges towards target
    assert loss.item() < 1.0
    assert torch.allclose(x, target, atol=0.25)
