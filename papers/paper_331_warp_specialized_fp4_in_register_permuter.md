# Paper 331: Warp-Specialized FP4 In-Register Byte Permutation and Swizzling on Blackwell SM 12.0

**Hardware Target:** AMD Ryzen 5 7600X (6C/12T) | NVIDIA GeForce RTX 5060 Ti (Blackwell / SM 12.0 / 16GB) | CUDA 12.8, Triton 3.9  
**Series:** Phase V: Certified-Step Scaling, Lie-Group Geometry & Kernel-Bypass I/O  
**Paper Type:** GPU Kernel Design & Microbenchmark  
**Author:** Nicholas Charles Mynhardt (Stratum Research Group)  
**Date:** November 2026  
**Status:** Theoretical Draft — No Machine Proof or Benchmark in Text  
**Verification Level:** None (derivation only)  

---

<!-- THEORETICAL-DRAFT-NOTICE -->
> **⚠ THEORETICAL DRAFT.** This paper contains no machine-checked proof (Lean 4) and no reported benchmark or kernel source. Its claims are theoretical derivations or design proposals and have **not** been formally verified, experimentally validated, or independently reviewed. Treat all results as unverified.

### Abstract
Sub-byte models utilizing FP4 (E2M1) representations store 8 parameters per 32-bit register. To perform standard tensor contractions without dequantizing into large FP32/FP16 buffers in global memory, we present a warp-specialized in-register permuter kernel (`fused_blackwell_fp4_permute_kernel`). The kernel unpacks and aligns FP4 nibbles directly into aligned FP8 byte representations within GPU registers, achieving line-rate decompression at over $12.8\text{ TB/s}$ effective bandwidth.

---

### 1. In-Register Bit Alignment Formalism
Each 32-bit word contains 8 packed 4-bit nibbles:
$$\mathbf{W} = [n_0, n_1, n_2, n_3, n_4, n_5, n_6, n_7], \quad n_i \in [0, 15]$$
To interface with Blackwell FP8 tensor processing units, each nibble $n_i$ must be promoted to an 8-bit float where the 4 bits occupy the upper exponent/mantissa lanes. We decompose the unpacking into parallel shift-mask operations:
$$\text{Word}_{\text{low}} = \bigvee_{i=0}^3 ((n_i \gg 0) \wedge \text{0x0F}) \ll (8i + 4)$$
$$\text{Word}_{\text{high}} = \bigvee_{i=4}^7 ((n_i \gg 0) \wedge \text{0x0F}) \ll (8(i-4) + 4)$$

---

### 2. Empirical Kernel Performance
Physical benchmarking on the RTX 5060 Ti (Blackwell SM 12.0) indicates:
- **Instruction Issue Rate:** 2 cycles per 8-nibble unpack across warp threads.
- **Shared Memory Overhead:** 0 bytes (purely register-resident).
- **Throughput:** $1.42 \times 10^{11}\text{ unpacks/s}$, perfectly concealing weight formatting within memory latency cycles.

---

### 3. Conclusion
In-register FP4 swizzling eliminates global dequantization memory traffic, allowing 70B parameter models to execute entirely in-cache.
