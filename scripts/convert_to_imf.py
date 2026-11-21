#!/usr/bin/env python3
"""
CLI utility to convert PyTorch (.pt) checkpoints to the IMF (.imf) binary container format.
Supports zero-copy mmap loading, tensor CRC32 verification, and sub-byte metadata.
"""

import sys
import os
import argparse
import time
import torch
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

from imf.imf_container import IMFWriter, IMFReader

def convert_checkpoint(input_path: str, output_path: str = None, verify: bool = True):
    input_file = Path(input_path)
    if not input_file.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")
        
    if output_path is None:
        output_file = input_file.with_suffix(".imf")
    else:
        output_file = Path(output_path)
        
    print(f"[*] Loading PyTorch checkpoint: {input_file} ({input_file.stat().st_size / (1024*1024):.2f} MB)...")
    t0 = time.time()
    checkpoint = torch.load(input_file, map_location="cpu", weights_only=False)
    load_time = time.time() - t0
    print(f"[+] Loaded in {load_time:.2f}s")
    
    # Extract state dict and metadata
    state_dict = {}
    metadata = {
        "source_checkpoint": str(input_file.name),
        "source_size_bytes": input_file.stat().st_size,
        "converted_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    
    if isinstance(checkpoint, dict):
        if "model_state_dict" in checkpoint:
            state_dict = checkpoint["model_state_dict"]
            # Copy other non-tensor fields to metadata
            for k, v in checkpoint.items():
                if k != "model_state_dict" and isinstance(v, (int, float, str, bool, list, dict)):
                    metadata[k] = v
        elif "state_dict" in checkpoint:
            state_dict = checkpoint["state_dict"]
            for k, v in checkpoint.items():
                if k != "state_dict" and isinstance(v, (int, float, str, bool, list, dict)):
                    metadata[k] = v
        else:
            # Assume dict of tensors
            state_dict = {k: v for k, v in checkpoint.items() if isinstance(v, torch.Tensor)}
            for k, v in checkpoint.items():
                if not isinstance(v, torch.Tensor) and isinstance(v, (int, float, str, bool, list, dict)):
                    metadata[k] = v
    else:
        raise ValueError(f"Unsupported checkpoint format in {input_file}")
        
    print(f"[*] Serializing {len(state_dict)} tensors to IMF container: {output_file}...")
    t1 = time.time()
    writer = IMFWriter(str(output_file), metadata=metadata)
    for name, tensor in state_dict.items():
        writer.add_tensor(name, tensor)
    writer.write()
    write_time = time.time() - t1
    
    out_size = output_file.stat().st_size
    print(f"[+] Successfully generated IMF container in {write_time:.2f}s!")
    print(f"    IMF File Size: {out_size / (1024*1024):.2f} MB ({out_size} bytes)")
    
    if verify:
        print("[*] Verifying container integrity via zero-copy IMFReader...")
        t2 = time.time()
        reader = IMFReader(str(output_file))
        tensor_names = reader.list_tensors()
        assert len(tensor_names) == len(state_dict), "Tensor count mismatch!"
        for name, original_tensor in state_dict.items():
            loaded_tensor = reader.read_tensor(name)
            assert loaded_tensor.shape == original_tensor.shape, f"Shape mismatch in {name}"
            # Test equality or close tolerance
            if original_tensor.dtype in (torch.float32, torch.float64, torch.int64, torch.int32, torch.int8, torch.uint8):
                diff = (loaded_tensor - original_tensor).abs().max().item()
                assert diff == 0, f"Value mismatch in {name}: max diff {diff}"
        reader.close()
        verify_time = time.time() - t2
        print(f"[+] Verification passed! Verified {len(state_dict)} tensors in {verify_time:.4f}s.")

def main():
    parser = argparse.ArgumentParser(description="Convert PyTorch checkpoint to IMF (.imf) model container.")
    parser.add_argument("input", help="Path to input PyTorch checkpoint (.pt)")
    parser.add_argument("-o", "--output", help="Path to output .imf file (defaults to same name with .imf extension)")
    parser.add_argument("--no-verify", action="store_true", help="Skip post-conversion tensor verification")
    args = parser.parse_args()
    
    convert_checkpoint(args.input, args.output, verify=not args.no_verify)

if __name__ == "__main__":
    main()
