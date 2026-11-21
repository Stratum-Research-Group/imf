"""
weft_to_imf_converter.py
========================
Converter utility to translate WEFT (.weft) sub-bit binary containers
into native Interaction Model Foundations (.imf) binary containers.

Specification alignment:
- Source: WEFT Binary Model Container Format (.weft)
  * Magic: b"WEFTMOD\x01"
  * LittleBit-2 low-rank binary factorizations (Dual-SVID / dual-path bitboards)
  * Packed uint32 bitboards (U_b, V_b) and FP16 scale vectors (h, l, g).
- Target: IMF Binary Model Container (.imf)
  * Magic: 0x494D4601 (b"IMF\x01")
  * 64-byte aligned header with zero-copy mmap index
  * Supports factorized sub-bit encoding (raw bitboards, scales, or materialized linear tensors)

Modes supported:
1. 'factorized' (default): Preserves sub-bit LittleBit-2 parameter representation:
   Stores u_packed, v_packed, scale_h, scale_l, scale_g, and bias directly into .imf
   with ENCODING_RAW_BIT / ENCODING_FLOAT16_SCALES metadata.
2. 'reconstructed': Reconstructs full FP16/BF16 weights:
   W_hat = sum_p [ diag(h_p) @ (U_b,p @ diag(l_p) @ V_b,p^T) @ diag(g_p) ]
   and stores full weight matrices with ENCODING_FLOAT16_SCALES.
"""

import os
import sys
import argparse
from pathlib import Path
from typing import Dict, Any, Optional
import numpy as np
import torch

from imf.imf_container import (
    IMFWriter,
    IMFReader,
    ENCODING_RAW_BIT,
    ENCODING_FLOAT16_SCALES,
    ENCODING_FLOAT32,
    ENCODING_BFLOAT16,
)


def _load_weft_format_module():
    """Dynamically loads weft.format without triggering unrelated dependencies."""
    try:
        from weft.format import WeftModelContainer, WeftSubBitLinear
        return WeftModelContainer, WeftSubBitLinear
    except Exception:
        # Fallback to direct file loading if weft package root imports external deps (e.g. transformers)
        import importlib.util
        possible_paths = [
            Path("/home/akarta/Projects/0.WiP/Weft/weft/format.py"),
            Path("../Weft/weft/format.py"),
            Path(__file__).resolve().parent.parent.parent / "Weft" / "weft" / "format.py",
        ]
        for p in possible_paths:
            if p.exists():
                spec = importlib.util.spec_from_file_location("weft_format_standalone", str(p))
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                return mod.WeftModelContainer, mod.WeftSubBitLinear
        raise ImportError("Could not find or import WEFT format module (format.py)")


def unpack_bitboard_numpy(packed: np.ndarray, rank: int) -> np.ndarray:
    """
    Unpacks (N, words_per_rank) uint32 bitboards into (N, rank) bipolar floats {-1.0, +1.0}.
    Bit 1 -> +1.0, Bit 0 -> -1.0.
    """
    N, num_words = packed.shape
    shifts = np.arange(32, dtype=np.uint32)
    # (N, num_words, 32)
    expanded = (packed[:, :, None] >> shifts[None, None, :]) & 1
    bipolar = (expanded.astype(np.float32) * 2.0 - 1.0).reshape(N, num_words * 32)
    return bipolar[:, :rank]


def reconstruct_weight_matrix(tdata: Dict[str, Any], dtype: torch.dtype = torch.float16) -> torch.Tensor:
    """
    Reconstructs continuous uncompressed weight matrix W from WEFT dual-path factors:
    W_hat = sum_p [ diag(h_p) @ (U_b,p @ diag(l_p) @ V_b,p^T) @ diag(g_p) ]
    Output shape: (out_features, in_features)
    """
    out_features = tdata["out_features"]
    in_features = tdata["in_features"]
    rank = tdata["rank"]
    num_paths = tdata["num_paths"]

    W_total = np.zeros((out_features, in_features), dtype=np.float32)

    for p in range(num_paths):
        p_data = tdata["paths"][p]
        u_packed = p_data["u_packed"].astype(np.uint32)
        v_packed = p_data["v_packed"].astype(np.uint32)
        h = p_data["scale_h"].astype(np.float32)  # (out_features,)
        l = p_data["scale_l"].astype(np.float32)  # (rank,)
        g = p_data["scale_g"].astype(np.float32)  # (in_features,)

        U_b = unpack_bitboard_numpy(u_packed, rank)  # (out_features, rank)
        V_b = unpack_bitboard_numpy(v_packed, rank)  # (in_features, rank)

        # Core product: (U_b * l) @ V_b^T -> (out_features, in_features)
        U_scaled = U_b * l[None, :]
        core = np.matmul(U_scaled, V_b.T)

        # Scale outer: diag(h) @ core @ diag(g)
        W_p = (h[:, None] * core) * g[None, :]
        W_total += W_p

    t = torch.from_numpy(W_total).to(dtype)
    return t


