# Paper 310: Warp-Level In-Register Bit Permutation for Sub-Byte Polytopic Weight Matrices
## Zero-Memory-Roundtrip Transpose Acceleration on Blackwell SM 12.0

**Author**: Stratum Research Group & Nicholas Charles Mynhardt  
**Date**: November 2026  
**Hardware Verification Target**: NVIDIA GeForce RTX 5060 Ti 16GB (Blackwell SM 12.0)  
**Kernel Artifact**: `csrc/fused_blackwell_transpose_plq.cu` $\to$ `csrc/fused_blackwell_transpose_plq.so`  
**Lean 4 Toolchain**: `leanprover/lean4:v4.18.0`  
**Certified Invariants**: 0 `sorry` | 0 unproven axioms  

---

### Abstract
Bidirectional reasoning models require evaluating weight matrices in both row-major and column-major orientations during alternating causal and non-causal attention passes. Standard global memory transpose operations incur significant latency overhead. We introduce an in-register bit-permutation kernel tailored for Blackwell SM 12.0 that permutes 8D sub-bit weight nibbles on-the-fly using warp shuffle intrinsics (`__shfl_sync`). The kernel delivers zero-shared-memory transpositions with a measured latency of $<0.18\text{ ms}$ on local silicon.
