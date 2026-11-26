#include <cuda_runtime.h>
#include <device_launch_parameters.h>
#include <cuda_fp16.h>
#include <cstdint>
#include <cstdio>

extern "C" {

// Kernel for packing and unpacking high-dimensional polytope coordinate slices
// across NVLink peer-to-peer memory allocations.
__global__ void nvlink_polytope_p2p_slice_kernel(
    const half* __restrict__ src_polytope_coords, // [num_tokens, polytope_dim] on Peer GPU
    half* __restrict__ dst_polytope_coords,       // [num_tokens, polytope_dim] on Local GPU
    int num_tokens,
    int polytope_dim,
    float scale_factor
) {
    int token_idx = blockIdx.x;
    if (token_idx >= num_tokens) return;

    int tid = threadIdx.x;
    int stride = blockDim.x;

    const half* src_row = src_polytope_coords + token_idx * polytope_dim;
    half* dst_row = dst_polytope_coords + token_idx * polytope_dim;

    for (int d = tid; d < polytope_dim; d += stride) {
        float val = __half2float(src_row[d]) * scale_factor;
        dst_row[d] = __float2half(val);
    }
}

// Host launch function verifying peer access and executing direct copy
cudaError_t launch_nvlink_polytope_p2p_transfer(
    int src_dev,
    int dst_dev,
    const half* d_src,
    half* d_dst,
    int num_tokens,
    int polytope_dim,
    float scale_factor,
    cudaStream_t stream
) {
    int can_access = 0;
    cudaDeviceCanAccessPeer(&can_access, dst_dev, src_dev);

    cudaSetDevice(dst_dev);
    if (can_access && src_dev != dst_dev) {
        cudaDeviceEnablePeerAccess(src_dev, 0);
    }

    int threads = 256;
    nvlink_polytope_p2p_slice_kernel<<<num_tokens, threads, 0, stream>>>(
        d_src, d_dst, num_tokens, polytope_dim, scale_factor
    );

    return cudaGetLastError();
}

}
