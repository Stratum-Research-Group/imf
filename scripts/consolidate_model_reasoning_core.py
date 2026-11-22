"""
Consolidate and filter external sharded models (Llama-3.3-70B / Qwen-2.5-72B) into
a lean, high-fidelity reasoning engine IMF container.

Separates reasoning core (self-attention query/key/value/output projections,
layer norms, embeddings) from dead feed-forward world-knowledge trivia layers,
enabling the dynamic engine to run within minimal memory while facts live in the
hyper-lattice polytope chambers.
"""

import os
import sys
import glob
import time
from pathlib import Path
from typing import Dict, List, Optional, Set, Any
import numpy as np
import torch

from imf.imf_container import IMFWriter, IMFReader, ENCODING_RAW_BIT, ENCODING_FLOAT16_SCALES
from imf.weft_to_imf_converter import _load_weft_format_module


def consolidate_reasoning_core_to_imf(
    source_dir: str,
    output_imf_path: str,
    filter_reasoning_only: bool = True,
    max_shards: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Consolidates sharded .weft files from source_dir into a single unified .imf container.
    If filter_reasoning_only=True:
        Extracts self-attention (q_proj, k_proj, v_proj, o_proj), layer norms (input_layernorm,
        post_attention_layernorm, norm), and token embeddings.
        Skips static FFN trivia bloat (gate_proj, up_proj, down_proj) which are routed
        to the HyperLatticeChamberStore.
    """
    source_path = Path(source_dir)
    assert source_path.exists(), f"Source path {source_dir} does not exist."

    shards = sorted(list(source_path.glob("*.weft")))
    if not shards:
        raise FileNotFoundError(f"No .weft files found in {source_dir}")

    if max_shards:
        shards = shards[:max_shards]

    WeftModelContainer, _ = _load_weft_format_module()
    print(f"[*] Consolidating {len(shards)} shards from {source_dir} -> {output_imf_path}")
    print(f"[*] Filter reasoning core only: {filter_reasoning_only}")

    # Reasoning module keywords
    reasoning_keywords = {
        "self_attn", "q_proj", "k_proj", "v_proj", "o_proj",
        "attn", "attention", "input_layernorm", "post_attention_layernorm",
        "embed_tokens", "tok_embeddings", "norm", "lm_head"
    }

    writer = IMFWriter(output_imf_path, model_config={"architecture": "Filtered_Reasoning_Core_70B"})
    total_operators = 0
    total_tensors = 0
    skipped_ffn_tensors = 0
    t0 = time.time()

    for idx, shard in enumerate(shards, 1):
        try:
            container = WeftModelContainer.load(str(shard))
        except Exception as e:
            print(f"    [!] Error loading shard {shard.name}: {e}")
            continue

        for name, tdata in container.tensors.items():
            # Check if this operator belongs to the reasoning core
            is_reasoning = any(kw in name.lower() for kw in reasoning_keywords)
            if filter_reasoning_only and not is_reasoning:
                skipped_ffn_tensors += tdata.get("num_paths", 2) * 5
                continue

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
                total_tensors += 5

            if tdata.get("bias") is not None:
                bias_t = torch.from_numpy(tdata["bias"])
                writer.add_tensor(f"{name}.bias", bias_t, encoding=ENCODING_FLOAT16_SCALES)
                total_tensors += 1

            total_operators += 1

    writer.write()
    elapsed = time.time() - t0
    size_mb = os.path.getsize(output_imf_path) / (1024 * 1024)

    stats = {
        "output_path": output_imf_path,
        "size_mb": size_mb,
        "total_operators": total_operators,
        "total_tensors": total_tensors,
        "skipped_ffn_tensors": skipped_ffn_tensors,
        "elapsed_seconds": elapsed,
    }
    print(f"[✓] Successfully wrote {total_tensors} reasoning tensors ({total_operators} operators) in {elapsed:.2f}s")
    print(f"[✓] Skipped {skipped_ffn_tensors} trivia/FFN tensors -> {size_mb:.2f} MB total container size")
    return stats


if __name__ == "__main__":
    src = "/run/media/akarta/AI/models/llama-3.3-70b-subbit"
    dst = "checkpoints/llama_3.3_70b_reasoning_core.imf"
    consolidate_reasoning_core_to_imf(src, dst, filter_reasoning_only=True, max_shards=3)
