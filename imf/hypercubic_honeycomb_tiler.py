"""
imf/hypercubic_honeycomb_tiler.py
Hypercubic Honeycomb Tiler for Continuous Infinite Spatial Memory Addressing.

Tessellates Euclidean hyperspace R^D into a discrete Z^D hypercubic honeycomb {4, 3^(D-2), 4}.
Continuous token vectors are mapped to their containing hypercubic unit cell:
    cell_coord = floor(x / cell_size) in Z^D
with relative sub-cell continuous offset:
    offset = (x / cell_size) - cell_coord in [0, 1)^D
Supports dynamic unbounded sequence streaming and neighbor face navigation (2*D facet neighbors).
"""

from typing import Dict, List, Optional, Tuple
import math
import torch
import torch.nn as nn
import torch.nn.functional as F


class HypercubicHoneycombTiler(nn.Module):
    """
    Hypercubic Honeycomb Spatial Tiler in dimension D.
    
    Tessellates continuous token projections across infinite Z^D cells.
    Each cell has 2*D facet-adjacent neighbor directions (±e_i).
    """

    def __init__(
        self,
        d_model: int,
        dim_space: int = 8,
        cell_size: float = 1.0,
        hash_table_size: int = 65536,
    ):
        super().__init__()
        self.d_model = d_model
        self.dim_space = dim_space
        self.cell_size = cell_size
        self.hash_table_size = hash_table_size
        
        # Projection frame to spatial dimension D
        self.proj_spatial = nn.Linear(d_model, dim_space, bias=False)
        
        # Large prime coefficients for spatial Z^D spatial hashing
        primes = [73856093, 19349663, 83492791, 2654435761, 50331653, 982451653, 4393139, 389]
        if dim_space > len(primes):
            # Extend with deterministic pseudo-primes
            primes += [int(2**31 - 1 - i * 10007) for i in range(dim_space - len(primes))]
        hash_coeffs = torch.tensor(primes[:dim_space], dtype=torch.long)
        self.register_buffer("hash_coeffs", hash_coeffs)
        
        self.reset_parameters()

    def reset_parameters(self):
        q, _ = torch.linalg.qr(torch.randn(self.d_model, self.dim_space))
        with torch.no_grad():
            self.proj_spatial.weight.copy_(q.t())

    def forward(
        self, x: torch.Tensor
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """
        Tiles continuous tokens into discrete Z^D honeycomb coordinates.
        
        Args:
            x: Input tensor [batch, seq_len, d_model] or [tokens, d_model]
            
        Returns:
            cell_coords: Discrete integer cell coordinates in Z^D [..., dim_space]
            cell_hashes: Spatial hash keys bounded in [0, hash_table_size - 1] [...]
            local_offsets: Continuous fractional offset inside the unit cell [..., dim_space]
        """
        orig_shape = x.shape
        if x.dim() == 3:
            B, S, D = x.shape
            x_flat = x.reshape(B * S, D)
        else:
            x_flat = x
            
        # Continuous projection into R^D
        coords_continuous = self.proj_spatial(x_flat) / self.cell_size  # [N, dim_space]
        
        # Discrete cell index via floor
        cell_coords = torch.floor(coords_continuous).to(torch.long)  # [N, dim_space]
        
        # Local continuous coordinates in [0, 1)^dim_space
        local_offsets = coords_continuous - cell_coords.to(coords_continuous.dtype)
        
        # Compute spatial hash key: sum_i (c_i * p_i) mod hash_table_size
        cell_hashes = torch.remainder(
            torch.sum(cell_coords * self.hash_coeffs, dim=-1),
            self.hash_table_size
        )
        
        if x.dim() == 3:
            cell_coords = cell_coords.view(B, S, self.dim_space)
            cell_hashes = cell_hashes.view(B, S)
            local_offsets = local_offsets.view(B, S, self.dim_space)
            
        return cell_coords, cell_hashes, local_offsets

    def get_facet_neighbors(self, cell_coords: torch.Tensor) -> torch.Tensor:
        """
        Returns the 2*D facet-adjacent neighbor coordinates for given cells in Z^D.
        
        Args:
            cell_coords: [..., dim_space]
            
        Returns:
            neighbor_coords: [..., 2*dim_space, dim_space]
        """
        shape = cell_coords.shape
        D = self.dim_space
        
        # Basis offsets: +e_i and -e_i for each axis i
        offsets = torch.zeros(2 * D, D, dtype=torch.long, device=cell_coords.device)
        for i in range(D):
            offsets[2 * i, i] = 1
            offsets[2 * i + 1, i] = -1
            
        # Expand and add offsets
        expanded_coords = cell_coords.unsqueeze(-2)  # [..., 1, D]
        neighbor_coords = expanded_coords + offsets   # [..., 2*D, D]
        return neighbor_coords
