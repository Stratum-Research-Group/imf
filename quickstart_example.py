"""
quickstart_example.py
Minimal 5-line Quickstart Example for IMF (Interaction Model Foundations).
Demonstrates:
1. MultiHeadSAVGLayer with 10D Decayotton Polytope Virtual Grid.
2. Fast Triton forward scan on CUDA.
3. Constant O(1) recurrent step inference without KV cache growth.
"""

import torch
from imf import MultiHeadSAVGLayer

# 1. Initialize IMF Multi-Head SAVG Layer with 10D Polytope Virtual Grid
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
layer = MultiHeadSAVGLayer(d_model=128, num_heads=4, preset="decayotton_orthoplex").to(device)

# 2. Parallel Sequence Forward Pass (Causal Scan)
x = torch.randn(2, 512, 128, device=device) # [Batch=2, Tokens=512, Dim=128]
out_seq = layer(x)
print(f"[✓] Parallel Sequence Forward Output Shape: {out_seq.shape}")

# 3. Constant O(1) Recurrent Step Inference (Zero KV Cache Bloat)
s_state, a_state = layer.init_state(batch_size=2, device=device)
x_token = torch.randn(2, 128, device=device) # Single incoming token

out_token, (s_next, a_next) = layer.step(x_token, s_state, a_state)
print(f"[✓] O(1) Recurrent Token Output Shape    : {out_token.shape}")
print(f"[✓] Symmetric State Shape (S_t)          : {s_next.shape}")
print(f"[✓] Antisymmetric State Shape (A_t)      : {a_next.shape}")
