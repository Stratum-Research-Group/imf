import tempfile
from pathlib import Path
import torch
import pytest
from imf.imf_container import IMFWriter, IMFReader, IMF_MAGIC

def test_imf_container_write_and_read():
    with tempfile.TemporaryDirectory() as tmpdir:
        imf_path = str(Path(tmpdir) / "test_model.imf")

        config = {
            "model_dim": 576,
            "num_layers": 16,
            "num_heads": 8,
            "architecture": "IMFJointReconPredictorLM",
        }

        # 1. Create dummy tensors
        t1 = torch.randn(128, 256, dtype=torch.float32)
        t2 = torch.randint(-127, 127, (64, 64), dtype=torch.int8)
        t3 = torch.randn(32, dtype=torch.bfloat16)

        # 2. Write container
        writer = IMFWriter(imf_path, model_config=config)
        writer.add_tensor("layer0.weight", t1)
        writer.add_tensor("layer0.quant_mask", t2)
        writer.add_tensor("layer0.bias", t3)
        writer.write()

        assert Path(imf_path).exists()

        # 3. Read back using memory mapping
        reader = IMFReader(imf_path)
        read_config = reader.get_config()
        assert read_config["model_dim"] == 576
        assert read_config["num_layers"] == 16

        names = reader.list_tensors()
        assert "layer0.weight" in names
        assert "layer0.quant_mask" in names
        assert "layer0.bias" in names

        # Verify exact round-trip tensor contents
        rec_t1 = reader.read_tensor("layer0.weight")
        assert torch.equal(rec_t1, t1)

        rec_t2 = reader.read_tensor("layer0.quant_mask")
        assert torch.equal(rec_t2, t2)

        rec_t3 = reader.read_tensor("layer0.bias")
        assert torch.equal(rec_t3, t3)

        reader.close()