def convert_weft_to_imf(
    weft_path: str,
    imf_path: str,
    mode: str = "factorized",
    target_dtype: torch.dtype = torch.float16,
) -> str:
    """
    Converts a .weft file into an .imf container file.

    Args:
        weft_path: Path to source .weft file.
        imf_path: Path to destination .imf file.
        mode: 'factorized' (keep LittleBit binary bitboards/scales) or
              'reconstructed' (materialize full dense weight matrices).
        target_dtype: Target tensor dtype for reconstructed weights.
    """
    WeftModelContainer, _ = _load_weft_format_module()
    print(f"[*] Reading source WEFT container: {weft_path}...")
    weft_container = WeftModelContainer.load(weft_path)

    # Base configuration enriched with WEFT provenance metadata
    imf_config = dict(weft_container.metadata)
    imf_config["converted_from"] = "WEFT"
    imf_config["conversion_mode"] = mode
    imf_config["source_file"] = os.path.basename(weft_path)

    writer = IMFWriter(imf_path, model_config=imf_config)
    num_tensors_written = 0

    print(f"[*] Converting in '{mode}' mode...")

    for name, tdata in weft_container.tensors.items():
        if mode == "factorized":
            # Store native LittleBit-2 factors directly
            num_paths = tdata["num_paths"]
            for p in range(num_paths):
                p_data = tdata["paths"][p]
                prefix = f"{name}.path{p}"

                u_t = torch.from_numpy(p_data["u_packed"].astype(np.int32))
                v_t = torch.from_numpy(p_data["v_packed"].astype(np.int32))
                h_t = torch.from_numpy(p_data["scale_h"])
                l_t = torch.from_numpy(p_data["scale_l"])
                g_t = torch.from_numpy(p_data["scale_g"])

                writer.add_tensor(f"{prefix}.u_packed", u_t, encoding=ENCODING_RAW_BIT)
                writer.add_tensor(f"{prefix}.v_packed", v_t, encoding=ENCODING_RAW_BIT)
                writer.add_tensor(f"{prefix}.scale_h", h_t, encoding=ENCODING_FLOAT16_SCALES)
                writer.add_tensor(f"{prefix}.scale_l", l_t, encoding=ENCODING_FLOAT16_SCALES)
                writer.add_tensor(f"{prefix}.scale_g", g_t, encoding=ENCODING_FLOAT16_SCALES)
                num_tensors_written += 5

            if tdata["bias"] is not None:
                bias_t = torch.from_numpy(tdata["bias"])
                writer.add_tensor(f"{name}.bias", bias_t, encoding=ENCODING_FLOAT16_SCALES)
                num_tensors_written += 1

        elif mode == "reconstructed":
            # Reconstruct dense weight tensor W: (out_features, in_features)
            w_dense = reconstruct_weight_matrix(tdata, dtype=target_dtype)
            weight_name = f"{name}.weight"
            writer.add_tensor(weight_name, w_dense, encoding=ENCODING_FLOAT16_SCALES)
            num_tensors_written += 1

            if tdata["bias"] is not None:
                bias_t = torch.from_numpy(tdata["bias"]).to(target_dtype)
                writer.add_tensor(f"{name}.bias", bias_t, encoding=ENCODING_FLOAT16_SCALES)
                num_tensors_written += 1

        else:
            raise ValueError(f"Unknown conversion mode: {mode}. Must be 'factorized' or 'reconstructed'.")

    writer.write()
    print(f"[✓] Converted {len(weft_container.tensors)} WEFT operators ({num_tensors_written} tensors) -> {imf_path}")
    return imf_path


def main():
    parser = argparse.ArgumentParser(description="Convert .weft model container to .imf container format.")
    parser.add_argument("input", type=str, help="Input .weft file path")
    parser.add_argument("-o", "--output", type=str, default=None, help="Output .imf file path")
    parser.add_argument(
        "--mode",
        choices=["factorized", "reconstructed"],
        default="factorized",
        help="Conversion mode: 'factorized' (preserves sub-bit bitboards) or 'reconstructed' (dense weights)",
    )
    args = parser.parse_args()

    input_path = args.input
    output_path = args.output
    if output_path is None:
        output_path = str(Path(input_path).with_suffix(".imf"))

    convert_weft_to_imf(input_path, output_path, mode=args.mode)


if __name__ == "__main__":
    main()
