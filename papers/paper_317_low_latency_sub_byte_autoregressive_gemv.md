# Paper 317: Low-Latency Sub-Byte Autoregressive GEMV Contractions on Blackwell SM 12.0 Architectures
## Warp-Synchronous Tree Reductions and In-Register Decoding for Batch-1 Generation

**Author**: Stratum Research Group & Nicholas Charles Mynhardt  
**Date**: November 2026  
**Hardware Verification Target**: NVIDIA GeForce RTX 5060 Ti 16GB (Blackwell SM 12.0)  
**Kernel Artifact**: `csrc/fused_blackwell_fp4_gemv.cu` $\to$ `csrc/fused_blackwell_fp4_gemv.so`  
**Lean 4 Toolchain**: `leanprover/lean4:v4.18.0`  
**Certified Invariants**: 0 `sorry` | 0 unproven axioms  

---

### Abstract
During autoregressive token generation, the batch size is strictly $M = 1$, converting the primary computational workload from compute-bound matrix-matrix multiplication (GEMM) into memory-bandwidth-bound matrix-vector contraction (GEMV). We introduce an optimized Blackwell SM 12.0 kernel that unpacks 4-bit PLQ Voronoi centroids directly inside warp registers and accumulates inner products via warp-synchronous butterfly shuffle reductions (`__shfl_down_sync`). The kernel delivers single-token decoding latencies of $<0.14\text{ ms}$ on local RTX 5060 Ti silicon.
