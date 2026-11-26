"""
imf/virtualized_leech_cell.py
Hierarchical 24-Dimensional Leech Lattice (\u039b_24) Virtualized Cell Layer.
Explores D > 2 nesting over the 196,560 minimal roots of the Leech lattice:
- Physical storage: Exactly 1 base Golay/Leech slice in R^24 (1,024 minimal root vectors = ~98.3 KB)
- Nested addressing:
    D=1: 1,024 virtual states
    D=2: 1,024^2 \u2248 1.05 \u00d7 10^6 virtual states
    D=3: 1,024^3 \u2248 1.07 \u00d7 10^9 virtual states
    D=4: 1,024^4 \u2248 1.10 \u00d7 10^12 virtual states
- Autograd support via Straight-Through Estimator (STE).
- Evaluates quantization distortion, memory savings, and throughput.
"""

import time
import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Tuple, List, Dict, Any
from imf.scaffold_100b_leech_mope import LeechLatticeQuantizer


class VirtualizedLeechCell(nn.Module):
    """
    24-Dimensional Leech Lattice (\u039b_24) Hierarchical Virtual Cell.
    Recursively nests D levels of Leech root contractions:
        x_D = \u2211_{d=0}^{D-1} \u03b3^d \u00b7 c_d,  c_d \u2208 \u039b_24
    """

    def __init__(self, depth: int = 3, scale_factor: float = 0.5, slice_size: int = 1024, device: str = "cpu"):
        super().__init__()
        self.depth = depth
        self.scale_factor = scale_factor
        self.slice_size = slice_size
        
        # Physical storage: exactly 1 unit slice of Leech roots in R^24
        quantizer = LeechLatticeQuantizer(d_group=24)
        roots = quantizer._generate_canonical_leech_slice(sample_size=slice_size)
        self.register_buffer("base_roots", roots.to(device))  # [slice_size, 24] float32
        
        # Learnable continuous transition bias per depth level
        self.level_biases = nn.Parameter(torch.zeros(depth, 24, device=device))

    @property
    def total_addressable_virtual_cells(self) -> float:
        return float(self.slice_size ** self.depth)

    @property
    def physical_memory_bytes(self) -> int:
        return self.base_roots.numel() * self.base_roots.element_size()

    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, List[torch.Tensor]]:
        """
        Hierarchical Voronoi Bisection in 24 Dimensions:
        Input:  [Batch, 24] continuous embedding vector
        Output:
            reconstructed: [Batch, 24] quantized coordinate evaluated on-demand
            virtual_addresses: [depth, Batch] sequence of selected Leech root indices
        """
        batch_size = x.shape[0]
        device = x.device
        
        curr_vec = x.clone()
        virtual_addresses = []
        reconstructed = torch.zeros_like(x)
        
        # Navigate depth levels in registers (O(D) operations)
        for d in range(self.depth):
            radius = self.scale_factor ** d
            level_roots = self.base_roots.to(device) * radius
            
            # Distance / dot-product with 1024 Leech roots: [Batch, 1024]
            scores = torch.matmul(curr_vec, level_roots.T)
            best_idx = torch.argmax(scores, dim=-1)  # [Batch]
            virtual_addresses.append(best_idx)
            
            selected_root = level_roots[best_idx]  # [Batch, 24]
            reconstructed = reconstructed + selected_root
            
            # Residual for next recursive nesting level
            curr_vec = curr_vec - selected_root + self.level_biases[d]
            
        # Straight-Through Estimator (STE)
        reconstructed = x + (reconstructed - x).detach()
        return reconstructed, virtual_addresses


def benchmark_leech_coset_expansion():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print("=" * 80)
    print("  IMF 24D Leech Lattice (\u039b_24) Coset Expansion Benchmark (D > 2)")
    print(f"  Target Device: {device} ({torch.cuda.get_device_name(0) if device=='cuda' else 'CPU'})")
    print("=" * 80)

    depths = [1, 2, 3, 4]
    results = []
    batch_size = 128

    for d in depths:
        cell = VirtualizedLeechCell(depth=d, scale_factor=0.5, slice_size=1024, device=device)
        total_cells = cell.total_addressable_virtual_cells
        base_bytes = cell.physical_memory_bytes
        # Equivalent FP16 memory: total_cells * 24 dims * 2 bytes
        equiv_fp16_bytes = total_cells * 24 * 2
        comp_ratio = equiv_fp16_bytes / base_bytes if base_bytes > 0 else 1.0

        # Run forward projection and compute reconstruction error
        x = torch.randn(batch_size, 24, device=device, requires_grad=True)
        
        # Warmup
        for _ in range(3):
            _ = cell(x)
        if device == "cuda":
            torch.cuda.synchronize()

        iters = 50
        t0 = time.perf_counter()
        for _ in range(iters):
            reconstructed, addrs = cell(x)
        if device == "cuda":
            torch.cuda.synchronize()
        latency_ms = ((time.perf_counter() - t0) / iters) * 1000.0

        loss = F.mse_loss(reconstructed, x)
        loss.backward()

        print(f"Depth D={d:1d} | Virtual Cells: {total_cells:12.2e} | Physical RAM: {base_bytes/1024:6.1f} KB | Equivalent FP16: {equiv_fp16_bytes/(1024*1024):10.2f} MB | Comp: {comp_ratio:12.2e}x | Latency: {latency_ms:.3f} ms | MSE: {loss.item():.5f}")

        results.append({
            "depth": d,
            "total_cells": total_cells,
            "physical_bytes": base_bytes,
            "equiv_fp16_bytes": equiv_fp16_bytes,
            "compression_ratio": comp_ratio,
            "latency_ms": latency_ms,
            "reconstruction_mse": float(loss.item())
        })

    import json
    from pathlib import Path
    out_file = Path("docs/benchmarks/leech_coset_expansion_benchmark.json")
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n[✓] Leech coset expansion results saved to {out_file}")
    return results


if __name__ == "__main__":
    benchmark_leech_coset_expansion()
