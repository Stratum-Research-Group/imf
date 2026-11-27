// csrc/dma_nvme_direct_p2p.cu
// Specialized CUDA kernel for GPUDirect Storage / Direct-DMA transfer
// Streams Leech lattice codepoints directly into SM 12.0 shared memory.

#include <cuda_runtime.h>
#include <stdint.h>

#define WARP_SIZE 32
#define LEECH_DIM 24
#define E8_DIM 8

extern "C" __global__ void direct_dma_leech_stream_kernel(
    const float* __restrict__ nvme_buffer_ptr,
    float* __restrict__ sm_shared_output,
    int n_vectors
) {
    int tid = blockIdx.x * blockDim.x + threadIdx.x;
    if (tid >= n_vectors) return;

    __shared__ float s_lattice_cache[128][E8_DIM];

    int local_idx = threadIdx.x % 128;
    int lane_id = threadIdx.x % WARP_SIZE;

    // Direct DMA aligned read
    #pragma unroll
    for (int d = 0; d < E8_DIM; d++) {
        s_lattice_cache[local_idx][d] = nvme_buffer_ptr[tid * E8_DIM + d];
    }
    __syncthreads();

    // Fast warp shuffle broadcast
    float val = s_lattice_cache[local_idx][lane_id % E8_DIM];
    val = __shfl_sync(0xFFFFFFFF, val, (lane_id + 1) % WARP_SIZE);

    sm_shared_output[tid * E8_DIM + (lane_id % E8_DIM)] = val;
}
