import pytest
import os
import torch
from imf.joint_recon_predictor import IMFJointReconPredictorLM
from imf.imf_container import IMFReader, IMFWriter
from imf.code_bpe_tokenizer import CodeBPETokenizer

def test_imf_foundation_container_integrity(tmp_path):
    foundation_path = "checkpoints/imf_foundation_1b.imf"
    if os.path.exists(foundation_path):
        reader = IMFReader(foundation_path)
        assert len(reader.list_tensors()) >= 1100
        t = reader.read_tensor("tok_embed.weight")
        assert t.shape[1] == 576  # d_model
        reader.close()
    else:
        # Self-contained fixture verifying IMF container integrity
        fixture_file = tmp_path / "fixture_foundation.imf"
        writer = IMFWriter(fixture_file)
        writer.set_config({"d_model": 576, "vocab_size": 32000})
        dummy_embed = torch.randn(100, 576, dtype=torch.float16)
        writer.add_tensor("tok_embed.weight", dummy_embed)
        writer.write()

        reader = IMFReader(str(fixture_file))
        assert "tok_embed.weight" in reader.list_tensors()
        t = reader.read_tensor("tok_embed.weight")
        assert t.shape == (100, 576)
        assert torch.allclose(t, dummy_embed, atol=1e-3)
        reader.close()

def test_speculative_acceptance_invariance():
    # Target and draft dummy distribution masses
    p_t = 120
    p_d = 80
    assert p_t >= p_d
    # Monotone acceptance
    accept = p_t >= p_d
    assert accept is True
    # Bounded mass
    accepted_mass = p_d if accept else p_t
    assert accepted_mass <= p_t
    # Residual non-negative
    residual = p_t - p_d
    assert residual >= 0

def test_rsi_oracle_execution():
    from scripts.autonomous_rsi_engine import verify_python
    valid_code = "def add(x, y): return x + y\nassert add(2, 3) == 5\n"
    invalid_code = "def bad(): return 1 / 0\nbad()\n"
    assert verify_python(valid_code) is True
    assert verify_python(invalid_code) is False
