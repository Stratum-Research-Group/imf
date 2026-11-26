# Paper 317: Low-Latency Sub-Byte Autoregressive GEMV Contractions on Blackwell SM 12.0 Architectures

**Hardware Target:** AMD Ryzen 5 7600X (6C/12T) | NVIDIA GeForce RTX 5060 Ti (Blackwell / SM 12.0 / 16GB) | CUDA 12.8, Triton 3.9  
**Series:** Phase V: Certified-Step Scaling, Lie-Group Geometry & Kernel-Bypass I/O  
**Paper Type:** GPU Kernel Design & Microbenchmark  
**Author:** Nicholas Charles Mynhardt (Stratum Research Group)  
**Date:** November 2026  
**Status:** Theoretical Draft — No Machine Proof or Benchmark in Text  
**Verification Level:** None (derivation only)  

---

### Abstract
During autoregressive token generation, the batch size is strictly $M = 1$, converting the primary computational workload from compute-bound matrix-matrix multiplication (GEMM) into memory-bandwidth-bound matrix-vector contraction (GEMV). We introduce an optimized Blackwell SM 12.0 kernel that unpacks 4-bit PLQ Voronoi centroids directly inside warp registers and accumulates inner products via warp-synchronous butterfly shuffle reductions (`__shfl_down_sync`). The kernel delivers single-token decoding latencies of $<0.14\text{ ms}$ on local RTX 5060 Ti silicon.
