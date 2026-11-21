"""
imf_to_weft_converter.py
========================
Inverse converter: Transforms native Interaction Model Foundations (.imf) binary containers
into WEFT (.weft) sub-bit binary containers.

Supported Modes:
1. 'factorized': If the .imf container already stores LittleBit-2 factors (.path0.u_packed, etc.),
   these bitboards and scales are losslessly transferred directly into the WEFT container.
2. 'svd_binarize': If the .imf container contains continuous dense linear weights (.weight),
   performs LittleBit-2 Dual-Path SVD binarization:
   - Rank-r truncated SVD: W approx U @ diag(S) @ V^T
   - Bipolar bitboard quantization: U_b = sign(U), V_b = sign(V)
   - Channel scales: h = sqrt(mean(U^2)), g = sqrt(mean(V^2)), l = S
   - Stores packed uint32 bitboards into the .weft container.
"""

import os
import sys
import argparse
from pathlib import Path
from typing import Dict, Any, List, Optional
import numpy as np
import torch

from imf.imf_container import IMFReader
from imf.weft_to_imf_converter import _load_weft_format_module


def pack_bitboard_numpy(bipolar: np.ndarray) -> np.ndarray:
    """
    Packs (N, rank) bipolar array {-1.0, +1.0} into (N, ceil(rank/32)) uint32 words.
    bipolar >= 0 -> bit 1, bipolar < 0 -> bit 0.
    """
    N, rank = bipolar.shape
    words_per_rank = (rank + 31) // 32
    packed = np.zeros((N, words_per_rank), dtype=np.uint32)

    bits = (bipolar >= 0).astype(np.uint32)
    for bit_idx in range(rank):
        word_idx = bit_idx // 32
        shift = bit_idx % 32
        packed[:, word_idx] |= (bits[:, bit_idx] << shift)

    return packed


def binarize_weight_matrix_to_paths(
    W: np.ndarray,
    rank: int = 32,
    num_paths: int = 2,
) -> List[Dict[str, np.ndarray]]:
    """
    Performs LittleBit-2 Dual-Path low-rank binarization on dense matrix W (out_features, in_features).
    Returns list of dicts with keys: u_packed, v_packed, scale_h, scale_l, scale_g.
    """
    out_features, in_features = W.shape
    residual = W.astype(np.float32).copy()
    paths = []

    for _ in range(num_paths):
        # Truncated SVD via randomized SVD / standard numpy SVD
        # out_features x in_features
        k = min(rank, min(out_features, in_features))
        U, S, Vt = np.linalg.svd(residual, full_matrices=False)
        U_k = U[:, :k]
        S_k = S[:k]
        V_k = Vt[:k, :].T  # in_features x k

        # If k < rank, pad with zeros
        if k < rank:
            pad_u = np.zeros((out_features, rank - k), dtype=np.float32)
            pad_v = np.zeros((in_features, rank - k), dtype=np.float32)
            pad_s = np.zeros(rank - k, dtype=np.float32)
            U_k = np.hstack([U_k, pad_u])
            V_k = np.hstack([V_k, pad_v])
            S_k = np.concatenate([S_k, pad_s])

        # Bipolar sign quantization: +1 or -1
        U_b = np.where(U_k >= 0, 1.0, -1.0).astype(np.float32)
        V_b = np.where(V_k >= 0, 1.0, -1.0).astype(np.float32)

        # Scale vectors
        scale_h = np.linalg.norm(U_k, axis=1) / np.sqrt(rank)
        scale_h = np.maximum(scale_h, 1e-6).astype(np.float16)

        scale_g = np.linalg.norm(V_k, axis=1) / np.sqrt(rank)
        scale_g = np.maximum(scale_g, 1e-6).astype(np.float16)

        scale_l = (S_k / np.sqrt(out_features * in_features)).astype(np.float16)

        u_packed = pack_bitboard_numpy(U_b)
        v_packed = pack_bitboard_numpy(V_b)

        paths.append({
            "u_packed": u_packed,
            "v_packed": v_packed,
            "scale_h": scale_h,
            "scale_l": scale_l,
            "scale_g": scale_g,
        })

        # Subtract reconstructed approximation from residual
        U_scaled = U_b * scale_l.astype(np.float32)[None, :]
        core = np.matmul(U_scaled, V_b.T)
        W_approx = (scale_h.astype(np.float32)[:, None] * core) * scale_g.astype(np.float32)[None, :]
        residual -= W_approx

    return paths


