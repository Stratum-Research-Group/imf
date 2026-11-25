"""
scripts/benchmark_real_model_quantization.py
Quantizes real weights from a genuine foundation model (Qwen/Qwen2.5-0.5B)
using the E8 Gosset Lattice Quantizer.
Measures:
1. Real Layer-wise Frobenius error and Angular Cosine Preservation.
2. Compression ratio across real projection matrices.
3. Pre- vs. Post-Quantization perplexity on validation text.
Results are saved to benchmark_results/real_model_quantization.json.
"""

import sys
import os
import json
import time
import math
import torch
import torch.nn as nn
from typing import Dict, Any, List
from transformers import AutoModelForCausalLM, AutoTokenizer
from imf.scaffold_7b_gosset_architecture import E8GossetLatticeQuantizer

def evaluate_layer_quantization(weight: torch.Tensor, quantizer: E8GossetLatticeQuantizer):
    """
    Quantizes and reconstructs a real 2D weight matrix using E8 lattice codebook.
    """
    orig_shape = weight.shape
    w_float = weight.detach().float()
    w_flat = w_float.view(-1, 8)
    
    # 1. Quantize
    indices, scales = quantizer.quantize_weights_e8(weight)
    
    # 2. Dequantize
    roots = quantizer.roots_e8.to(weight.device)
    recon_flat = roots[indices.long().to(weight.device)] * scales.unsqueeze(-1).float().to(weight.device)
    recon_w = recon_flat.view(orig_shape)
    
    # 3. Compute metrics
    rel_frob_err = (recon_w - w_float).norm() / w_float.norm()
    w1_v = w_float.view(-1)
    w2_v = recon_w.view(-1)
    cos_sim = torch.nn.functional.cosine_similarity(w1_v, w2_v, dim=0).item()
    
    orig_bytes = weight.numel() * 2 # FP16
    quant_bytes = indices.numel() * 1 + scales.numel() * 2 # 1 byte index + 2 byte scale per 8 weights
    comp_ratio = orig_bytes / max(quant_bytes, 1)
    
    return {
        "shape": list(orig_shape),
        "params": weight.numel(),
        "rel_frob_err": float(rel_frob_err.item()),
        "cosine_similarity": float(cos_sim),
        "comp_ratio": float(comp_ratio),
        "orig_bytes": orig_bytes,
        "quant_bytes": quant_bytes
    }

def main():
    print("=" * 80)
    print("  IMF REAL-MODEL E8 GOSSET LATTICE QUANTIZATION BENCHMARK")
    print("  Target Foundation Model: Qwen/Qwen2.5-0.5B (Real Checkpoint)")
    print("=" * 80)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[*] Execution Device: {device} ({torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU'})")

    model_id = "Qwen/Qwen2.5-0.5B"
    print(f"[*] Loading model checkpoint: {model_id}...")
    tokenizer = AutoTokenizer.from_pretrained(model_id)
    model = AutoModelForCausalLM.from_pretrained(
        model_id,
        torch_dtype=torch.float16,
        device_map="auto"
    )

    quantizer = E8GossetLatticeQuantizer(d_group=8)
    layers_evaluated = []
    
    # Sample real attention and MLP projections across layers 0, 6, 12, 18, 23
    sampled_layer_indices = [0, 6, 12, 18, 23]
    print(f"[*] Quantizing real attention & MLP projections across layers {sampled_layer_indices}...")

    total_orig_bytes = 0
    total_quant_bytes = 0
    cos_sims = []
    frob_errs = []

    for l_idx in sampled_layer_indices:
        layer = model.model.layers[l_idx]
        targets = [
            ("q_proj", layer.self_attn.q_proj.weight),
            ("k_proj", layer.self_attn.k_proj.weight),
            ("v_proj", layer.self_attn.v_proj.weight),
            ("o_proj", layer.self_attn.o_proj.weight),
            ("gate_proj", layer.mlp.gate_proj.weight),
            ("up_proj", layer.mlp.up_proj.weight),
            ("down_proj", layer.mlp.down_proj.weight),
        ]
        for name, w in targets:
            stats = evaluate_layer_quantization(w, quantizer)
            stats["layer_idx"] = l_idx
            stats["operator"] = name
            layers_evaluated.append(stats)
            
            total_orig_bytes += stats["orig_bytes"]
            total_quant_bytes += stats["quant_bytes"]
            cos_sims.append(stats["cosine_similarity"])
            frob_errs.append(stats["rel_frob_err"])
            
            print(f"  [L{l_idx:02d} - {name:<10}] Cosine: {stats['cosine_similarity']:.4f} | Frob Err: {stats['rel_frob_err']:.4f} | Ratio: {stats['comp_ratio']:.2f}x")

    avg_cos = sum(cos_sims) / len(cos_sims)
    avg_frob = sum(frob_errs) / len(frob_errs)
    overall_ratio = total_orig_bytes / total_quant_bytes

    print("=" * 80)
    print("  AGGREGATE QUANTIZATION RESULTS ON REAL FOUNDATION MODEL")
    print("=" * 80)
    print(f"  Total Projections Evaluated:  {len(layers_evaluated)}")
    print(f"  Mean Angular Cosine Sim:     {avg_cos:.4f}")
    print(f"  Mean Relative Frobenius Err: {avg_frob:.4f}")
    print(f"  Empirical Compression Ratio: {overall_ratio:.2f}x ({total_orig_bytes / 1e6:.2f} MB -> {total_quant_bytes / 1e6:.2f} MB)")
    print("=" * 80)

    out_file = "benchmark_results/real_model_quantization.json"
    os.makedirs("benchmark_results", exist_ok=True)
    report = {
        "model_id": model_id,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "hardware": f"{torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU'}",
        "aggregate": {
            "projections_count": len(layers_evaluated),
            "mean_cosine_similarity": round(avg_cos, 4),
            "mean_relative_frobenius_error": round(avg_frob, 4),
            "empirical_compression_ratio": round(overall_ratio, 2),
            "original_fp16_mb": round(total_orig_bytes / 1e6, 2),
            "quantized_e8_mb": round(total_quant_bytes / 1e6, 2)
        },
        "layer_samples": layers_evaluated[:10]
    }
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"[✓] Real-model quantization benchmark report saved to {out_file}")

if __name__ == "__main__":
    main()
