"""
hyperbolic_polytope_tiling.py
Non-Euclidean Hyperbolic Polytope Tiling (H^d) in the Poincaré Ball Model for IMF.

Mathematical Formulation:
In hyperbolic space H^d represented by the Poincaré ball model B^d = {x in R^d : ||x|| < 1}:
1. Conformal Metric:
   ds^2 = 4 dx^2 / (1 - ||x||^2)^2
2. Hyperbolic Geodesic Distance:
   d_H(u, v) = arcosh(1 + 2 * ||u - v||^2 / ((1 - ||u||^2) * (1 - ||v||^2)))
3. Möbius Gyro-Vector Addition:
   u (+) v = ((1 + 2 <u, v> + ||v||^2) u + (1 - ||u||^2) v) / (1 + 2 <u, v> + ||u||^2 ||v||^2)
4. Hyperbolic Polytope Barycentric Coordinates:
   For landmark ideal/hyperideal vertices {v_1, ..., v_K} on H^d:
   w_i(x) = softmax(-d_H(x, v_i) / tau)
Enables exponential tree-like representation capacity for hierarchical taxomonies and formal proof trees.
"""

import math
import torch
import torch.nn as nn
import torch.nn.functional as F


def poincare_project(x: torch.Tensor, max_norm: float = 0.99) -> torch.Tensor:
    """Projects Euclidean embeddings into the open Poincaré ball ||x|| < 1."""
    norm = torch.norm(x, dim=-1, keepdim=True) + 1e-7
    scale = torch.clamp(max_norm / norm, max=1.0)
    return x * scale


def hyperbolic_distance(u: torch.Tensor, v: torch.Tensor, eps: float = 1e-6) -> torch.Tensor:
    """
    Computes pairwise Poincaré geodesic distance d_H(u, v).
    Args:
        u: [..., D]
        v: [..., D]
    Returns:
        d_H: [...]
    """
    u_norm_sq = torch.sum(u ** 2, dim=-1).clamp(max=1.0 - eps)
    v_norm_sq = torch.sum(v ** 2, dim=-1).clamp(max=1.0 - eps)
    diff_norm_sq = torch.sum((u - v) ** 2, dim=-1)

    arg = 1.0 + 2.0 * diff_norm_sq / ((1.0 - u_norm_sq) * (1.0 - v_norm_sq))
    return torch.acosh(arg.clamp(min=1.0 + eps))


class HyperbolicPolytopeTiling(nn.Module):
    """
    Hyperbolic Polytope Landmark Connector in Poincaré space H^d.
    Maps embeddings to hierarchical tree-depth coordinate frames.
    """
    def __init__(self, d_model: int = 256, num_vertices: int = 12, temperature: float = 1.0):
        super().__init__()
        self.d_model = d_model
        self.num_vertices = num_vertices
        self.temperature = temperature

        # Initialize landmark vertices near the hyperbolic boundary (radius 0.85)
        raw_corners = torch.randn(num_vertices, d_model)
        unit_corners = F.normalize(raw_corners, dim=-1) * 0.85
        self.vertices = nn.Parameter(unit_corners)

        self.in_proj = nn.Linear(d_model, d_model, bias=False)
        self.out_proj = nn.Linear(d_model, d_model, bias=False)

    def get_coordinates(self, x: torch.Tensor) -> torch.Tensor:
        """
        Computes hyperbolic barycentric coordinates:
        w_i(x) = softmax(-d_H(x_proj, v_i) / tau)
        Args:
            x: [Batch, SeqLen, d_model]
        Returns:
            coords: [Batch, SeqLen, num_vertices]
        """
        B, T, D = x.shape
        x_proj = poincare_project(self.in_proj(x)) # [B, T, D]
        v_proj = poincare_project(self.vertices)   # [K, D]

        # Pairwise distance: [B, T, 1, D] vs [1, 1, K, D]
        x_exp = x_proj.unsqueeze(2)
        v_exp = v_proj.unsqueeze(0).unsqueeze(0)
        dist_h = hyperbolic_distance(x_exp, v_exp) # [B, T, K]

        return F.softmax(-dist_h / self.temperature, dim=-1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Maps input embeddings through the hyperbolic polytope tiling frame.
        """
        coords = self.get_coordinates(x) # [B, T, K]
        v_proj = poincare_project(self.vertices) # [K, D]
        # Hyperbolic Frechet mean / barycentric weighted combination
        reconstructed = torch.matmul(coords, v_proj) # [B, T, D]
        return self.out_proj(reconstructed)
