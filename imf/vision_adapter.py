"""
imf/vision_adapter.py
IMF Geometric Vision-Language Multimodal Adapter (IMF-VLM).

Architecture:
1. SigLIP / ViT Patch Linear & Conv Tokenizer:
   - Maps 2D spatial patches (e.g. 14x14 or 16x16) into intermediate representation.
2. Stiefel Isometry Projection into SO(n) Continuous Lie Algebra Manifold:
   - Enforces orthogonality W^T W = I so that image token norms do not distort
     the continuous Lie state-space dynamics or trigger representation explosion.
3. 2D Continuous Rotary/Planar Positional Harmonics:
   - Sinusoidal frequency grid matching geometric spatial coordinates.
4. Multimodal Fusion Interleaver:
   - Interleaves image patch tokens with textual prompt embeddings for unified
     polytope routing through the 8-domain MoPE and Lie SSM blocks.
"""

from typing import Dict, List, Optional, Tuple, Union, Any
import math
import torch
import torch.nn as nn
import torch.nn.functional as F


class IMFVLMVisionAdapter(nn.Module):
    """
    Multimodal Vision-Language Projection Adapter grounded in Lie Continuous Isometries.
    """
    def __init__(
        self,
        img_size: int = 224,
        patch_size: int = 14,
        in_channels: int = 3,
        d_model: int = 576,
        vision_hidden_dim: int = 768,
        dropout: float = 0.0,
    ):
        super().__init__()
        assert img_size % patch_size == 0, "img_size must be divisible by patch_size"
        self.img_size = img_size
        self.patch_size = patch_size
        self.num_patches_per_axis = img_size // patch_size
        self.num_patches = self.num_patches_per_axis ** 2
        self.d_model = d_model
        self.vision_hidden_dim = vision_hidden_dim

        # 1. 2D Patch Convolutional Embedding
        self.patch_conv = nn.Conv2d(
            in_channels,
            vision_hidden_dim,
            kernel_size=patch_size,
            stride=patch_size,
            bias=False,
        )

        # 2. 2D Continuous Spatial Coordinates & Harmonics
        self.register_buffer("spatial_harmonics", self._init_2d_harmonics(vision_hidden_dim))

        # 3. Two-layer MLP projection into d_model with GeLU
        self.proj_up = nn.Linear(vision_hidden_dim, d_model * 2, bias=False)
        self.proj_down = nn.Linear(d_model * 2, d_model, bias=False)
        self.norm = nn.LayerNorm(d_model)
        self.dropout = nn.Dropout(dropout)

        # 4. Stiefel Manifold Orthogonal Rectifier: ensure unitary energy preservation
        # Initializes to identity projection block
        stiefel_weight = torch.eye(d_model)
        self.stiefel_matrix = nn.Parameter(stiefel_weight)

    def _init_2d_harmonics(self, dim: int) -> torch.Tensor:
        """Computes 2D sinusoidal positional encodings for grid."""
        half_dim = dim // 2
        freqs = torch.exp(-math.log(10000.0) * torch.arange(0, half_dim, 2).float() / half_dim)
        grid_y, grid_x = torch.meshgrid(
            torch.arange(self.num_patches_per_axis, dtype=torch.float32),
            torch.arange(self.num_patches_per_axis, dtype=torch.float32),
            indexing="ij",
        )
        grid_y = grid_y.flatten().unsqueeze(1) # [num_patches, 1]
        grid_x = grid_x.flatten().unsqueeze(1) # [num_patches, 1]

        sin_y = torch.sin(grid_y * freqs)
        cos_y = torch.cos(grid_y * freqs)
        sin_x = torch.sin(grid_x * freqs)
        cos_x = torch.cos(grid_x * freqs)

        harmonics = torch.cat([sin_y, cos_y, sin_x, cos_x], dim=-1)
        if harmonics.shape[-1] < dim:
            pad = torch.zeros(self.num_patches, dim - harmonics.shape[-1])
            harmonics = torch.cat([harmonics, pad], dim=-1)
        return harmonics.unsqueeze(0) # [1, num_patches, dim]

    def encode_patches(self, images: torch.Tensor) -> torch.Tensor:
        """
        Args:
            images: [Batch, C, H, W]
        Returns:
            vision_tokens: [Batch, num_patches, d_model]
        """
        B = images.shape[0]
        # [B, vision_hidden_dim, H/P, W/P] -> [B, N, vision_hidden_dim]
        patches = self.patch_conv(images).flatten(2).transpose(1, 2)
        patches = patches + self.spatial_harmonics

        # MLP Projection
        h = F.gelu(self.proj_up(patches))
        tokens = self.proj_down(h)
        tokens = self.norm(tokens)

        # Stiefel Orthogonal Projection to guarantee isometric energy conservation:
        # Q via Gram-Schmidt / polar decomposition during inference
        u, _, v = torch.svd(self.stiefel_matrix)
        q_stiefel = torch.matmul(u, v.t()) # Unitary matrix in SO(d_model)

        tokens = torch.matmul(tokens, q_stiefel)
        return self.dropout(tokens)

    def fuse_multimodal(
        self,
        text_tokens: torch.Tensor,     # [Batch, SeqLen_text, d_model]
        images: Optional[torch.Tensor] = None, # [Batch, C, H, W]
        prefix_vision: bool = True,
    ) -> Tuple[torch.Tensor, Dict[str, Any]]:
        """
        Interleaves or prefixes vision tokens into text sequence.
        """
        if images is None:
            return text_tokens, {"has_vision": False, "num_vision_tokens": 0}

        vision_tokens = self.encode_patches(images)
        num_v = vision_tokens.shape[1]

        if prefix_vision:
            fused = torch.cat([vision_tokens, text_tokens], dim=1)
        else:
            fused = torch.cat([text_tokens, vision_tokens], dim=1)

        metrics = {
            "has_vision": True,
            "num_vision_tokens": num_v,
            "vision_token_norm": vision_tokens.norm(dim=-1).mean().item(),
            "fused_sequence_length": fused.shape[1],
        }
        return fused, metrics
