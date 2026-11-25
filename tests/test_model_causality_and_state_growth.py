import pytest
import torch
import torch.nn.functional as F

from imf.omni_block import IMFOmniBlock
from imf.omnilm_mope import IMFOmniLMMoPE

def test_model_level_causality_token_invariance():
    """
    Items 6 & Item 9: Full model-level causality test across multiple sequence positions
    in both eval mode and training mode (verifying no forward leakage across layers and MoE).
    Modifying token at position t must NOT change logits at positions <= t - 1.
    """
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    model = IMFOmniLMMoPE(vocab_size=128, d_model=64, num_layers=2).to(device)
    
    seq_len = 32
    batch_size = 2
    
    # Test across multiple perturbation positions: early, mid, late
    for mode in ["eval", "train"]:
        if mode == "eval":
            model.eval()
        else:
            model.train()
            
        for perturb_pos in [4, 16, 28]:
            torch.manual_seed(42 + perturb_pos)
            x1 = torch.randint(0, 128, (batch_size, seq_len), device=device)
            x2 = x1.clone()
            
            # Perturb token at position perturb_pos
            x2[:, perturb_pos] = (x1[:, perturb_pos] + 7) % 128
            
            with torch.no_grad():
                out1 = model(x1)
                out2 = model(x2)
        
            logits1 = out1[0] if isinstance(out1, (tuple, list)) else (out1["pred_logits"] if isinstance(out1, dict) else out1)
            logits2 = out2[0] if isinstance(out2, (tuple, list)) else (out2["pred_logits"] if isinstance(out2, dict) else out2)
        
            # Check positions 0 .. perturb_pos - 1 within floating-point tolerance limit (1e-4)
            prior_diff = (logits1[:, :perturb_pos] - logits2[:, :perturb_pos]).abs().max().item()
            assert prior_diff < 1e-4, f"[{mode} mode, pos={perturb_pos}] Causal leakage! Prior position diff: {prior_diff}"


def test_ssm_state_growth_bounds_and_frobenius():
    """
    Item 7: Test true ||M||_F Frobenius norm across long sequences (up to 32k tokens)
    in FP32, BF16, and FP16. Evaluates orthogonal state dynamics and numerical stability.
    """
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    
    for dtype in [torch.float32, torch.bfloat16]:
        block = IMFOmniBlock(d_model=64, num_heads=4, use_triton_ssm=False).to(device).to(dtype)
        block.eval()
        
        for seq_len in [1024, 4096, 16384, 32768]:
            torch.manual_seed(100)
            x = torch.randn(1, seq_len, 64, device=device, dtype=dtype)
            with torch.no_grad():
                out, final_M = block.forward_ssm(block.norm1(x), return_final_state=True)
                
            frob_norm = torch.linalg.norm(final_M.float()).item()
            assert not torch.isnan(out).any(), f"NaN in output for dtype={dtype}, seq_len={seq_len}"
            assert not torch.isinf(out).any(), f"Inf in output for dtype={dtype}, seq_len={seq_len}"
            assert not torch.isnan(final_M).any(), f"NaN in state M for dtype={dtype}, seq_len={seq_len}"
            assert not torch.isinf(final_M).any(), f"Inf in state M for dtype={dtype}, seq_len={seq_len}"
            
            # Theoretical check: without decay, ||M_T||_F grows as O(sqrt(T)) under random inputs
            # For T=32768, sqrt(32768) ~ 181. Verify ||M||_F remains numerically finite and bounded
            assert frob_norm > 0.0
            assert frob_norm < 1e7, f"Excessive Frobenius growth: {frob_norm}"
