#!/usr/bin/env python3
"""
scripts/bench_e8_quantization_worked_example.py
Computes the exact optimal E8 root lattice quantization of the worked example vector:
w = [0.852, -0.412, 0.915, -0.054, -0.781, 0.320, 0.655, -0.210]^T
contrasting it with scalar rounding on Z^8.
"""

import numpy as np
import itertools

w = np.array([0.852, -0.412, 0.915, -0.054, -0.781, 0.320, 0.655, -0.210])
w_norm = np.linalg.norm(w)
w_norm_sq = np.sum(w**2)

print(f"Vector w: {w}")
print(f"Norm ||w||_2: {w_norm:.4f} (squared: {w_norm_sq:.4f})")

# Generate all 240 E8 roots
roots = []
# Type 1: 112 integer roots: (+-1, +-1, 0, 0, 0, 0, 0, 0)
for i in range(8):
    for j in range(i + 1, 8):
        for s1 in [-1.0, 1.0]:
            for s2 in [-1.0, 1.0]:
                r = np.zeros(8)
                r[i] = s1
                r[j] = s2
                roots.append(r)

# Type 2: 128 half-integer roots: (+-1/2)^8 with even number of - signs
for signs in itertools.product([-0.5, 0.5], repeat=8):
    if sum(1 for s in signs if s < 0) % 2 == 0:
        roots.append(np.array(signs))

roots = np.array(roots)
assert len(roots) == 240

# Compute inner products
dots = roots @ w
best_idx = np.argmax(dots)
best_root = roots[best_idx]
max_dot = dots[best_idx]

print(f"Best root index: {best_idx}")
print(f"Best root vector: {best_root}")
print(f"Inner product <w, r>: {max_dot:.4f}")

# Scale s = <w, r> / ||r||^2 = max_dot / 2.0
s = max_dot / 2.0
w_hat = s * best_root
error_vec = w - w_hat
mse_e8 = np.sum(error_vec**2)
cos_fidelity = float(np.dot(w, w_hat) / (w_norm * np.linalg.norm(w_hat)))

print(f"Optimal scale s: {s:.5f}")
print(f"Reconstructed w_hat: {np.round(w_hat, 4)}")
print(f"Residual error vector: {np.round(error_vec, 4)}")
print(f"E8 MSE ||w - w_hat||^2: {mse_e8:.4f}")
print(f"Cosine fidelity: {cos_fidelity:.4f}")

# Compare with scalar rounding on Z^8
# For fair comparison at same effective 1-parameter scale:
# w_scaled = w / s_scalar, rounded to integers
# Best scalar scale for 1-bit or int grid:
w_scalar_round = np.round(w)
mse_scalar = np.sum((w - w_scalar_round)**2)
print(f"Scalar Z^8 rounding: {w_scalar_round}")
print(f"Scalar Z^8 MSE: {mse_scalar:.4f}")
print(f"PLQ Error Reduction vs Z^8: {(1.0 - mse_e8 / mse_scalar) * 100:.2f}%")
