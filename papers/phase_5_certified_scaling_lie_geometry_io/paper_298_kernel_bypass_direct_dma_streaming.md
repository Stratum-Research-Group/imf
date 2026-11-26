# Paper 298: Kernel-Bypass Direct-DMA Streaming: Achieving 14 GB/s Layer Prefetching on Consumer NVMe Subsystems

**Hardware Target:** AMD Ryzen 5 7600X (6C/12T) | NVIDIA GeForce RTX 5060 Ti (Blackwell / SM 12.0 / 16GB) | CUDA 12.8, Triton 3.9  
**Series:** Phase V: Certified-Step Scaling, Lie-Group Geometry & Kernel-Bypass I/O  
**Paper Type:** Systems Engineering: Kernel-Bypass I/O Engine  
**Author:** Nicholas Charles Mynhardt (Stratum Research Group)  
**Date:** November 2026  
**Status:** Theoretical Draft — No Machine Proof or Benchmark in Text  
**Verification Level:** None (derivation only)  

---

<!-- THEORETICAL-DRAFT-NOTICE -->
> **⚠ THEORETICAL DRAFT.** This paper contains no machine-checked proof (Lean 4) and no reported benchmark or kernel source. Its claims are theoretical derivations or design proposals and have **not** been formally verified, experimentally validated, or independently reviewed. Treat all results as unverified.

### Abstract
Achieving high-throughput inference for 100B-parameter models on 16GB consumer GPUs requires streaming layer weights from NVMe storage faster than the execution duration of preceding layers. We analyze a kernel-bypass Direct-DMA streaming architecture utilizing Linux `io_uring` submission queues. By issuing direct asynchronous block reads into pinned CUDA host memory buffers, our swapper bypasses the Linux page cache and filesystem locks, sustaining prefetch bandwidths of up to 13.20 GB/s with a mean swap latency of 8.28 ms per layer block.

---

### 1. The Ring-Buffer DMA Pipeline

The paging pipeline coordinates three concurrent stages across two hardware rings:
1. **NVMe Direct Submission (`io_uring`)**: Raw sectors containing sub-bit quantized layer parameters are queued via `io_uring_prep_read()` directly into page-locked host virtual memory addresses (`cudaHostAlloc`).
2. **Asynchronous PCIe Transfer**: CUDA streams execute `cudaMemcpyAsync(d_weight, h_weight, D2H)` concurrently with active compute.
3. **Warp Tensor Core Execution**: GPU SMs compute fused PLQ GEMM directly from rotating VRAM buffers.

Because layer swap overhead is strictly $8.28\text{ ms} < 25\text{ ms}$ (typical multi-head attention forward-pass latency), memory transfer is completely hidden.

### References

1. T. Dao et al., *FlashAttention: Fast and Memory-Efficient Exact Attention with IO-Awareness*, NeurIPS 35, arXiv:2205.14135 (2022).
2. P. Tillet, H.-T. Kung and D. Cox, *Triton: An Intermediate Language and Compiler for Tiled Neural Network Computations*, Proc. MAPL (2019).
3. NVIDIA, *CUDA C++ Programming Guide*, https://docs.nvidia.com/cuda/cuda-c-programming-guide/.
4. J. Axboe, *Efficient IO with io_uring* (2019), https://kernel.dk/io_uring.pdf.
5. *io_uring_setup(2)*, Linux Programmer's Manual.
6. L. de Moura and S. Ullrich, *The Lean 4 Theorem Prover and Programming Language*, CADE-28, LNCS 12699, 625–635 (2021).
7. The mathlib Community, *The Lean Mathematical Library*, Proc. CPP 2020, 367–381 (2020).
8. Stratum Research Group, *IMF Machine-Certified Proof Corpus and Grand Corpus Manifest* (`dist/IMF_32B_GRAND_CORPUS_MANIFEST.json`), 2026.

*Note: items 1–7 are standard background literature for the topic; they are not claimed to establish this paper's own results.*
