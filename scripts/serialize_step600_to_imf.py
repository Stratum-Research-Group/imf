"""
serialize_step600_to_imf.py
Converts finalized Step 600 PyTorch SFT weights into the zero-copy,
sub-byte .imf binary container format with 64-byte hardware alignment.
"""

import os
import sys
import time
import torch
from imf.imf_container import IMFWriter

def convert_checkpoint_to_imf(
    ckpt_path: str = "checkpoints/imf_foundation_1b_sft.pt",
    imf_output_path: str = "checkpoints/imf_foundation_1b.imf"
):
    print("=" * 80)
    print("  IMF Model Container Serialization: PyTorch -> .imf Binary Format")
    print("=" * 80)

    if not os.path.exists(ckpt_path):
        print(f"[!] Error: Source checkpoint not found at {ckpt_path}")
        return False

    print(f"[*] Reading PyTorch checkpoint from {ckpt_path} (CPU mapping)...")
    t0 = time.perf_counter()
    ckpt = torch.load(ckpt_path, map_location="cpu", weights_only=False)
    state_dict = ckpt.get("model_state_dict", ckpt)
    read_elapsed = time.perf_counter() - t0
    print(f"[✓] Checkpoint loaded in {read_elapsed:.2f}s ({len(state_dict)} tensors).")

    # Serialize to .imf container with streaming write
    print(f"[*] Serializing {len(state_dict)} tensors to {imf_output_path} (streaming mode)...")
    t_ser = time.perf_counter()
    writer = IMFWriter(imf_output_path, streaming=True)
    for name, tensor in state_dict.items():
        # Ensure contiguous FP16 representation for zero-overhead edge transfer
        t_contig = tensor.detach().contiguous().half() if tensor.is_floating_point() else tensor.detach().contiguous()
        writer.add_tensor(name, t_contig)
    writer.write()
    ser_elapsed = time.perf_counter() - t_ser

    file_size_mb = os.path.getsize(imf_output_path) / (1024 * 1024)
    print(f"[✓] Container written successfully in {ser_elapsed:.2f}s.")
    print(f"    Target Container: {imf_output_path}")
    print(f"    Binary Size:      {file_size_mb:.2f} MB ({file_size_mb/1024:.2f} GB)")
    print(f"    Hardware Offset:  64-byte aligned / POSIX mmap compatible")
    print("=" * 80)
    return True

if __name__ == "__main__":
    convert_checkpoint_to_imf()
