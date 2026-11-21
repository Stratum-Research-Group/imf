import pytest
import os
import torch
from imf.code_bpe_tokenizer import CodeBPETokenizer
from imf.joint_recon_predictor import IMFJointReconPredictorLM
from imf.imf_container import IMFReader

def test_plan_and_design_tokens_file():
    path = "data/expanded_corpus/plan_and_design_tokens.pt"
    assert os.path.exists(path)
    tokens = torch.load(path, map_location="cpu")
    assert len(tokens) >= 100000

def test_imf_foundation_plan_design_metadata():
    reader = IMFReader("checkpoints/imf_foundation_1b.imf")
    config = reader.get_config()
    alignment = config.get("alignment", "")
    assert alignment in ["Cognitive-Flow-State-Aligned", "RSI-Autonomous-Compiler-Evolved"]
    reader.close()

def test_svg_and_plan_formatting():
    from scripts.synthesize_plan_and_design_corpus import generate_examples
    examples = generate_examples()
    assert len(examples) >= 2
    # At least one flagship template has embedded procedural SVG
    has_svg = any("<svg" in ex["completion"] for ex in examples)
    assert has_svg is True
    for ex in examples:
        assert "<plan>" in ex["completion"]
        assert "</plan>" in ex["completion"]
        assert "<design>" in ex["completion"]
        assert "</design>" in ex["completion"]
        assert "<code>" in ex["completion"]
        assert "</code>" in ex["completion"]