def convert_imf_to_weft(
    imf_path: str,
    weft_path: str,
    rank: int = 32,
    num_paths: int = 2,
) -> str:
    """
    Converts an .imf container file to a .weft binary container.
    """
    WeftModelContainer, WeftSubBitLinear = _load_weft_format_module()
    print(f"[*] Reading source IMF container: {imf_path}...")
    reader = IMFReader(imf_path)
    config = reader.get_config()
    tensor_names = reader.list_tensors()

    weft_container = WeftModelContainer(metadata=config)

    # 1. Detect if factorized LittleBit tensors exist (.path0.u_packed)
    has_factorized = any(".path0.u_packed" in t for t in tensor_names)

    if has_factorized:
        print("[*] Detected factorized LittleBit-2 tensors inside IMF container. Direct transfer...")
        # Group by layer prefix
        prefixes = set()
        for t in tensor_names:
            if ".path0." in t:
                prefixes.add(t.split(".path0.")[0])

        for prefix in prefixes:
            # Discover num_paths
            p_idx = 0
            paths_data = []
            while f"{prefix}.path{p_idx}.u_packed" in tensor_names:
                u = reader.read_tensor(f"{prefix}.path{p_idx}.u_packed").cpu().numpy().astype(np.uint32)
                v = reader.read_tensor(f"{prefix}.path{p_idx}.v_packed").cpu().numpy().astype(np.uint32)
                h = reader.read_tensor(f"{prefix}.path{p_idx}.scale_h").cpu().numpy().astype(np.float16)
                l = reader.read_tensor(f"{prefix}.path{p_idx}.scale_l").cpu().numpy().astype(np.float16)
                g = reader.read_tensor(f"{prefix}.path{p_idx}.scale_g").cpu().numpy().astype(np.float16)
                paths_data.append({
                    "u_packed": u,
                    "v_packed": v,
                    "scale_h": h,
                    "scale_l": l,
                    "scale_g": g,
                })
                p_idx += 1

            bias_data = None
            if f"{prefix}.bias" in tensor_names:
                bias_data = reader.read_tensor(f"{prefix}.bias").cpu().numpy().astype(np.float16)

            out_features = len(paths_data[0]["scale_h"])
            in_features = len(paths_data[0]["scale_g"])
            r = len(paths_data[0]["scale_l"])

            weft_container.tensors[prefix] = {
                "in_features": in_features,
                "out_features": out_features,
                "rank": r,
                "num_paths": len(paths_data),
                "paths": paths_data,
                "bias": bias_data,
            }
    else:
        print("[*] Detected dense weight tensors. Performing LittleBit-2 Dual-Path SVD binarization...")
        linear_weights = [t for t in tensor_names if t.endswith(".weight") and reader.read_tensor(t).ndim == 2]
        for w_name in linear_weights:
            prefix = w_name[:-7]
            W_tensor = reader.read_tensor(w_name).cpu().float().numpy()
            out_features, in_features = W_tensor.shape

            paths_data = binarize_weight_matrix_to_paths(W_tensor, rank=rank, num_paths=num_paths)

            bias_data = None
            if f"{prefix}.bias" in tensor_names:
                bias_data = reader.read_tensor(f"{prefix}.bias").cpu().numpy().astype(np.float16)

            weft_container.tensors[prefix] = {
                "in_features": in_features,
                "out_features": out_features,
                "rank": rank,
                "num_paths": num_paths,
                "paths": paths_data,
                "bias": bias_data,
            }

    reader.close()
    weft_container.save(weft_path)
    print(f"[✓] Converted IMF container -> WEFT container: {weft_path} ({len(weft_container.tensors)} operators)")
    return weft_path


def main():
    parser = argparse.ArgumentParser(description="Convert .imf container format to .weft format.")
    parser.add_argument("input", type=str, help="Input .imf file path")
    parser.add_argument("-o", "--output", type=str, default=None, help="Output .weft file path")
    parser.add_argument("--rank", type=int, default=32, help="Binarization rank (for dense weights)")
    parser.add_argument("--paths", type=int, default=2, help="Number of dual paths (for dense weights)")
    args = parser.parse_args()

    out_path = args.output or str(Path(args.input).with_suffix(".weft"))
    convert_imf_to_weft(args.input, out_path, rank=args.rank, num_paths=args.paths)


if __name__ == "__main__":
    main()
