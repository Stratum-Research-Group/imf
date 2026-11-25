"""
IMF 14B MoPE Local Architecture Scaffold & Memory Footprint Analyzer
====================================================================
Evaluates parameter allocation, memory budget, and execution footprint for
a 14B Mixture of Poincaré Experts (MoPE) architecture utilizing:
  1. Gosset E_8 Sub-Bit Dequantization (1.5 bits/weight effective)
  2. Associative Multi-Head Latent Attention (MLA) with 8.0x KV compression
  3. Symplectic Top-2 Poincaré Gating
"""

import math

def calculate_14b_mope_budget():
    print("=" * 75)
    print("  IMF 14B MoPE (MIXTURE OF POINCARÉ EXPERTS) ARCHITECTURE SPECIFICATION")
    print("=" * 75)

    vocab_size = 32000
    d_model = 4096
    n_layers = 32
    n_heads = 32
    d_head = 128
    d_latent_kv = 512    # MLA Latent dimension (8x compression over 4096)
    n_experts = 16       # 16 Poincaré Experts per layer
    top_k = 2            # Top-2 routing per token
    d_ffn_expert = 2816  # Expert intermediate dimension

    # 1. Attention Weights per Layer (MLA)
    # W_q: d_model * d_model
    # W_DKV: d_model * d_latent_kv (down-projection for K, V)
    # W_UK: d_latent_kv * (n_heads * d_head) (uncompress key)
    # W_UV: d_latent_kv * (n_heads * d_head) (uncompress value)
    # W_out: (n_heads * d_head) * d_model
    params_q = d_model * d_model
    params_dkv = d_model * d_latent_kv
    params_uk = d_latent_kv * (n_heads * d_head)
    params_uv = d_latent_kv * (n_heads * d_head)
    params_out = (n_heads * d_head) * d_model
    params_attn_layer = params_q + params_dkv + params_uk + params_uv + params_out

    # 2. MoE Weights per Layer (16 Experts + Router)
    # Router: d_model * n_experts
    # Per expert: Gate, Up, Down: 3 * d_model * d_ffn_expert
    params_router = d_model * n_experts
    params_single_expert = 3 * d_model * d_ffn_expert
    params_moe_layer = params_router + n_experts * params_single_expert

    # 3. Layer Norms & Embeddings
    params_norms = 2 * d_model
    params_layer = params_attn_layer + params_moe_layer + params_norms

    total_layer_params = n_layers * params_layer
    embedding_params = vocab_size * d_model
    output_head_params = vocab_size * d_model
    total_model_params = total_layer_params + embedding_params + output_head_params

    # Active Parameters per Forward Token (Top-2 Experts active)
    active_expert_params = top_k * params_single_expert
    active_layer_params = params_attn_layer + params_router + active_expert_params + params_norms
    active_total_params = n_layers * active_layer_params + embedding_params + output_head_params

    print(f"Total Model Parameters:    {total_model_params / 1e9:.2f} Billion ({total_model_params:,})")
    print(f"Active Parameters/Token:   {active_total_params / 1e9:.2f} Billion ({active_total_params:,})")
    print(f"Active Parameter Ratio:    {(active_total_params / total_model_params) * 100:.2f}%")
    print("-" * 75)

    # Memory Budgets across Precision Modes
    fp16_bytes = total_model_params * 2
    int8_bytes = total_model_params * 1
    int4_bytes = total_model_params * 0.5
    # Gosset E8 lattice quantization: 1.5 bits/weight (1.0 bit index + 0.5 bit codebook/scale)
    gosset_e8_bytes = total_model_params * (1.5 / 8.0)

    print("WEIGHT VRAM FOOTPRINT:")
    print(f"  FP16 Precision:          {fp16_bytes / (1024**3):.2f} GB")
    print(f"  INT8 Precision:          {int8_bytes / (1024**3):.2f} GB")
    print(f"  INT4 Precision:          {int4_bytes / (1024**3):.2f} GB")
    print(f"  Gosset E8 (1.5 bits):    {gosset_e8_bytes / (1024**3):.2f} GB")
    print("-" * 75)

    # KV Cache Comparison for Context Length 8,192
    seq_len = 8192
    # Standard MHA: 2 * n_layers * n_heads * d_head * seq_len * 2 bytes
    standard_mha_kv_bytes = 2 * n_layers * (n_heads * d_head) * seq_len * 2
    # Latent MLA: 2 * n_layers * d_latent_kv * seq_len * 2 bytes (or single latent vector)
    mla_latent_kv_bytes = n_layers * d_latent_kv * seq_len * 2

    print(f"KV CACHE FOOTPRINT (Context = {seq_len:,} Tokens, FP16):")
    print(f"  Standard MHA (4096-dim): {standard_mha_kv_bytes / (1024**2):.2f} MB ({standard_mha_kv_bytes / (1024**3):.2f} GB)")
    print(f"  Associative MLA (512-dim):{mla_latent_kv_bytes / (1024**2):.2f} MB ({mla_latent_kv_bytes / (1024**3):.2f} GB)")
    print(f"  KV Compression Factor:   {standard_mha_kv_bytes / mla_latent_kv_bytes:.1f}x")
    print("-" * 75)

    # Workstation Hardware Feasibility on RTX 5060 Ti (16GB VRAM)
    total_local_vram_usage = gosset_e8_bytes + mla_latent_kv_bytes + (512 * 1024 * 1024) # +512MB activation workspace
    print(f"RTX 5060 Ti (16GB VRAM) Total Footprint:")
    print(f"  Model Weights (E8):      {gosset_e8_bytes / (1024**3):.2f} GB")
    print(f"  KV Cache (8k MLA):       {mla_latent_kv_bytes / (1024**3):.2f} GB")
    print(f"  Activation Workspace:    0.50 GB")
    print(f"  TOTAL VRAM COMMITTED:    {total_local_vram_usage / (1024**3):.2f} GB / 16.00 GB")
    print(f"  HEADROOM REMAINING:      {(16 * (1024**3) - total_local_vram_usage) / (1024**3):.2f} GB")
    print("=" * 75)

if __name__ == "__main__":
    calculate_14b_mope_budget()
