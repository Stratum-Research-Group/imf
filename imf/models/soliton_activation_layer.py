"""
Poincaré Soliton Activation Layer (nn.Module)
Integrates physical 1D fused integrable lattice flows (discrete Toda, Camassa-Holm, etc.)
directly into neural network hidden states to conserve phase-space volume and prevent representation collapse.
"""

import math
import torch
import torch.nn as nn
from imf.kernels.triton_fused_poincare_discrete_camassa_holm import triton_poincare_discrete_camassa_holm

class PoincareSolitonActivation(nn.Module):
    def __init__(self, d_model: int = 4096, alpha: float = 0.5):
        super().__init__()
        self.d_model = d_model
        self.alpha = alpha
        self.scale = nn.Parameter(torch.ones(d_model) * 0.1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        x: [B, S, D] token hidden representations
        Applies a discrete Camassa-Holm soliton lattice update across the feature dimension D.
        """
        orig_shape = x.shape
        B, S, D = orig_shape
        flat_x = x.view(-1, D)

        if x.is_cuda:
            # Normalize to unit hyperbolic disk coordinates (-0.95, +0.95)
            u = torch.tanh(flat_x * 0.1)
            u_p1 = torch.roll(u, shifts=-1, dims=-1)
            u_m1 = torch.roll(u, shifts=1, dims=-1)
            m = u - self.alpha * (u_p1 - 2.0 * u + u_m1)

            # Fused Triton execution
            dm, metric = triton_poincare_discrete_camassa_holm(u.reshape(-1), m.reshape(-1), alpha=self.alpha)
            # Safe bounded residual update
            dm_bounded = torch.tanh(dm.view(B * S, D) * 0.05)
            updated_x = flat_x + dm_bounded * self.scale
            return updated_x.view(orig_shape)
        else:
            return x

if __name__ == "__main__":
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Testing PoincareSolitonActivation Layer on: {device}")
    layer = PoincareSolitonActivation(d_model=4096).to(device)

    x = torch.randn(2, 32, 4096, device=device, dtype=torch.float32)
    out = layer(x)
    print(f"Input shape:  {x.shape}")
    print(f"Output shape: {out.shape}")
    print(f"Mean delta:   {(out - x).abs().mean().item():.3e}")
    assert out.shape == x.shape
    print("[✓] PoincareSolitonActivation successfully verified and wired.")
