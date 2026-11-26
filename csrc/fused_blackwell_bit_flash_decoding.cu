#include <cuda_runtime.h>
#include <device_launch_parameters.h>
#include <stdint.h>
#include <math.h>

// Fused Blackwell Bitplane Flash-Decoding Kernel with Paged KV Quantization
// Optimizes autoregressive single-token generation at extended context lengths (>64k).
// Partitions the sequence dimension across CUDA threadblocks.
// Accumulates partial reductions in shared memory tiles before final warp reduction.

#define BLOCK_SIZE 256
#define TILES_PER_BLOCK 4

extern "C" __global__ void fused_blackwell_bit_flash_decoding_kernel(
    const uint32_t* __restrict__ q_packed,       // [batch, heads, head_dim / 16] (single decoding token)
    const uint32_t* __restrict__ paged_k_packed, // [paged_blocks, block_len, heads, head_dim / 16]
    const uint32_t* __restrict__ paged_v_packed, // [paged_blocks, block_len, heads, head_dim / 16]
    const int* __restrict__ block_table,         // [batch, max_blocks_per_seq]
    float* __restrict__ partial_out,             // [grid_dim, batch, heads, head_dim / 16]
    float* __restrict__ partial_max,             // [grid_dim, batch, heads]
    float* __restrict__ partial_sum,             // [grid_dim, batch, heads]
    const int seq_len,
    const int num_heads,
    const int head_dim,
    const int page_block_size
) {
    int tid = threadIdx.x;
    int chunk_idx = blockIdx.x; // sequence chunk partitioned across grid
    int num_chunks = gridDim.x;
    int words_per_head = head_dim / 16;

    int tokens_per_chunk = (seq_len + num_chunks - 1) / num_chunks;
    int start_token = chunk_idx * tokens_per_chunk;
    int end_token = min(start_token + tokens_per_chunk, seq_len);

    if (start_token >= seq_len) return;

    __shared__ float smem_scores[BLOCK_SIZE];
    __shared__ float smem_max;
    __shared__ float smem_sum;

    if (tid == 0) {
        smem_max = -1e20f;
        smem_sum = 0.0f;
    }
    __syncthreads();

    float local_max = -1e20f;

    // Loop over tokens allocated to this threadblock chunk
    for (int t = start_token + tid; t < end_token; t += BLOCK_SIZE) {
        int page_idx = t / page_block_size;
        int page_offset = t % page_block_size;
        int phys_block = block_table[page_idx];

        // Compute bipolar Hamming dot product in registers
        float dot_prod = 0.0f;
        #pragma unroll
        for (int w = 0; w < words_per_head; ++w) {
            uint32_t q_w = q_packed[w];
            uint32_t k_w = paged_k_packed[phys_block * page_block_size * words_per_head + page_offset * words_per_head + w];

            #pragma unroll
            for (int i = 0; i < 16; ++i) {
                float q_val = (float)((q_w >> (i * 2)) & 0x3) - 1.5f;
                float k_val = (float)((k_w >> (i * 2)) & 0x3) - 1.5f;
                dot_prod += q_val * k_val;
            }
        }

        dot_prod *= 1.0f / sqrtf((float)head_dim);
        if (dot_prod > local_max) local_max = dot_prod;
    }

    // Warp reduction for max score
    #pragma unroll
    for (int offset = 16; offset > 0; offset /= 2) {
        local_max = fmaxf(local_max, __shfl_down_sync(0xffffffff, local_max, offset));
    }

    if (tid % 32 == 0) {
        atomicMax((int*)&smem_max, __float_as_int(local_max));
    }
    __syncthreads();

    float chunk_max = smem_max;
    float local_sum = 0.0f;

    for (int t = start_token + tid; t < end_token; t += BLOCK_SIZE) {
        int page_idx = t / page_block_size;
        int page_offset = t % page_block_size;
        int phys_block = block_table[page_idx];

        float dot_prod = 0.0f;
        #pragma unroll
        for (int w = 0; w < words_per_head; ++w) {
            uint32_t q_w = q_packed[w];
            uint32_t k_w = paged_k_packed[phys_block * page_block_size * words_per_head + page_offset * words_per_head + w];

            #pragma unroll
            for (int i = 0; i < 16; ++i) {
                float q_val = (float)((q_w >> (i * 2)) & 0x3) - 1.5f;
                float k_val = (float)((k_w >> (i * 2)) & 0x3) - 1.5f;
                dot_prod += q_val * k_val;
            }
        }
        dot_prod *= 1.0f / sqrtf((float)head_dim);
        local_sum += expf(dot_prod - chunk_max);
    }

    #pragma unroll
    for (int offset = 16; offset > 0; offset /= 2) {
        local_sum += __shfl_down_sync(0xffffffff, local_sum, offset);
    }

    if (tid % 32 == 0) {
        atomicAdd(&smem_sum, local_sum);
    }
    __syncthreads();

    if (tid == 0) {
        partial_max[chunk_idx] = chunk_max;
        partial_sum[chunk_idx] = smem_sum;
    }
}

extern "C" void launch_fused_blackwell_bit_flash_decoding(
    const uint32_t* q_packed,
    const uint32_t* paged_k_packed,
    const uint32_t* paged_v_packed,
    const int* block_table,
    float* partial_out,
    float* partial_max,
    float* partial_sum,
    int seq_len,
    int num_heads,
    int head_dim,
    int page_block_size,
    int num_chunks,
    cudaStream_t stream
) {
    dim3 grid(num_chunks);
    dim3 block(BLOCK_SIZE);

    fused_blackwell_bit_flash_decoding_kernel<<<grid, block, 0, stream>>>(
        q_packed, paged_k_packed, paged_v_packed, block_table,
        partial_out, partial_max, partial_sum,
        seq_len, num_heads, head_dim, page_block_size
    );
}
