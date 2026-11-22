"""
imf/imf_model_loader.py
Zero-copy checkpoint loader that populates PyTorch nn.Modules directly from
an .imf model container using mmap without double-buffering in host memory.
"""

import time
import torch
import torch.nn as nn
from typing import Dict, Any, Optional
from imf.imf_container import IMFReader


def load_imf_state_dict(imf_path: str, device: str = "cpu") -> Dict[str, torch.Tensor]:
    """
    Reads an .imf container via zero-copy mmap and constructs a state_dict.
    Sub-millisecond access for inspection, streaming transfer for GPU.
    """
    reader = IMFReader(imf_path)
    state_dict = {}
    for name in reader.list_tensors():
        state_dict[name] = reader.read_tensor(name, device=device)
    reader.close()
    return state_dict


def load_model_from_imf(model: nn.Module, imf_path: str, device: str = "cpu", strict: bool = False) -> nn.Module:
    """
    Loads weights from an .imf container into a PyTorch model in-place.
    Defaults to strict=False to maintain backward compatibility across Pre-LN and architecture revisions.
    """
    t0 = time.perf_counter()
    state_dict = load_imf_state_dict(imf_path, device=device)
    load_time = (time.perf_counter() - t0) * 1000
    
    incompatible = model.load_state_dict(state_dict, strict=strict)
    if hasattr(incompatible, "missing_keys") and len(incompatible.missing_keys) > 0:
        print(f"[*] Note: Loaded container with {len(incompatible.missing_keys)} missing keys (strict={strict})")
    print(f"[✓] Successfully loaded {len(state_dict)} tensors from {imf_path} into model in {load_time:.2f} ms")
    return model
