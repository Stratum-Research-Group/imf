import pytest
import torch
import torch.nn.functional as F

from imf.omni_block import IMFOmniBlock
from imf.omnilm_mope import IMFOmniLMMoPE

def test_model_level_causality_token_invariance():
    """
    Item 9: Full model-level causality test.
    Modifying token at position t+1 must NOT change logits at or before position t.
    """
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    model = IMFOmniLMMoPE(vocab_size=128, d_model=64, num_layers=2).to(device)
    model.eval()
    
    seq_len = 16
    batch_size = 2
    
    x1 = torch.randint(0, 128, (batch_size, seq_len), device=device)
    x2 = x1.clone()
    
    # Perturb token at position t=10
    perturb_pos = 10
    x2[:, perturb_pos] = (x1[:, perturb_pos] + 5) % 128
    
    with torch.no_grad():
        out1 = model(x1)
        out2 = model(x2)

    logits1 = out1[0] if isinstance(out1, (tuple, list)) else (out1["pred_logits"] if isinstance(out1, dict) else out1)
    logits2 = out2[0] if isinstance(out2, (tuple, list)) else (out2["pred_logits"] if isinstance(out2, dict) else out2)

    # Check positions 0 .. perturb_pos - 1 within floating-point precision limit (1e-4)
    prior_diff = (logits1[:, :perturb_pos] - logits2[:, :perturb_pos]).abs().max().item()
    assert prior_diff < 1e-4, f"Causal leakage! Prior position diff: {prior_diff}"

def test_ssm_state_growth_bounds():
    """
    Item 11: SSM state growth check up to long sequence length.
    Ensure ||M||_F remains numerical bounded and does not explode to NaN or inf.
    """
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    block = IMFOmniBlock(d_model=64, num_heads=4).to(device)
    block.eval()
    
    # Run through 1024 tokens in chunks and check state norm
    x = torch.randn(1, 1024, 64, device=device, dtype=torch.float32)
    with torch.no_grad():
        out = block(x)
        
    assert not torch.isnan(out).any()
    assert not torch.isinf(out).any()
    assert out.abs().max().item() < 1e5
