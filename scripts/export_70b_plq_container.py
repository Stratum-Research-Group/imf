#!/usr/bin/env python3
"""
scripts/export_70b_plq_container.py
===================================
Exports the complete 80-layer IMF 70.55B Model into a native, streaming
zero-copy .imf binary container using E8 Gosset / Leech Lattice Quantization.
"""

import sys
import os
import time
from pathlib import Path
import torch

from imf.model_70b_factorized import IMF70BModel
from imf.imf_container import IMFWriter

ROOT = Path(__file__).resolve().parent.parent
CHECKPOINTS_DIR = ROOT / "checkpoints"
CHECKPOINTS_DIR.mkdir(parents=True, exist_ok=True)


def main():
    out_path = CHECKPOINTS_DIR / "imf_70b_plq_architecture.imf"
    print("=================================================================")
    print("  IMF 70-Billion Parameter Native PLQ Container Exporter         ")
    print("  Target: E8 Gosset 240-Root Lattice & Zero-Copy Sub-Bit Format  ")
    print("=================================================================")

    num_layers = int(sys.argv[1]) if len(sys.argv) > 1 else 80
    print(f"[*] Instantiating IMF 70B Model ({num_layers} layers, d=8192, intermediate=28672)...")
    t0 = time.time()
    
    # We construct layers directly in CPU / meta memory to avoid OOM
    model = IMF70BModel(
        num_layers=num_layers,
        d_model=8192,
        d_mlp=28672,
        use_polytope_lattice=True
    )
    t1 = time.time()
    print(f"[✓] Architecture instantiated in {t1 - t0:.2f}s.")

    print(f"[*] Packaging into zero-copy binary container with disk streaming: {out_path}...")
    writer = IMFWriter(str(out_path), streaming=True)

    total_tensors = 0
    total_bytes = 0

    for name, param in model.named_parameters():
        data = param.data.cpu()
        writer.add_tensor(name, data)
        total_tensors += 1
        total_bytes += data.numel() * data.element_size()

    for name, buf in model.named_buffers():
        data = buf.data.cpu()
        writer.add_tensor(name, data)
        total_tensors += 1
        total_bytes += data.numel() * data.element_size()

    print(f"[*] Writing {total_tensors} tensors ({total_bytes / (1024**3):.2f} GB raw buffers)...")
    writer.write()
    t2 = time.time()

    actual_size = os.path.getsize(out_path) / (1024**3)
    print("-----------------------------------------------------------------")
    print(f"[✓] Container Export Complete in {t2 - t1:.2f}s!")
    print(f"  Container File: {out_path}")
    print(f"  Final File Size: {actual_size:.2f} GB")
    print("=================================================================")


if __name__ == "__main__":
    main()
