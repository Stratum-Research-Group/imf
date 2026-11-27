import os
import pytest

# Skip module if WEFT repo / package is not present
try:
    from imf.weft_to_imf_converter import _load_weft_format_module
    _load_weft_format_module()
except Exception:
    pytestmark = pytest.mark.skip(reason="WEFT framework not found or IMF_WEFT_PATH not configured")

"""
Tests for imf_to_weft_converter.py
Validates:
1. Full round-trip fidelity: .weft -> .imf -> .weft (lossless bitboards in factorized mode).
2. Dense IMF to WEFT binarization: .imf (dense weights) -> .weft (LittleBit-2 dual-path factors).
"""

import os
import tempfile
import torch
import numpy as np
import pytest

from imf.imf_container import IMFWriter, IMFReader
from imf.weft_to_imf_converter import convert_weft_to_imf, _load_weft_format_module
from imf.imf_to_weft_converter import convert_imf_to_weft


def test_weft_imf_roundtrip_lossless():
    WeftModelContainer, WeftSubBitLinear = _load_weft_format_module()

    with tempfile.TemporaryDirectory() as tmpdir:
        weft_orig = os.path.join(tmpdir, "orig.weft")
        imf_mid = os.path.join(tmpdir, "mid.imf")
        weft_back = os.path.join(tmpdir, "back.weft")

        # 1. Create original WEFT container
        c_orig = WeftModelContainer(metadata={"arch": "test_roundtrip", "hidden_size": 64})
        layer = WeftSubBitLinear(in_features=32, out_features=64, rank=16, num_paths=2, bias=True)
        c_orig.add_subbit_linear("encoder.linear", layer)
        c_orig.save(weft_orig)

        # 2. WEFT -> IMF (factorized)
        convert_weft_to_imf(weft_orig, imf_mid, mode="factorized")
        assert os.path.exists(imf_mid)

        # 3. IMF -> WEFT
        convert_imf_to_weft(imf_mid, weft_back)
        assert os.path.exists(weft_back)

        # 4. Read back and verify exact bitboards and scales match
        c_back = WeftModelContainer.load(weft_back)
        assert "encoder.linear" in c_back.tensors

        orig_t = c_orig.tensors["encoder.linear"]
        back_t = c_back.tensors["encoder.linear"]

        for p in range(2):
            np.testing.assert_array_equal(orig_t["paths"][p]["u_packed"], back_t["paths"][p]["u_packed"])
            np.testing.assert_array_equal(orig_t["paths"][p]["v_packed"], back_t["paths"][p]["v_packed"])
            np.testing.assert_allclose(orig_t["paths"][p]["scale_h"], back_t["paths"][p]["scale_h"], rtol=1e-3)
            np.testing.assert_allclose(orig_t["paths"][p]["scale_l"], back_t["paths"][p]["scale_l"], rtol=1e-3)
            np.testing.assert_allclose(orig_t["paths"][p]["scale_g"], back_t["paths"][p]["scale_g"], rtol=1e-3)

        np.testing.assert_allclose(orig_t["bias"], back_t["bias"], rtol=1e-3)


def test_dense_imf_to_weft_binarization():
    WeftModelContainer, WeftSubBitLinear = _load_weft_format_module()

    with tempfile.TemporaryDirectory() as tmpdir:
        imf_dense = os.path.join(tmpdir, "dense.imf")
        weft_out = os.path.join(tmpdir, "binarized.weft")

        # 1. Create dense IMF model
        writer = IMFWriter(imf_dense, model_config={"arch": "dense_model"})
        w = torch.randn(64, 32, dtype=torch.float32)
        b = torch.randn(64, dtype=torch.float16)
        writer.add_tensor("linear.weight", w)
        writer.add_tensor("linear.bias", b)
        writer.write()

        # 2. Convert dense IMF -> WEFT
        convert_imf_to_weft(imf_dense, weft_out, rank=16, num_paths=2)
        assert os.path.exists(weft_out)

        # 3. Read back WEFT and verify layer execution
        c = WeftModelContainer.load(weft_out)
        assert "linear" in c.tensors
        layer = c.get_subbit_linear("linear")

        x = torch.randn(2, 4, 32)
        y = layer(x)
        assert y.shape == (2, 4, 64)
        assert not torch.isnan(y).any()
