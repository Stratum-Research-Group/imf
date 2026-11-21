"""
tests/test_eth_uncrossing_parallel_limiter.py
Unit tests verifying the ETH Uncrossing & Parallelism Limiter.
"""

import pytest
import torch
from imf.eth_uncrossing_parallel_limiter import ETHUncrossingParallelLimiter


def test_eth_uncrossing_isometry_norm():
    """Verify Householder reflection preserves Frobenius and Euclidean norms exactly."""
    torch.manual_seed(42)
    B, S, D = 2, 8, 64
    limiter = ETHUncrossingParallelLimiter(d_model=D, num_parallel_channels=4, max_energy_bound=100.0)
    
    x = torch.randn(B, S, D)
    orig_norms = torch.norm(x, p=2, dim=-1)
    
    out, stats = limiter(x)
    out_norms = torch.norm(out, p=2, dim=-1)
    
    # Below the ceiling, Householder uncrossing is an exact orthogonal isometry (norms match)
    assert torch.allclose(orig_norms, out_norms, atol=1e-5)


def test_eth_uncrossing_strict_overflow_prevention():
    """Verify that extreme runaway activations (> 1e6) are strictly bounded to B_max."""
    torch.manual_seed(42)
    B, S, D = 2, 4, 32
    max_bound = 16.0
    limiter = ETHUncrossingParallelLimiter(d_model=D, num_parallel_channels=4, max_energy_bound=max_bound)
    
    # Inject massive overflowing inputs
    x_overflow = torch.randn(B, S, D) * 1e8
    out, stats = limiter(x_overflow)
    
    assert torch.isfinite(out).all()
    out_norms = torch.norm(out, p=2, dim=-1)
    
    # Must be strictly <= max_bound + tolerance
    assert (out_norms <= max_bound + 1e-4).all()
    assert stats["bounded_norm"] <= max_bound + 1e-4


def test_eth_uncrossing_involution():
    """Verify that applying the Householder reflection twice is an exact involution."""
    torch.manual_seed(42)
    limiter = ETHUncrossingParallelLimiter(d_model=32, num_parallel_channels=2, max_energy_bound=50.0)
    
    x = torch.randn(4, 32)
    out1, _ = limiter(x)
    out2, _ = limiter(out1)
    
    # Since R_s(R_s(v)) = v, two applications return to the original input (up to scaling)
    assert torch.allclose(out2, x, atol=1e-5)
