"""
imf/model_70b_factorized.py
Reference Implementation of the 70-Billion Parameter IMF Factorized Model (IMF70BModel).
Supports both:
1. Native E8 Polytope Lattice Quantization (PolytopeLatticeLinear): 8D Gosset 240-root discrete lattice.
2. Dual-Path Factorization (DualPathFactorizedLinear): Low-rank sub-byte coordinates.
"""

import math
import torch
import torch.nn as nn
from typing import Optional, Tuple, Dict, Any
from imf.fused_dual_path_gemm import DualPathFactorizedLinear
from imf.polytope_lattice_quantizer import PolytopeLatticeLinear


class IMF70BDecoderLayer(nn.Module):
    """A single factorized decoder layer of the 70B architecture."""
    def __init__(
        self,
        d_model: int = 8192,
        d_mlp: int = 28672,
        rank: int = 128,
        use_polytope_lattice: bool = False,
        dtype=torch.bfloat16,
    ):
        super().__init__()
        self.d_model = d_model
        self.use_polytope_lattice = use_polytope_lattice
        
        if use_polytope_lattice:
            # Native E8 Polytope Lattice Quantization (Paper 40)
            self.q_proj = PolytopeLatticeLinear(d_model, d_model, scale_block_size=64)
            self.k_proj = PolytopeLatticeLinear(d_model, d_model // 8, scale_block_size=64)
            self.v_proj = PolytopeLatticeLinear(d_model, d_model // 8, scale_block_size=64)
            self.o_proj = PolytopeLatticeLinear(d_model, d_model, scale_block_size=64)

            self.gate_proj = PolytopeLatticeLinear(d_model, d_mlp, scale_block_size=64)
            self.up_proj = PolytopeLatticeLinear(d_model, d_mlp, scale_block_size=64)
            self.down_proj = PolytopeLatticeLinear(d_mlp, d_model, scale_block_size=64)
        else:
            # Dual-Path Factorized Linear
            self.q_proj = DualPathFactorizedLinear(d_model, d_model, rank=rank, dtype=dtype)
            self.k_proj = DualPathFactorizedLinear(d_model, d_model // 8, rank=rank, dtype=dtype) # GQA 8:1
            self.v_proj = DualPathFactorizedLinear(d_model, d_model // 8, rank=rank, dtype=dtype)
            self.o_proj = DualPathFactorizedLinear(d_model, d_model, rank=rank, dtype=dtype)
            
            # SwiGLU MLP projections
            self.gate_proj = DualPathFactorizedLinear(d_model, d_mlp, rank=rank, dtype=dtype)
            self.up_proj = DualPathFactorizedLinear(d_model, d_mlp, rank=rank, dtype=dtype)
            self.down_proj = DualPathFactorizedLinear(d_mlp, d_model, rank=rank, dtype=dtype)
        
        # RMSNorm equivalents
        self.input_layernorm = nn.LayerNorm(d_model, dtype=dtype)
        self.post_attention_layernorm = nn.LayerNorm(d_model, dtype=dtype)
        self.num_heads = 64
        self.num_kv_heads = 8
        self.head_dim = d_model // self.num_heads

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # 1. Attention Block with Causal GQA (Grouped Query Attention 8:1)
        B, T, C = x.shape
        norm_x = self.input_layernorm(x)
        q = self.q_proj(norm_x)
        k = self.k_proj(norm_x)
        v = self.v_proj(norm_x)

        q = q.view(B, T, self.num_heads, self.head_dim).transpose(1, 2)
        k = k.view(B, T, self.num_kv_heads, self.head_dim).transpose(1, 2)
        v = v.view(B, T, self.num_kv_heads, self.head_dim).transpose(1, 2)

        # Expand KV heads to match query heads for GQA
        k = k.repeat_interleave(self.num_heads // self.num_kv_heads, dim=1)
        v = v.repeat_interleave(self.num_heads // self.num_kv_heads, dim=1)

        attn_val = torch.nn.functional.scaled_dot_product_attention(
            q, k, v, is_causal=(T > 1)
        )
        attn_val = attn_val.transpose(1, 2).contiguous().view(B, T, C)
        attn_out = self.o_proj(attn_val)
        x = x + attn_out

        # 2. MLP Block (SwiGLU: SiLU(gate) * up)
        norm_x2 = self.post_attention_layernorm(x)
        gate = torch.nn.functional.silu(self.gate_proj(norm_x2))
        up = self.up_proj(norm_x2)
        mlp_out = self.down_proj(gate * up)
        x = x + mlp_out
        return x


class IMF70BModel(nn.Module):
    """
    70.55-Billion Parameter Full-Scale Architecture under Native Polytope / Factorization.
    In uncompressed FP16: 70.55B params (~131.4 GB).
    In Native E8 PLQ: ~10.94 GB total container footprint (< 14 GB runtime VRAM).
    """
    def __init__(
        self,
        num_layers: int = 80,
        d_model: int = 8192,
        d_mlp: int = 28672,
        rank: int = 128,
        vocab_size: int = 128256,
        use_polytope_lattice: bool = True,
        dtype=torch.bfloat16,
    ):
        super().__init__()
        self.num_layers = num_layers
        self.d_model = d_model
        self.vocab_size = vocab_size

        self.tok_embeddings = nn.Embedding(vocab_size, d_model, dtype=dtype)
        # Allocate layers
        self.layers = nn.ModuleList([
            IMF70BDecoderLayer(
                d_model=d_model,
                d_mlp=d_mlp,
                rank=rank,
                use_polytope_lattice=use_polytope_lattice,
                dtype=dtype,
            )
            for _ in range(num_layers)
        ])
        self.norm = nn.LayerNorm(d_model, dtype=dtype)
        self.output = nn.Linear(d_model, vocab_size, bias=False, dtype=dtype)

    def forward(self, input_ids: torch.Tensor) -> torch.Tensor:
        h = self.tok_embeddings(input_ids)
        for layer in self.layers:
            h = layer(h)
        h = self.norm(h)
        logits = self.output(h)
        return logits
