"""
gauge_polytope_complex.py
Non-Abelian SU(2) Gauge-Equivariant Simplicial Complex for IMF (Interaction Model Foundations).

Mathematical Formulation:
1. Vertices (0-simplices): Regular polytope landmark vertices v_i in R^d (e.g. 10D Decayotton K=11).
2. Edges (1-simplices): Directed edges e_ij carry non-abelian gauge connections U_ij in SU(2),
   modeled as unit quaternions q = a + bi + cj + dk with ||q|| = 1.
   Anti-Hermitian Lie algebra skew-symmetry: A_ji = -A_ij guarantees U_ji = U_ij^{-1} = U_ij^*.
3. Triangles (2-simplices): Wilson loop holonomy / curvature tensor:
   W_ijk = U_ij * U_jk * U_ki in SU(2)
   Scalar curvature: F_ijk = Re(W_ijk) = 1/2 Tr(W_ijk) in [-1, 1].
   A flat gauge field yields W_ijk = 1. Non-trivial curvature creates topological holonomy.
"""

import math
import torch
import torch.nn as nn
import torch.nn.functional as F

def quaternion_mul(q1: torch.Tensor, q2: torch.Tensor) -> torch.Tensor:
    """Computes quaternion product q1 * q2 for tensors of shape [..., 4] (w, x, y, z)."""
    w1, x1, y1, z1 = q1[..., 0], q1[..., 1], q1[..., 2], q1[..., 3]
    w2, x2, y2, z2 = q2[..., 0], q2[..., 1], q2[..., 2], q2[..., 3]
    w = w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2
    x = w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2
    y = w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2
    z = w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2
    return torch.stack([w, x, y, z], dim=-1)


class SU2GaugeSimplicialComplex(nn.Module):
    """
    Non-Abelian SU(2) Gauge Complex over a Polytope Simplicial Grid.
    Modulates token trajectories based on parallel transport holonomy along simplicial faces.
    """
    def __init__(self, num_vertices: int = 11, d_model: int = 256):
        super().__init__()
        self.num_vertices = num_vertices
        self.d_model = d_model

        # Lie algebra su(2) generators for directed edges: [V, V, 3] (Pauli basis sigma_x, sigma_y, sigma_z)
        self.edge_algebra = nn.Parameter(torch.randn(num_vertices, num_vertices, 3) * 0.05)
        self.curvature_proj = nn.Linear(1, d_model, bias=False)

    def get_su2_connections(self) -> torch.Tensor:
        """
        Computes unit quaternionic gauge transport operators U_ij in SU(2).
        Returns:
            U: [V, V, 4] where U[i, j] is unit quaternion representing U_{ij}
        """
        # Enforce anti-symmetry: A_ji = -A_ij
        skew = 0.5 * (self.edge_algebra - self.edge_algebra.transpose(0, 1))  # [V, V, 3]
        theta = torch.norm(skew, dim=-1, keepdim=True) + 1e-8  # [V, V, 1]
        axis = skew / theta
        w = torch.cos(theta)
        xyz = torch.sin(theta) * axis
        return torch.cat([w, xyz], dim=-1)  # [V, V, 4]

    def compute_triangle_curvature(self, coords: torch.Tensor) -> torch.Tensor:
        """
        Computes the expected Wilson loop holonomy curvature weighted by token barycentric coordinates.
        Args:
            coords: [Batch, SeqLen, num_vertices] barycentric weights w(x)
        Returns:
            curvature_feature: [Batch, SeqLen, d_model]
        """
        U = self.get_su2_connections()  # [V, V, 4]
        # Invert U for the closing edge: U_ki = U_ik^*
        # Compute U_ij * U_jk: [V, V, 1, 4] * [1, V, V, 4]
        # To keep it O(V^3) compute efficient for V=11:
        V = self.num_vertices
        U_ij = U.unsqueeze(2).expand(V, V, V, 4)
        U_jk = U.unsqueeze(0).expand(V, V, V, 4)
        U_ik = U.transpose(0, 1).unsqueeze(1).expand(V, V, V, 4)  # U_ki = U[k, i]
        
        W_2step = quaternion_mul(U_ij, U_jk)
        W_loop = quaternion_mul(W_2step, U_ik)  # [V, V, V, 4]
        
        # Real part Re(W_loop) is 1/2 Tr(W_ijk) in [-1, 1]
        F_ijk = W_loop[..., 0]  # [V, V, V]

        # Contract with token barycentric weights: sum_ijk (w_i * w_j * w_k * F_ijk)
        # coords: [B, T, V]
        holonomy = torch.einsum("bti,btj,btk,ijk->bt", coords, coords, coords, F_ijk)  # [B, T]
        return self.curvature_proj(holonomy.unsqueeze(-1))
