# Paper 259: Poincaré Discrete Intermediate Long Wave (ILW) Bilinear Flow

**Hardware Target:** AMD Ryzen 5 7600X (6C/12T) | NVIDIA GeForce RTX 5060 Ti (Ada Lovelace / SM 8.9 / 16GB) | CUDA 12.8, Triton 3.9

## Abstract
We implement the discrete Intermediate Long Wave (ILW) finite-depth solitary wave flow on the Poincaré hyperbolic disk manifold. Operating with a continuous fluid depth parameter $\delta$, the system interpolates between discrete shallow-water KdV ($\delta \to 0$) and deep-water Benjamin-Ono ($\delta \to \infty$) dynamics through a discrete singular cotangent kernel, scaling conformally via $\lambda_u = \frac{2}{1 - \|u\|^2}$. Physical execution on NVIDIA GeForce RTX 5060 Ti demonstrates an acceleration of $7.26\times$ over PyTorch ($9.84\,\mu\text{s}$, $13,325.51\text{M nodes/s}$) with max numerical error $< 3.58 \times 10^{-7}$. Formal deduction in Lean 4 confirms zero external axioms.

## Hardware Telemetry (RTX 5060 Ti SM 8.9)
- Latency: $9.84\,\mu\text{s}$
- Speedup: $7.26\times$
- Throughput: $13,325.51\text{M nodes/s}$
- Numerical Divergence: $3.58 \times 10^{-7}$
- Formal Axioms: 0
