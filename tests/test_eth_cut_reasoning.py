import pytest
import torch
from imf.eth_cut_reasoning import BidirectionalCutReasoning


def test_bidirectional_cut_reasoning_forward():
    d_model = 64
    cut_module = BidirectionalCutReasoning(d_model=d_model, num_cuts=2)

    B, T = 4, 16
    fwd = torch.randn(B, T, d_model, requires_grad=True)
    bwd = torch.randn(B, T, d_model, requires_grad=True)

    out, metrics = cut_module(fwd, bwd)

    assert out.shape == (B, T, d_model)
    assert "cut_compatibility" in metrics
    assert "crossing_energy" in metrics
    assert not torch.isnan(out).any()

    # Autograd backward verification
    loss = out.sum()
    loss.backward()
    assert fwd.grad is not None
    assert bwd.grad is not None
    assert cut_module.raw_singlet.grad is not None


@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA required for GPU verification")
def test_bidirectional_cut_reasoning_cuda():
    device = torch.device("cuda")
    d_model = 64
    cut_module = BidirectionalCutReasoning(d_model=d_model, num_cuts=2).to(device)

    B, T = 4, 16
    fwd = torch.randn(B, T, d_model, device=device, requires_grad=True)
    bwd = torch.randn(B, T, d_model, device=device, requires_grad=True)

    out, metrics = cut_module(fwd, bwd)
    assert out.device.type == "cuda"
    loss = out.sum()
    loss.backward()
    assert fwd.grad is not None
