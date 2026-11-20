import pytest
import torch
from imf.joint_recon_predictor import IMFJointReconPredictorLM


def test_joint_recon_predictor_forward_backward():
    vocab_size = 128
    d_model = 64
    model = IMFJointReconPredictorLM(
        vocab_size=vocab_size,
        d_model=d_model,
        num_layers=1,
        num_heads=2,
        polytope_dim=3,
        num_experts=2,
        top_k=1,
        max_seq_len=64,
        alpha_recon=0.5,
    )

    B, T = 2, 16
    x = torch.randint(0, vocab_size, (B, T))
    y = torch.randint(0, vocab_size, (B, T))

    pred_logits, recon_logits, metrics = model(x, targets=y)

    assert pred_logits.shape == (B, T, vocab_size)
    assert recon_logits.shape == (B, T, vocab_size)
    assert "total_loss" in metrics
    assert "loss_pred" in metrics
    assert "loss_recon" in metrics
    assert "effective_rank" in metrics

    loss = metrics["total_loss"]
    loss.backward()

    # Verify gradients reach embedding and reconstruction heads
    assert model.tok_embed.weight.grad is not None
    assert model.recon_head.weight.grad is not None
    assert not torch.isnan(model.tok_embed.weight.grad).any()


@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA required for GPU verification")
def test_joint_recon_predictor_cuda():
    device = torch.device("cuda")
    vocab_size = 128
    d_model = 64
    model = IMFJointReconPredictorLM(
        vocab_size=vocab_size,
        d_model=d_model,
        num_layers=1,
        num_heads=2,
        polytope_dim=3,
        num_experts=2,
        top_k=1,
        max_seq_len=64,
        alpha_recon=0.5,
    ).to(device)

    B, T = 2, 16
    x = torch.randint(0, vocab_size, (B, T), device=device)
    y = torch.randint(0, vocab_size, (B, T), device=device)

    pred_logits, recon_logits, metrics = model(x, targets=y)
    assert pred_logits.device.type == "cuda"
    assert recon_logits.device.type == "cuda"
    loss = metrics["total_loss"]
    loss.backward()
    assert model.tok_embed.weight.grad is not None
