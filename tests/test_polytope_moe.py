import pytest
import torch
from imf.polytope_moe import PolytopeMixtureOfExperts, PolytopeExpert


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
