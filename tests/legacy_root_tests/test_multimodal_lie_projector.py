"""
test_multimodal_lie_projector.py
Tests the Unified Multimodal IMF Projector (Text, Vision, Audio) under continuous Lie SSM dimension.
"""

import torch
from imf.multimodal_lie_projector import (
    LieVisionPatchProjector,
    LieAudioTemporalProjector,
    UnifiedMultimodalIMFInterface,
)

def test_multimodal_fusion():
    print("=" * 80)
    print("  Testing IMF Unified Multimodal Fusion Architecture (Vision + Audio + Text)")
    print("=" * 80)

    device = "cpu"
    d_model = 576  # Flagship 1.14B latent dimension

    # 1. Vision Projector Test
    v_proj = LieVisionPatchProjector(img_size=224, patch_size=16, in_channels=3, d_model=d_model).to(device)
    dummy_imgs = torch.randn(2, 3, 224, 224, device=device)
    v_tokens = v_proj(dummy_imgs)
    print(f"[✓] Vision Projector: Input {list(dummy_imgs.shape)} -> Patch Tokens {list(v_tokens.shape)}")
    assert v_tokens.shape == (2, 196, d_model)

    # 2. Audio Projector Test
    a_proj = LieAudioTemporalProjector(in_features=80, d_model=d_model, downsample_factor=4).to(device)
    dummy_audio = torch.randn(2, 400, 80, device=device) # 400 frames of 80-bin Mel spectrogram
    a_tokens = a_proj(dummy_audio)
    print(f"[✓] Audio Projector:  Input {list(dummy_audio.shape)} -> Temporal Tokens {list(a_tokens.shape)}")
    assert a_tokens.shape == (2, 100, d_model)

    # 3. Unified Multimodal Sequence Composition
    text_embed = torch.nn.Embedding(4096, d_model).to(device)
    mm_interface = UnifiedMultimodalIMFInterface(text_embed=text_embed, d_model=d_model).to(device)

    text_ids = torch.randint(0, 4096, (2, 32), device=device) # 32 prompt tokens
    unified_seq = mm_interface.compose_multimodal_sequence(
        text_ids=text_ids,
        images=dummy_imgs,
        audio=dummy_audio,
    )
    expected_total_len = 196 + 100 + 32  # 328 tokens
    print(f"[✓] Unified Sequence: 196 (Vision) + 100 (Audio) + 32 (Text) = {list(unified_seq.shape)}")
    assert unified_seq.shape == (2, expected_total_len, d_model)

    print("=" * 80)
    print("[✓] Multimodal Vision & Audio pipelines successfully aligned to 1.14B Lie Manifold!")

if __name__ == "__main__":
    test_multimodal_fusion()
