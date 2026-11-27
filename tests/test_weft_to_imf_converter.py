import os
import pytest

# Skip module if WEFT repo / package is not present
try:
    from imf.weft_to_imf_converter import _load_weft_format_module
    _load_weft_format_module()
except Exception:
    pytestmark = pytest.mark.skip(reason="WEFT framework not found or IMF_WEFT_PATH not configured")

"""
Tests for weft_to_imf_converter.py
Validates:
1. End-to-end conversion from .weft container to .imf container in 'factorized' mode.
2. End-to-end conversion from .weft container to .imf container in 'reconstructed' mode.
3. Verification of bitboards, scales, and numerical forward equivalence.
"""

import os
import sys
import tempfile
from pathlib import Path
import pytest
import torch
import numpy as np

# Ensure IMF and WEFT pathing
from imf.imf_container import IMFReader
from imf.weft_to_imf_converter import convert_weft_to_imf, _load_weft_format_module


def test_weft_to_imf_factorized_conversion():
    WeftModelContainer, WeftSubBitLinear = _load_weft_format_module()

    with tempfile.TemporaryDirectory() as tmpdir:
        weft_file = os.path.join(tmpdir, "sample.weft")
        imf_file = os.path.join(tmpdir, "sample.imf")

        # 1. Create a synthetic WEFT container
        container = WeftModelContainer(metadata={"model_type": "weft-subbit", "hidden_size": 128})
        layer0 = WeftSubBitLinear(in_features=64, out_features=128, rank=32, num_paths=2, bias=True)
        container.add_subbit_linear("layers.0.q_proj", layer0)
        container.save(weft_file)

        assert os.path.exists(weft_file)

        # 2. Convert to IMF in factorized mode
        convert_weft_to_imf(weft_file, imf_file, mode="factorized")
        assert os.path.exists(imf_file)

        # 3. Read back via IMFReader and verify contents
        reader = IMFReader(imf_file)
        config = reader.get_config()
        assert config["model_type"] == "weft-subbit"
        assert config["conversion_mode"] == "factorized"

        tensor_names = reader.list_tensors()
        expected_keys = [
            "layers.0.q_proj.path0.u_packed",
            "layers.0.q_proj.path0.v_packed",
            "layers.0.q_proj.path0.scale_h",
            "layers.0.q_proj.path0.scale_l",
            "layers.0.q_proj.path0.scale_g",
            "layers.0.q_proj.path1.u_packed",
            "layers.0.q_proj.path1.v_packed",
            "layers.0.q_proj.path1.scale_h",
            "layers.0.q_proj.path1.scale_l",
            "layers.0.q_proj.path1.scale_g",
            "layers.0.q_proj.bias",
        ]
        for k in expected_keys:
            assert k in tensor_names

        # Verify tensor shapes and data parity
        u0 = reader.read_tensor("layers.0.q_proj.path0.u_packed")
        assert u0.shape == layer0.u_packed[0].shape
        assert torch.equal(u0, layer0.u_packed[0].cpu())

        h0 = reader.read_tensor("layers.0.q_proj.path0.scale_h")
        assert torch.equal(h0, layer0.scale_h[0].cpu())

        b = reader.read_tensor("layers.0.q_proj.bias")
        assert torch.equal(b, layer0.bias.cpu())

        reader.close()


def test_weft_to_imf_reconstructed_conversion():
    WeftModelContainer, WeftSubBitLinear = _load_weft_format_module()

    with tempfile.TemporaryDirectory() as tmpdir:
        weft_file = os.path.join(tmpdir, "sample.weft")
        imf_file = os.path.join(tmpdir, "sample_recon.imf")

        # 1. Create a synthetic WEFT container
        container = WeftModelContainer(metadata={"model_type": "weft-subbit", "hidden_size": 64})
        layer = WeftSubBitLinear(in_features=32, out_features=64, rank=16, num_paths=2, bias=True)
        container.add_subbit_linear("layers.0.linear", layer)
        container.save(weft_file)

        # 2. Convert to IMF in reconstructed mode
        convert_weft_to_imf(weft_file, imf_file, mode="reconstructed", target_dtype=torch.float32)
        assert os.path.exists(imf_file)

        # 3. Read back reconstructed weight
        reader = IMFReader(imf_file)
        w_recon = reader.read_tensor("layers.0.linear.weight")
        bias_recon = reader.read_tensor("layers.0.linear.bias")
        assert w_recon.shape == (64, 32)
        assert bias_recon.shape == (64,)

        # 4. Compare forward pass of original WEFT layer vs dense matrix product
        x = torch.randn(2, 5, 32)
        y_weft = layer(x)
        y_recon = torch.matmul(x, w_recon.t()) + bias_recon

        assert torch.allclose(y_weft, y_recon, atol=1e-3, rtol=1e-3)
        reader.close()
