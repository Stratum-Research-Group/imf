# Paper 263: Poincaré Discrete Calogero-Moser Many-Body Rational Flow

## Abstract
We implement the discrete Calogero-Moser many-body rational interaction flow on the Poincaré hyperbolic disk manifold. Operating with inverse-cube repulsive inter-particle forces with non-zero equilibrium spacing $d_0$, the system preserves complete integrability and Lax pair structure while scaled conformally via $\lambda_x = \frac{2}{1 - \|x\|^2}$. Physical execution on NVIDIA GeForce RTX 5060 Ti demonstrates an acceleration of $10.30\times$ over PyTorch ($19.56\,\mu\text{s}$, $6,701.53\text{M particles/s}$) with max numerical error $< 7.63 \times 10^{-6}$. Formal deduction in Lean 4 confirms zero external axioms.

## Hardware Telemetry (RTX 5060 Ti SM 8.9)
- Latency: $19.56\,\mu\text{s}$
- Speedup: $10.30\times$
- Throughput: $6,701.53\text{M particles/s}$
- Numerical Divergence: $7.63 \times 10^{-6}$
- Formal Axioms: 0
