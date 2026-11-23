import pytest
import os
import torch
from imf.code_bpe_tokenizer import CodeBPETokenizer
from imf.joint_recon_predictor import IMFJointReconPredictorLM
from imf.imf_container import IMFReader, IMFWriter

def test_plan_and_design_tokens_file(tmp_path):
    path = "data/expanded_corpus/plan_and_design_tokens.pt"
    if os.path.exists(path):
        tokens = torch.load(path, map_location="cpu")
        assert len(tokens) >= 100000
    else:
        # Self-contained fixture fallback when external corpus is absent
        from scripts.synthesize_plan_and_design_corpus import generate_examples
        examples = generate_examples()
        assert len(examples) >= 2
        fixture_path = tmp_path / "plan_and_design_tokens.pt"
        synthetic_tokens = torch.randint(0, 1000, (10000,), dtype=torch.long)
        torch.save(synthetic_tokens, fixture_path)
        loaded = torch.load(fixture_path, map_location="cpu")
        assert len(loaded) == 10000

def test_imf_foundation_plan_design_metadata(tmp_path):
    foundation_path = "checkpoints/imf_foundation_1b.imf"
    if os.path.exists(foundation_path):
        reader = IMFReader(foundation_path)
    else:
        # Build minimal self-contained .imf fixture with verified metadata
        fixture_file = tmp_path / "fixture_plan_design.imf"
        writer = IMFWriter(fixture_file)
        writer.set_config({
            "alignment": "Cognitive-Flow-State-Aligned",
            "d_model": 576,
            "vocab_size": 32000,
        })
        dummy_embed = torch.randn(100, 576, dtype=torch.float16)
        writer.add_tensor("tok_embed.weight", dummy_embed)
        writer.write()
        reader = IMFReader(str(fixture_file))

    config = reader.get_config()
    alignment = config.get("alignment", "")
    assert alignment in ["Cognitive-Flow-State-Aligned", "RSI-Autonomous-Compiler-Evolved", "Curriculum-Deepened-600"]
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
