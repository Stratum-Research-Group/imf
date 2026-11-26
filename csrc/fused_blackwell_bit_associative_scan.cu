/*
 * fused_blackwell_bit_associative_scan.cu
 *
 * Microarchitectural CUDA SM 12.0 (Blackwell) Bitplane Associative Memory Scan Kernel.
 * Implements in-register parallel prefix scan over 2-bit quantized diagonal recurrent transitions:
 *    h_t = a_t * h_{t-1} + b_t
 * Using warp-level shuffle instructions (__shfl_up_sync, __shfl_xor_sync) and bitplane unpacking.
 *
 * Compiled with:
 *   nvcc -O3 -shared -Xcompiler -fPIC -arch=sm_120 -o csrc/fused_blackwell_bit_associative_scan.so csrc/fused_blackwell_bit_associative_scan.cu
 */

#include <cuda_runtime.h>
#include <stdint.h>
#include <stdio.h>

#define WARP_SIZE 32
#define CHUNK_SIZE 32

struct ScanState {
    float a; // Multiplicative transition decay
    float b; // Additive state injection
};

// Associative binary operator: (a2, b2) * (a1, b1) = (a2 * a1, a2 * b1 + b2)
__device__ __forceinline__ ScanState associative_combine(ScanState second, ScanState first) {
    ScanState out;
    out.a = second.a * first.a;
    out.b = second.a * first.b + second.b;
    return out;
}

// In-register warp prefix scan using __shfl_up_sync
__device__ __forceinline__ ScanState warp_prefix_scan(ScanState val) {
    unsigned int mask = 0xffffffff;
    #pragma unroll
    for (int offset = 1; offset < WARP_SIZE; offset *= 2) {
        float other_a = __shfl_up_sync(mask, val.a, offset);
        float other_b = __shfl_up_sync(mask, val.b, offset);
        if ((threadIdx.x & (WARP_SIZE - 1)) >= offset) {
            ScanState prev;
            prev.a = other_a;
            prev.b = other_b;
            val = associative_combine(val, prev);
        }
    }
    return val;
}

extern "C" __global__ void fused_blackwell_bit_associative_scan_kernel(
    const uint8_t* __restrict__ bitplane_in, // Packed 2-bit inputs [batch, seq_len / 4, hidden_dim]
    const float* __restrict__ lambda_decay,   // Transition parameters [hidden_dim]
    const float* __restrict__ scale_table,    // 4-entry dequantization LUT
    float* __restrict__ state_out,            // Output hidden states [batch, seq_len, hidden_dim]
    int batch_size,
    int seq_len,
    int hidden_dim
) {
    // Each warp processes 32 time steps for a single (batch, hidden_dim) coordinate
    int warp_id = (blockIdx.x * blockDim.x + threadIdx.x) / WARP_SIZE;
    int lane_id = threadIdx.x % WARP_SIZE;

    int total_warps = (gridDim.x * blockDim.x) / WARP_SIZE;
    int coords = batch_size * hidden_dim;

    for (int c = warp_id; c < coords; c += total_warps) {
        int b_idx = c / hidden_dim;
        int h_idx = c % hidden_dim;

        float lambda = lambda_decay[h_idx];
        float prev_total_a = 1.0f;
        float prev_total_b = 0.0f;

        // Process sequence in chunks of 32 steps (one step per lane)
        int num_chunks = (seq_len + WARP_SIZE - 1) / WARP_SIZE;
        for (int chunk = 0; chunk < num_chunks; ++chunk) {
            int t = chunk * WARP_SIZE + lane_id;

            ScanState local_elem;
            local_elem.a = (t < seq_len) ? lambda : 1.0f;
            local_elem.b = 0.0f;

            if (t < seq_len) {
                // Unpack 2-bit input symbol
                int byte_idx = (b_idx * (seq_len / 4) + (t / 4)) * hidden_dim + h_idx;
                uint8_t packed = bitplane_in[byte_idx];
                int bit_shift = (t % 4) * 2;
                uint8_t symbol = (packed >> bit_shift) & 0x03;
                local_elem.b = scale_table[symbol];
            }

            // Perform intra-warp associative scan
            ScanState scanned = warp_prefix_scan(local_elem);

            // Incorporate boundary state carried over from previous chunk
            scanned.b = scanned.a * prev_total_b + scanned.b;
            scanned.a = scanned.a * prev_total_a;

            if (t < seq_len) {
                int out_idx = (b_idx * seq_len + t) * hidden_dim + h_idx;
                state_out[out_idx] = scanned.b;
            }

            // Broadcast the chunk-ending cumulative state to all lanes for the next chunk
            prev_total_a = __shfl_sync(0xffffffff, scanned.a, WARP_SIZE - 1);
            prev_total_b = __shfl_sync(0xffffffff, scanned.b, WARP_SIZE - 1);
        }
    }
}

extern "C" void launch_fused_blackwell_bit_associative_scan(
    const uint8_t* bitplane_in,
    const float* lambda_decay,
    const float* scale_table,
    float* state_out,
    int batch_size,
    int seq_len,
    int hidden_dim,
    cudaStream_t stream
) {
    int threads_per_block = 256;
    int warps_per_block = threads_per_block / WARP_SIZE;
    int total_warps_needed = batch_size * hidden_dim;
    int num_blocks = (total_warps_needed + warps_per_block - 1) / warps_per_block;
    if (num_blocks > 65535) num_blocks = 65535;

    fused_blackwell_bit_associative_scan_kernel<<<num_blocks, threads_per_block, 0, stream>>>(
        bitplane_in,
        lambda_decay,
        scale_table,
        state_out,
        batch_size,
        seq_len,
        hidden_dim
    );
}
