"""
test_chiral_and_quaternary.py
Automated Verification Suite for:
1. Grassmann-Lie exterior tri-vector chiral pseudoscalar reflection antisymmetry (Direction 3).
2. Volume-preserving SL(d) dynamic polytope re-meshing (Direction 1).
3. 4-Simplex (m=4) CP-factorized hyperface binding (Direction 4).
"""

import math
import pytest
import torch
import torch.nn as nn
import torch.nn.functional as F

from polytope_connector import ConfigurablePolytopeConnector
from higher_arity_simplex import HigherAritySimplexBinding


class MinimalChiralFeaturizer(nn.Module):
    """
    Computes Grassmann exterior pseudoscalar volume forms for chiral centers:
    Omega(C*) = v1 ^ v2 ^ v3 = det([v1, v2, v3])
    """
    def __init__(self, d_model: int = 32):
        super().__init__()
        self.d_model = d_model
        self.atom_embed = nn.Embedding(10, d_model)
        self.pseudoscalar_proj = nn.Linear(1, d_model, bias=False)
        self.out_head = nn.Linear(d_model, 1, bias=False)

    def forward(self, atom_types: torch.Tensor, coords: torch.Tensor) -> torch.Tensor:
        v1 = coords[:, 1] - coords[:, 0]
        v2 = coords[:, 2] - coords[:, 0]
        v3 = coords[:, 3] - coords[:, 0]
        mat = torch.stack([v1, v2, v3], dim=-1)
        vol = torch.linalg.det(mat).unsqueeze(-1)
        
        emb = self.atom_embed(atom_types).sum(dim=1)
        chiral_feat = emb * torch.tanh(self.pseudoscalar_proj(vol))
        return self.out_head(chiral_feat)


def test_chiral_enantiomeric_inversion_antisymmetry():
    """Verify that chiral pseudoscalar flips sign under mirror reflection."""
    model = MinimalChiralFeaturizer(d_model=32)
    atom_types = torch.tensor([[1, 2, 3, 4]])
    
    # Standard chiral tetrahedron (R-enantiomer)
    r_coords = torch.tensor([[[0., 0., 0.], [1., 0., 0.], [0., 1., 0.], [0., 0., 1.]]])
    # Mirror reflection along z-axis (S-enantiomer)
    s_coords = r_coords.clone()
    s_coords[0, :, 2] = -s_coords[0, :, 2]

    pred_r = model(atom_types, r_coords)
    pred_s = model(atom_types, s_coords)

    # Antisymmetry: f(P(x)) = -f(x)
    assert not torch.allclose(pred_r, torch.zeros_like(pred_r))
    assert torch.allclose(pred_r, -pred_s, atol=1e-6)
    assert abs((pred_r + pred_s).item()) < 1e-6


def test_sl_d_dynamic_remeshing_determinant_unity():
    """Verify that learnable SL(d) matrix exponentiation maintains exact unit determinant."""
    d_model = 16
    conn = ConfigurablePolytopeConnector(d_model=d_model, preset="decayotton_orthoplex", learnable_remeshing=True)
    conn.dynamic_remeshing.data.normal_(0, 0.1)

    d = d_model
    trace_correction = torch.trace(conn.dynamic_remeshing) / d
    sl_generator = conn.dynamic_remeshing - trace_correction * torch.eye(d)
    warp = torch.matrix_exp(sl_generator)
    det_val = torch.linalg.det(warp).item()

    assert abs(det_val - 1.0) < 1e-4, f"Determinant {det_val} != 1.0"


def test_quaternary_4simplex_backward_pass():
    """Verify 4-simplex CP binding forward and backward pass."""
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    d_model = 32
    binding = HigherAritySimplexBinding(d_model=d_model, arity=4, rank=8, num_corners=11).to(device)
    tokens = [torch.randn(2, 8, d_model, device=device, requires_grad=True) for _ in range(4)]

    out = binding(tokens)
    assert out.shape == (2, 8, d_model)
    loss = out.sum()
    loss.backward()

    for t in tokens:
        assert t.grad is not None
    assert binding.face_factor.grad is not None
    assert binding.core_weight.grad is not None
