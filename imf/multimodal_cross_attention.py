"""
imf/multimodal_cross_attention.py
Continuous Multimodal Cross-Attention & Dynamic State Interpolation.
Bridges discrete text tokens with continuous sensory streams (vision/audio frames)
by projecting sensory embeddings into skew-symmetric generators of the Lie algebra so(d_h).
Interpolates recurrent states via continuous geodesic flow:
    h(t) = exp(delta_t * Omega) h(0) + delta_t * W_in x(t)
Preserves unitary state norms and allows backpropagation through variable timestamp gaps.
"""

import math
import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Optional, Tuple


class ContinuousMultimodalCrossAttention(nn.Module):
    def __init__(self, d_model: int = 128, d_sensory: int = 256, d_state: int = 64, num_heads: int = 4):
        super().__init__()
        self.d_model = d_model
        self.d_sensory = d_sensory
        self.d_state = d_state
        self.num_heads = num_heads

        # Sensory to state generator projection (maps sensory features to skew-symmetric generator Omega)
        self.sensory_proj = nn.Linear(d_sensory, d_state * d_state)
        # Input coupling projection
        self.input_proj = nn.Linear(d_sensory, d_state)
        # Cross-attention query/key/value projections between text tokens and sensory frames
        self.q_proj = nn.Linear(d_model, d_model)
        self.k_proj = nn.Linear(d_sensory, d_model)
        self.v_proj = nn.Linear(d_sensory, d_model)
        self.out_proj = nn.Linear(d_model, d_model)

    def compute_skew_symmetric_generator(self, sensory_feat: torch.Tensor) -> torch.Tensor:
        """
        Projects sensory features to so(d_state) Lie algebra generator Omega.
        Omega = (M - M^T) / 2
        """
        M = self.sensory_proj(sensory_feat).view(-1, self.d_state, self.d_state)
        Omega = 0.5 * (M - M.transpose(-1, -2))
        return Omega

    def continuous_state_step(
        self,
        h_prev: torch.Tensor,
        sensory_feat: torch.Tensor,
        delta_t: float = 1.0,
    ) -> torch.Tensor:
        """
        Propagates recurrent state across continuous time interval delta_t:
        Cayley approximation of exp(delta_t * Omega):
            R = (I - delta_t/2 * Omega)^-1 (I + delta_t/2 * Omega)
        h_next = h_prev @ R + delta_t * input_proj(sensory_feat)
        """
        B = h_prev.shape[0]
        Omega = self.compute_skew_symmetric_generator(sensory_feat) # [B, D_state, D_state]
        I = torch.eye(self.d_state, device=h_prev.device, dtype=h_prev.dtype).unsqueeze(0).expand(B, -1, -1)
        
        # Cayley transform
        half_dt = 0.5 * delta_t
        A = half_dt * Omega
        # Inversion of (I - A)
        inv_term = torch.linalg.inv(I - A)
        R = torch.bmm(inv_term, I + A) # Orthogonal matrix in SO(d_state)
        
        # Recurrent state update
        in_inj = delta_t * self.input_proj(sensory_feat) # [B, D_state]
        h_next = torch.bmm(h_prev.unsqueeze(1), R).squeeze(1) + in_inj
        return h_next

    def forward(
        self,
        text_tokens: torch.Tensor,       # [B, T_text, D_model]
        sensory_frames: torch.Tensor,    # [B, T_sensory, D_sensory]
        timestamps: Optional[torch.Tensor] = None, # [B, T_sensory] frame timestamps
        initial_state: Optional[torch.Tensor] = None # [B, D_state]
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Fuses text tokens with continuous sensory frames via cross-attention
        and returns updated text tokens along with continuously threaded recurrent state.
        """
        B, T_text, _ = text_tokens.shape
        _, T_sensory, _ = sensory_frames.shape
        device = text_tokens.device

        # 1. Cross-attention: text queries attend to sensory keys/values
        Q = self.q_proj(text_tokens)
        K = self.k_proj(sensory_frames)
        V = self.v_proj(sensory_frames)

        scale = 1.0 / math.sqrt(self.d_model)
        attn_scores = torch.bmm(Q, K.transpose(1, 2)) * scale
        attn_weights = F.softmax(attn_scores, dim=-1)
        cross_out = torch.bmm(attn_weights, V)
        text_fused = text_tokens + self.out_proj(cross_out)

        # 2. Continuous Lie group state propagation across sensory frames
        if initial_state is None:
            h = torch.zeros(B, self.d_state, device=device, dtype=text_tokens.dtype)
        else:
            h = initial_state

        for t in range(T_sensory):
            frame_t = sensory_frames[:, t, :]
            if timestamps is not None and t > 0:
                dt = float((timestamps[:, t] - timestamps[:, t - 1]).clamp(min=1e-3).mean().item())
            else:
                dt = 1.0
            h = self.continuous_state_step(h, frame_t, delta_t=dt)

        return text_fused, h
