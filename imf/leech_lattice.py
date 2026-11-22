"""
imf/leech_lattice.py
====================
Exact 24-Dimensional Leech Lattice (Lambda_24) Minimal Root Generator and Quantizer.

Generates the complete set of 196,560 minimal roots of norm^2 = 32 (norm = sqrt(8) ~ 2.82842712)
in R^24 using the extended binary Golay code G_24 via the standard Conway-Sloane construction:
  1. Type 1: 1,104 vectors of shape (+-4, +-4, 0^22)
  2. Type 2: 97,152 vectors of shape (+-2^8, 0^16) on the 759 octads of G_24 with even minus signs
  3. Type 3: 98,304 vectors of shape (-+3, +-1^23) matching G_24 codeword parity signs
Total: 1,104 + 97,152 + 98,304 = 196,560 minimal roots.
"""

from typing import Optional, Tuple
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

from imf.triton_leech_kernel import fused_leech24_gemv


def generate_extended_golay_codewords() -> np.ndarray:
    """
    Constructs the 4,096 codewords of the extended binary Golay code G_24 [24, 12, 8].
    Generator matrix G = [I_12 | B] where B is a bordered circulant matrix derived
    from the quadratic residues modulo 11.
    """
    qr = {1, 3, 4, 5, 9}
    B = np.zeros((12, 12), dtype=np.uint8)
    B[0, 1:] = 1
    B[1:, 0] = 1
    for i in range(11):
        for j in range(11):
            if i == j or ((j - i) % 11) in qr:
                B[i + 1, j + 1] = 1

    G = np.hstack([np.eye(12, dtype=np.uint8), B])
    messages = np.array(list(np.ndindex((2,) * 12)), dtype=np.uint8)
    codewords = (messages @ G) % 2
    return codewords  # shape: (4096, 24)


def generate_leech24_minimal_roots() -> torch.Tensor:
    """
    Generates all 196,560 minimal roots of the 24-dimensional Leech lattice Lambda_24.
    Returns:
        torch.Tensor of shape [196560, 24] with dtype float32,
        each row having norm sqrt(8) ~ 2.82842712.
    """
    codewords = generate_extended_golay_codewords()

    # 1. Type 1: (+-4, +-4, 0^22) -> binom(24, 2) * 4 = 276 * 4 = 1,104 vectors
    type1_list = []
    for i in range(24):
        for j in range(i + 1, 24):
            for s1 in [4, -4]:
                for s2 in [4, -4]:
                    v = np.zeros(24, dtype=np.int8)
                    v[i] = s1
                    v[j] = s2
                    type1_list.append(v)
    type1 = np.array(type1_list, dtype=np.int8)

    # 2. Type 2: (+-2^8, 0^16) on the 759 octads of G_24 with even number of minus signs
    # 759 * 2^7 = 97,152 vectors
    octads = codewords[codewords.sum(axis=1) == 8]
    sign_choices_7 = np.array(list(np.ndindex((2,) * 7)), dtype=np.int8)
    sign_choices_8 = np.hstack([sign_choices_7, (sign_choices_7.sum(axis=1) % 2)[:, None]])
    signs_type2 = np.where(sign_choices_8 == 0, 2, -2).astype(np.int8)  # (128, 8)

    type2_list = []
    for oct in octads:
        idx = np.where(oct == 1)[0]
        vecs = np.zeros((128, 24), dtype=np.int8)
        vecs[:, idx] = signs_type2
        type2_list.append(vecs)
    type2 = np.vstack(type2_list)

    # 3. Type 3: (-+3, +-1^23) where signs come from G_24 codewords
    # 24 * 4,096 = 98,304 vectors
    signs_all = np.where(codewords == 0, 1, -1).astype(np.int8)  # (4096, 24)
    type3_list = []
    for k in range(24):
        v = signs_all.copy()
        v[:, k] *= -3
        type3_list.append(v)
    type3 = np.vstack(type3_list)

    all_roots = np.vstack([type1, type2, type3]).astype(np.float32)
    # Scaled such that norm is sqrt(8) ~ 2.82842712 (norm^2 = 32 in standard integers, / 2.0 -> norm^2 = 8)
    roots_tensor = torch.from_numpy(all_roots) * 0.5
    return roots_tensor


class LeechLinear(nn.Module):
    """
    Sub-bit Linear layer quantized to the 24-dimensional Leech lattice.
    Each 24-weight block is indexed by a Leech root index (0 .. 196,559).
    Bits-per-weight: log2(196560) / 24 ~ 17.58 / 24 ~ 0.733 bpw (+ scale ~ 1.0 bpw).
    """

    def __init__(
        self,
        in_features: int,
        out_features: int,
        bias: bool = False,
        scale_block_size: int = 48,
        codebook: Optional[torch.Tensor] = None,
    ):
        super().__init__()
        assert in_features % 24 == 0, f"in_features ({in_features}) must be divisible by 24"
        assert scale_block_size % 24 == 0, f"scale_block_size ({scale_block_size}) must be divisible by 24"

        self.in_features = in_features
        self.out_features = out_features
        self.scale_block_size = scale_block_size

        if codebook is None:
            # Generate or register codebook
            codebook = generate_leech24_minimal_roots()
        self.register_buffer("codebook", codebook, persistent=False)

        # Discrete root indices: [out_features, in_features // 24]
        self.register_buffer(
            "indices",
            torch.zeros((out_features, in_features // 24), dtype=torch.int32),
        )
        # Block scales: [out_features, in_features // scale_block_size]
        self.scales = nn.Parameter(
            torch.ones((out_features, in_features // scale_block_size), dtype=torch.float16)
        )

        if bias:
            self.bias = nn.Parameter(torch.zeros(out_features, dtype=torch.float16))
        else:
            self.register_parameter("bias", None)

    def dequantize_weight(self) -> torch.Tensor:
        """
        Dequantizes the weight matrix to dense float [out_features, in_features].
        """
        # Look up 24D roots: [out_features, in_features // 24, 24]
        roots = self.codebook[self.indices.long()]
        # Reshape to [out_features, num_scale_blocks, scale_block_size]
        W_blocks = roots.reshape(self.out_features, -1, self.scale_block_size)
        scales_exp = self.scales.unsqueeze(-1).to(roots.dtype)
        # Normalize: unit root RMS norm factor (norm is sqrt(8) so RMS is sqrt(8)/sqrt(24) = 1/sqrt(3) ~ 0.57735)
        # Scale to match block RMS
        W = (W_blocks * scales_exp).reshape(self.out_features, self.in_features)
        return W

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass using GPU Triton fused Leech GEMV if CUDA & batch_size==1,
        otherwise vectorized dequantization fallback.
        """
        orig_shape = x.shape
        x_2d = x.reshape(-1, self.in_features)

        if x.is_cuda and x_2d.shape[0] == 1 and x.dtype == torch.float16:
            # Fused Triton Leech GEMV path
            roots_cuda = self.codebook.to(device=x.device, dtype=torch.float32)
            out = fused_leech24_gemv(
                x_2d,
                self.indices,
                self.scales,
                roots_cuda,
                scale_block_size=self.scale_block_size,
            )
        else:
            # Dequantized matmul fallback
            W = self.dequantize_weight().to(device=x.device, dtype=x.dtype)
            out = F.linear(x_2d, W)

        if self.bias is not None:
            out = out + self.bias.to(out.dtype)

        return out.reshape(*orig_shape[:-1], self.out_features)
