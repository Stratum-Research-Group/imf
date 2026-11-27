import pytest
import torch
from imf.polytope_moe import PolytopeMixtureOfExperts, PolytopeExpert, FineGrainedPolytopeMoPE


def test_polytope_expert_forward():
    d_model = 64
    d_ff = 128
    expert = PolytopeExpert(d_model=d_model, d_ff=d_ff, domain_name="test_domain")
    x = torch.randn(4, 16, d_model)
    out = expert(x)
    assert out.shape == x.shape
    assert not torch.isnan(out).any()


def test_polytope_moe_forward_euclidean():
    d_model = 64
    moe = PolytopeMixtureOfExperts(
        d_model=d_model,
        num_experts=4,
        top_k=2,
        use_hyperbolic=False,
        polytope_dim=3,
    )
    x = torch.randn(2, 10, d_model, requires_grad=True)
    out, aux = moe(x)

    assert out.shape == (2, 10, d_model)
    assert "load_balance_loss" in aux
    assert aux["load_balance_loss"].item() > 0
    assert aux["topk_indices"].shape == (2, 10, 2)
    assert aux["topk_weights"].shape == (2, 10, 2)

    # Autograd backward verification
    loss = out.sum() + aux["load_balance_loss"]
    loss.backward()
    assert x.grad is not None
    assert not torch.isnan(x.grad).any()


def test_polytope_moe_forward_hyperbolic():
    d_model = 64
    moe = PolytopeMixtureOfExperts(
        d_model=d_model,
        num_experts=4,
        top_k=2,
        use_hyperbolic=True,
        polytope_dim=3,
        curvature=1.0,
    )
    x = torch.randn(2, 8, d_model, requires_grad=True)
    out, aux = moe(x)

    assert out.shape == (2, 8, d_model)
    assert aux["routing_probs"].shape == (2, 8, 4)
    # Weights should sum to 1 per token
    assert torch.allclose(aux["topk_weights"].sum(dim=-1), torch.ones(2, 8), atol=1e-5)

    loss = out.sum() + aux["load_balance_loss"]
    loss.backward()
    assert x.grad is not None
    assert not torch.isnan(x.grad).any()


@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA required for GPU verification")
def test_polytope_moe_cuda():
    device = torch.device("cuda")
    d_model = 64
    moe = PolytopeMixtureOfExperts(
        d_model=d_model,
        num_experts=4,
        top_k=2,
        use_hyperbolic=True,
    ).to(device)
    x = torch.randn(4, 16, d_model, device=device, requires_grad=True)
    out, aux = moe(x)
    assert out.device.type == "cuda"
    loss = out.sum() + aux["load_balance_loss"]
    loss.backward()
    assert x.grad is not None


def test_fine_grained_polytope_mope():
    d_model = 64
    num_micro_experts = 32
    top_k = 2
    mope = FineGrainedPolytopeMoPE(
        d_model=d_model,
        num_micro_experts=num_micro_experts,
        top_k=top_k,
        polytope_dim=8,
        repulsive_weight=0.1,
        balance_weight=0.01,
    )
    x = torch.randn(2, 8, d_model, requires_grad=True)
    out, aux = mope(x)

    assert out.shape == (2, 8, d_model)
    expected_sparsity = (1.0 - (top_k / num_micro_experts)) * 100.0
    assert abs(aux["activation_sparsity_percent"] - expected_sparsity) < 1e-3
    assert aux["load_balance_loss"].item() > 0
    assert aux["repulsive_loss"].item() >= 0
    assert "total_aux_loss" in aux

    loss = out.sum() + aux["total_aux_loss"]
    loss.backward()
    assert x.grad is not None
    assert not torch.isnan(x.grad).any()


@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA required for dual-stream test")
def test_fine_grained_polytope_mope_dual_stream_cuda():
    device = torch.device("cuda")
    d_model = 64
    mope = FineGrainedPolytopeMoPE(
        d_model=d_model,
        num_micro_experts=16,
        top_k=2,
        polytope_dim=8,
        enable_dual_stream=True,
    ).to(device)

    x = torch.randn(2, 16, d_model, device=device, requires_grad=True)
    out, aux = mope(x)

    assert out.device.type == "cuda"
    assert aux["dual_stream_active"] is True
    assert "entropy_loss" in aux
    assert "normalized_entropy" in aux
    assert out.shape == (2, 16, d_model)

    loss = out.sum() + aux["total_aux_loss"]
    loss.backward()
    assert x.grad is not None
    assert not torch.isnan(x.grad).any()


def test_fine_grained_polytope_entropy_and_capacity_overflow():
    d_model = 32
    # Small micro experts with tight capacity factor
    mope = FineGrainedPolytopeMoPE(
        d_model=d_model,
        num_micro_experts=4,
        top_k=2,
        polytope_dim=4,
        capacity_factor=0.5, # Deliberately low capacity to force overflow handling
        entropy_weight=0.05,
    )
    x = torch.randn(4, 32, d_model)
    out, aux = mope(x)
    assert out.shape == (4, 32, d_model)
    assert "normalized_entropy" in aux
    assert 0.0 <= aux["normalized_entropy"].item() <= 1.05
    assert aux["capacity_overflows"] >= 0

