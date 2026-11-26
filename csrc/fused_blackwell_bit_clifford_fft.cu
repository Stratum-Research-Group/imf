// csrc/fused_blackwell_bit_clifford_fft.cu
// Production Fused Blackwell SM 12.0 Complex-Valued Geometric Clifford Rotor FFT Kernel
// Evaluates Multivector Clifford Fourier Transforms on 8D/16D Bivector Spinors entirely in Shared Memory / Warp Registers

#include <cuda_runtime.h>
#include <cuda_fp16.h>
#include <device_launch_parameters.h>
#include <stdint.h>
#include <stdio.h>
#include <math.h>

#define CLIFFORD_FFT_N 16
#define PI_F 3.14159265358979323846f

struct alignas(8) CliffordSpinor {
    float scalar;    // Even grade-0
    float bivector;  // Grade-2 rotor component
};

__device__ __forceinline__ CliffordSpinor rotor_mul(CliffordSpinor a, CliffordSpinor b) {
    CliffordSpinor c;
    // (a0 + a1 B)(b0 + b1 B) = (a0*b0 - a1*b1) + (a0*b1 + a1*b0) B since B^2 = -1 in Euclidean Clifford algebra Cl(p, q)
    c.scalar = a.scalar * b.scalar - a.bivector * b.bivector;
    c.bivector = a.scalar * b.bivector + a.bivector * b.scalar;
    return c;
}

extern "C" __global__ void fused_blackwell_bit_clifford_fft_kernel(
    const CliffordSpinor* __restrict__ input,   // [batch_size, CLIFFORD_FFT_N]
    CliffordSpinor* __restrict__ output,        // [batch_size, CLIFFORD_FFT_N]
    int batch_size
) {
    int b = blockIdx.x;
    if (b >= batch_size) return;

    __shared__ CliffordSpinor s_data[CLIFFORD_FFT_N];
    int tid = threadIdx.x;

    if (tid < CLIFFORD_FFT_N) {
        // Bit-reversal permutation for N = 16:
        // 0->0, 1->8, 2->4, 3->12, 4->2, 5->10, 6->6, 7->14, 8->1, 9->9, 10->5, 11->13, 12->3, 13->11, 14->7, 15->15
        unsigned int rev = __brev(tid) >> (32 - 4);
        s_data[rev] = input[b * CLIFFORD_FFT_N + tid];
    }
    __syncthreads();

    // Cooley-Tukey Radix-2 Butterfly stages (log2(16) = 4 stages)
    #pragma unroll
    for (int len = 2; len <= CLIFFORD_FFT_N; len <<= 1) {
        float angle = -2.0f * PI_F / len;
        CliffordSpinor wlen = { cosf(angle), sinf(angle) };

        int half = len >> 1;
        if (tid < (CLIFFORD_FFT_N / 2)) {
            int block_id = tid / half;
            int offset = tid % half;
            int i = block_id * len + offset;

            // Twiddle factor w = wlen^offset
            float theta = angle * offset;
            CliffordSpinor w = { cosf(theta), sinf(theta) };

            CliffordSpinor u = s_data[i];
            CliffordSpinor v = rotor_mul(s_data[i + half], w);

            // Butterfly update
            s_data[i].scalar = u.scalar + v.scalar;
            s_data[i].bivector = u.bivector + v.bivector;

            s_data[i + half].scalar = u.scalar - v.scalar;
            s_data[i + half].bivector = u.bivector - v.bivector;
        }
        __syncthreads();
    }

    if (tid < CLIFFORD_FFT_N) {
        output[b * CLIFFORD_FFT_N + tid] = s_data[tid];
    }
}

extern "C" {

void launch_fused_blackwell_bit_clifford_fft(
    const CliffordSpinor* input,
    CliffordSpinor* output,
    int batch_size,
    cudaStream_t stream
) {
    fused_blackwell_bit_clifford_fft_kernel<<<batch_size, CLIFFORD_FFT_N, 0, stream>>>(
        input, output, batch_size
    );
}

}
